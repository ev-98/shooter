#!/usr/bin/env python3
"""
HIGH NOON SHOWDOWN
==================
Modes:
  LOCAL   — two players, same keyboard (A = P1, L = P2)
  SOLO    — one player vs the clock (SPACE)
  ONLINE  — join/host over LAN using a 4-letter room code

Run the game:
    python main.py

Run a server (for online mode):
    python server.py
"""
import asyncio
import random
import sys
import time

import pygame

from client import NetworkClient
from game import Mode, Session, Settings, State
from sounds import SoundManager
from ui import (
    make_fonts,
    render_draw,
    render_lobby,
    render_menu,
    render_mode_select,
    render_online_setup,
    render_ready,
    render_result,
    render_settings,
    render_timeout,
)

# ── Constants ─────────────────────────────────────────────────────────────────
W, H       = 800, 500
FPS        = 60
TITLE      = "High Noon Showdown"

# Solo / local draw timer bounds (seconds)
DRAW_MIN   = 1.5
DRAW_MAX   = 5.0

# ── Helpers ───────────────────────────────────────────────────────────────────

def player_labels(session: Session):
    if session.mode == Mode.ONLINE:
        my   = "YOU"
        them = "OPPONENT"
        if session.player_idx == 0:
            return my, them
        return them, my
    return "P1", "P2"


def reset_draw_timer() -> float:
    return time.perf_counter() + random.uniform(DRAW_MIN, DRAW_MAX)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    surf  = pygame.display.set_mode((W, H))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()
    fonts = make_fonts()

    sess   = Session()
    net    = NetworkClient()
    tick   = 0

    # Local-only timing
    draw_trigger: float | None = None   # perf_counter time to show DRAW

    # Online setup sub-state
    online_phase   = "choose"        # choose | host_wait | join_ip | join_code
    join_ip        = "127.0.0.1"
    join_code_buf  = ""
    input_focus    = "ip"            # ip | code  (join screen)
    cursor_tick    = 0

    # Result flash
    flash_val      = 0.0             # 0-1 white flash
    mode_selected  = 0               # cursor in mode select screen

    # ── Event loop ────────────────────────────────────────────────────────────
    running = True
    while running:
        dt = clock.tick(FPS)
        tick += 1
        cursor_tick += 1

        # ── Pygame events ─────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                k = event.key

                # ── MENU ──────────────────────────────────────────────────
                if sess.state == State.MENU:
                    if k == pygame.K_RETURN:
                        sess.state = State.MENU  # transition to mode select
                        # Reuse MENU flag; switch manually:
                        sess.state = _go_mode_select(sess)

                # ── MODE SELECT ───────────────────────────────────────────
                elif sess.state == State.MENU and False:  # placeholder
                    pass

                # We use a separate local variable for mode select screen
                # since State.MENU doubles as the mode-select entry point.
                # Handled below after state machine with explicit screen var.

                # ── ONLINE SETUP ──────────────────────────────────────────
                elif sess.state == State.ONLINE_SETUP:
                    if online_phase == "choose":
                        if k == pygame.K_h:
                            net = NetworkClient()
                            net.connect(join_ip)
                            online_phase = "host_connecting"
                        elif k == pygame.K_j:
                            online_phase = "join_ip"
                            input_focus = "ip"
                            join_code_buf = ""
                        elif k in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                            sess.state = State.MENU
                            online_phase = "choose"

                    elif online_phase in ("join_ip", "join_code"):
                        if k == pygame.K_TAB:
                            input_focus = "code" if input_focus == "ip" else "ip"
                        elif k == pygame.K_RETURN:
                            if input_focus == "ip":
                                input_focus = "code"
                            else:
                                # Try to connect and join
                                net = NetworkClient()
                                net.connect(join_ip)
                                online_phase = "join_connecting"
                        elif k == pygame.K_BACKSPACE:
                            if input_focus == "ip":
                                join_ip = join_ip[:-1]
                            else:
                                join_code_buf = join_code_buf[:-1]
                        elif k == pygame.K_ESCAPE:
                            sess.state = State.MENU
                            online_phase = "choose"
                        else:
                            ch = event.unicode
                            if input_focus == "ip" and ch in "0123456789.":
                                if len(join_ip) < 21:
                                    join_ip += ch
                            elif input_focus == "code" and ch.isalpha():
                                if len(join_code_buf) < 4:
                                    join_code_buf += ch.upper()

                    elif online_phase == "host_wait":
                        if k == pygame.K_ESCAPE:
                            net.close()
                            sess.state = State.MENU
                            online_phase = "choose"

                # ── LOBBY ─────────────────────────────────────────────────
                elif sess.state == State.LOBBY:
                    if k == pygame.K_ESCAPE:
                        net.close()
                        sess.state = State.MENU
                        online_phase = "choose"

                # ── READY (local / solo) ───────────────────────────────────
                elif sess.state == State.READY:
                    if sess.mode != Mode.ONLINE:
                        result = _handle_fire_key(k, sess)
                        if result == "false_start":
                            _do_false_start(sess, _key_to_player(k, sess))
                        elif result == "ok":
                            pass  # will be caught in state tick below

                # ── DRAW (local / solo) ────────────────────────────────────
                elif sess.state == State.DRAW:
                    if sess.mode != Mode.ONLINE:
                        result = _handle_fire_key(k, sess)
                        if result == "ok":
                            flash_val = 1.0
                            num = 1 if sess.mode == Mode.SOLO else 2
                            if sess.resolve_local_or_wait(num):
                                sess.state = State.RESULT

                # ── ONLINE DRAW ───────────────────────────────────────────
                elif sess.state == State.DRAW and sess.mode == Mode.ONLINE:
                    if k == pygame.K_SPACE:
                        net.send({"type": "fire"})

                # ── RESULT ────────────────────────────────────────────────
                elif sess.state == State.RESULT:
                    if k == pygame.K_r:
                        if sess.mode == Mode.ONLINE:
                            if sess.is_host:
                                net.send({"type": "rematch"})
                        else:
                            _start_local_round(sess)
                            draw_trigger = reset_draw_timer()
                    elif k == pygame.K_ESCAPE:
                        if sess.mode == Mode.ONLINE:
                            net.close()
                            online_phase = "choose"
                        sess.state = State.MENU

                # ── TIMEOUT ───────────────────────────────────────────────
                elif sess.state == State.TIMEOUT:
                    if k == pygame.K_r:
                        _start_local_round(sess)
                        draw_trigger = reset_draw_timer()
                    elif k == pygame.K_ESCAPE:
                        sess.state = State.MENU

        # ── Mode-select screen (overlaid on MENU state) ────────────────────
        # We use a two-level approach: State.MENU = either main menu or
        # mode select. Track with a local variable.
        # (Handled via _go_mode_select above; see render section.)

        # ── Online fire key (DRAW state, online mode) ──────────────────────
        # Needs to be outside the event loop for the online+draw branch.
        if sess.state == State.DRAW and sess.mode == Mode.ONLINE:
            keys = pygame.key.get_pressed()
            if keys[pygame.K_SPACE]:
                pass  # handled in event loop above to avoid repeat

        # ── Local draw timer tick ──────────────────────────────────────────
        if sess.state == State.READY and sess.mode != Mode.ONLINE:
            if draw_trigger and time.perf_counter() >= draw_trigger:
                sess.set_draw()
                draw_trigger = None
                flash_val = 0.0

        # ── Online: handle network messages ───────────────────────────────
        if sess.mode == Mode.ONLINE or online_phase in (
                "host_connecting", "join_connecting", "host_wait"):
            _poll_network(net, sess, online_phase, join_code_buf,
                          join_ip, sess.online_code)
            # Sync back mutated online_phase
            online_phase = _online_phase_sync(
                net, sess, online_phase, join_code_buf)

        # ── Solo: single-player resolve ────────────────────────────────────
        if sess.state == State.DRAW and sess.mode == Mode.SOLO:
            if 0 in sess.last_times:
                sess.resolve_local_or_wait(1)
                sess.state = State.RESULT
                flash_val = 1.0

        # ── Local 2P resolve ──────────────────────────────────────────────
        if sess.state == State.DRAW and sess.mode == Mode.LOCAL:
            if sess.resolve_local_or_wait(2):
                sess.state = State.RESULT
                flash_val = 1.0

        # ── Flash decay ───────────────────────────────────────────────────
        flash_val = max(0.0, flash_val - 0.04)

        # ── Render ────────────────────────────────────────────────────────
        p1l, p2l = player_labels(sess)
        _render(surf, fonts, sess, tick, flash_val,
                online_phase, join_ip, join_code_buf, input_focus,
                cursor_tick, mode_selected, p1l, p2l)

        pygame.display.flip()

        # ── Mode select key handling (needs render to have run once) ───────
        if sess.state == State.MENU:
            # Peek at pressed keys for mode select navigation
            pass  # handled via KEYDOWN events

    net.close()
    pygame.quit()
    sys.exit()


# ── State helpers ─────────────────────────────────────────────────────────────

_in_mode_select = False   # module-level flag (single-file simplicity)
_mode_select_idx = 0


def _go_mode_select(sess: Session) -> State:
    global _in_mode_select, _mode_select_idx
    _in_mode_select = True
    _mode_select_idx = 0
    return State.MENU  # stay in MENU state, flag drives render


def _handle_fire_key(key, sess: Session) -> str:
    if sess.mode == Mode.LOCAL:
        if key == sess.settings.p1_key:
            return sess.fire(0)
        if key == sess.settings.p2_key:
            return sess.fire(1)
    elif sess.mode == Mode.SOLO:
        if key == sess.settings.solo_key:
            return sess.fire(0)
    return "ignored"


def _key_to_player(key, sess: Session) -> int:
    if sess.mode == Mode.LOCAL and key == sess.settings.p2_key:
        return 1
    return 0


def _do_false_start(sess: Session, player: int):
    sess.false_start_player = player
    winner = 1 - player if sess.mode == Mode.LOCAL else -1
    if winner >= 0:
        sess.winner = winner
        sess.scores[winner] += 1
    sess.state = State.RESULT


def _start_local_round(sess: Session):
    sess.reset_round()
    sess.state = State.READY


def _poll_network(net: NetworkClient, sess: Session,
                  online_phase: str, join_code_buf: str,
                  join_ip: str, room_code: str):
    """Consume all pending network messages."""
    while True:
        msg = net.poll()
        if msg is None:
            break
        t = msg.get("type")

        if t == "created":
            sess.online_code = msg["code"]

        elif t == "joined":
            sess.online_code = msg.get("code", "")

        elif t == "start":
            sess.reset_round()
            sess.state = State.LOBBY

        elif t == "ready":
            sess.reset_round()
            sess.state = State.READY

        elif t == "draw":
            sess.set_draw()

        elif t == "fire":
            net.send({"type": "fire"})

        elif t == "false_start":
            sess.false_start_player = msg["offender"]
            sess.winner = msg["winner"]
            if sess.winner is not None:
                sess.scores[sess.winner % 2] += 1
            sess.state = State.RESULT

        elif t == "result":
            sess.winner = msg["winner"]
            sess.last_times = {int(k): v for k, v in msg["times"].items()}
            if sess.winner is not None:
                sess.scores[sess.winner % 2] += 1
            sess.state = State.RESULT

        elif t == "timeout":
            sess.state = State.TIMEOUT

        elif t == "opponent_left":
            sess.online_error = "Opponent disconnected."
            sess.state = State.MENU

        elif t == "error":
            sess.online_error = msg.get("msg", "Unknown error")

        elif t == "connect_error":
            sess.online_error = msg.get("msg", "Connection failed")


def _online_phase_sync(net: NetworkClient, sess: Session,
                       online_phase: str, join_code_buf: str) -> str:
    """Transition online_phase based on connection + session state."""
    if online_phase == "host_connecting" and net.connected:
        net.send({"type": "create"})
        return "host_wait"
    if online_phase == "join_connecting" and net.connected:
        net.send({"type": "join", "code": join_code_buf})
        return "join_wait"
    if online_phase == "join_wait" and sess.state in (State.LOBBY, State.READY):
        return "in_game"
    if online_phase == "host_wait" and sess.online_code:
        return "host_wait"  # stay until opponent joins
    return online_phase


# ── Render dispatcher ─────────────────────────────────────────────────────────

def _render(surf, fonts, sess: Session, tick: int, flash: float,
            online_phase: str, join_ip: str, join_code_buf: str,
            input_focus: str, cursor_tick: int, mode_selected: int,
            p1l: str, p2l: str):
    global _in_mode_select, _mode_select_idx

    st = sess.state

    if st == State.MENU:
        if _in_mode_select:
            render_mode_select(surf, fonts, _mode_select_idx)
            # Key handling for mode select
            keys = pygame.key.get_pressed()
            # (arrow keys handled via KEYDOWN below — see _handle_mode_select_keys)
        else:
            render_menu(surf, fonts, tick)

    elif st == State.ONLINE_SETUP:
        cursor_on = (cursor_tick // 30) % 2 == 0
        phase_map = {
            "host_connecting": "host_wait",
            "join_connecting": "join_ip",
            "join_wait": "join_code",
        }
        display_phase = phase_map.get(online_phase, online_phase)
        ti = join_ip if input_focus == "ip" else join_code_buf
        render_online_setup(surf, fonts, display_phase, ti, input_focus,
                            sess.online_error, sess.online_code, cursor_on)

    elif st == State.LOBBY:
        render_lobby(surf, fonts, tick)

    elif st == State.READY:
        render_ready(surf, fonts, tick, sess.mode, sess.scores, p1l, p2l)

    elif st == State.DRAW:
        render_draw(surf, fonts, tick, sess.mode, sess.scores, p1l, p2l, flash)

    elif st == State.RESULT:
        render_result(surf, fonts, sess.mode, sess.winner,
                      sess.false_start_player, sess.last_times,
                      sess.scores, p1l, p2l,
                      is_online=sess.mode == Mode.ONLINE,
                      is_host=sess.is_host)

    elif st == State.TIMEOUT:
        render_timeout(surf, fonts)


# ── Mode-select key handler (called from main event loop) ─────────────────────

def handle_mode_select_key(key, sess: Session, net: NetworkClient,
                           join_ip_ref: list, draw_trigger_ref: list,
                           online_phase_ref: list) -> bool:
    """
    Returns True if the event was consumed.
    Mutates sess.state, sess.mode, and the mutable ref lists.
    """
    global _in_mode_select, _mode_select_idx

    if not _in_mode_select:
        return False

    if key in (pygame.K_UP, pygame.K_w):
        _mode_select_idx = (_mode_select_idx - 1) % 4
        return True
    if key in (pygame.K_DOWN, pygame.K_s):
        _mode_select_idx = (_mode_select_idx + 1) % 4
        return True
    if key == pygame.K_ESCAPE:
        _in_mode_select = False
        sess.state = State.MENU
        return True
    if key == pygame.K_RETURN:
        _in_mode_select = False
        if _mode_select_idx == 0:       # SOLO
            sess.mode = Mode.SOLO
            sess.scores = [0, 0]
            sess.reset_round()
            sess.state = State.READY
            draw_trigger_ref[0] = reset_draw_timer()
        elif _mode_select_idx == 1:     # LOCAL
            sess.mode = Mode.LOCAL
            sess.scores = [0, 0]
            sess.reset_round()
            sess.state = State.READY
            draw_trigger_ref[0] = reset_draw_timer()
        elif _mode_select_idx == 2:     # ONLINE
            sess.mode = Mode.ONLINE
            sess.scores = [0, 0]
            sess.player_idx = None
            sess.is_host = False
            sess.online_error = ""
            sess.state = State.ONLINE_SETUP
            online_phase_ref[0] = "choose"
        elif _mode_select_idx == 3:     # SETTINGS
            sess.state = State.SETTINGS
        return True
    return False


# ── Monkeypatched main with mode-select wired in ──────────────────────────────

def main_v2():
    """Full main loop with mode-select integrated cleanly."""
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    surf  = pygame.display.set_mode((W, H))
    pygame.display.set_caption(TITLE)
    clock = pygame.time.Clock()
    fonts = make_fonts()

    sess   = Session()
    net    = NetworkClient()
    snd    = SoundManager(sess.settings)
    tick   = 0

    draw_trigger_ref  = [None]     # mutable reference trick
    online_phase_ref  = ["choose"]
    join_ip_ref       = ["127.0.0.1"]
    join_code_buf     = ""
    input_focus       = "ip"
    cursor_tick       = 0
    flash_val         = 0.0

    settings_selected  = 0    # cursor in settings screen
    settings_listening = False # waiting for a new key binding

    global _in_mode_select, _mode_select_idx
    _in_mode_select = False
    _mode_select_idx = 0

    prev_state = sess.state
    snd.start_wind()
    running = True
    while running:
        clock.tick(FPS)
        tick += 1
        cursor_tick += 1
        op = online_phase_ref[0]

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                k = event.key

                # Mode select screen takes priority
                _old_idx = _mode_select_idx
                if handle_mode_select_key(k, sess, net, join_ip_ref,
                                          draw_trigger_ref, online_phase_ref):
                    op = online_phase_ref[0]
                    if _mode_select_idx != _old_idx:
                        snd.play_blip()
                    elif k == pygame.K_RETURN:
                        snd.play_confirm()
                    continue

                # Main menu
                if sess.state == State.MENU and not _in_mode_select:
                    if k == pygame.K_RETURN:
                        _in_mode_select = True
                        _mode_select_idx = 0
                        snd.play_confirm()

                # Online setup
                elif sess.state == State.ONLINE_SETUP:
                    op = online_phase_ref[0]
                    if op == "choose":
                        if k == pygame.K_h:
                            net = NetworkClient()
                            net.connect(join_ip_ref[0])
                            online_phase_ref[0] = "host_connecting"
                            sess.is_host = True
                            sess.player_idx = 0
                        elif k == pygame.K_j:
                            online_phase_ref[0] = "join_ip"
                            input_focus = "ip"
                            join_code_buf = ""
                        elif k == pygame.K_ESCAPE:
                            sess.state = State.MENU
                            _in_mode_select = True
                    elif op in ("join_ip", "join_code"):
                        if k == pygame.K_TAB:
                            input_focus = "code" if input_focus == "ip" else "ip"
                            online_phase_ref[0] = "join_code" if input_focus == "code" else "join_ip"
                        elif k == pygame.K_RETURN:
                            if input_focus == "ip":
                                input_focus = "code"
                                online_phase_ref[0] = "join_code"
                            else:
                                net = NetworkClient()
                                net.connect(join_ip_ref[0])
                                sess.is_host = False
                                sess.player_idx = 1
                                online_phase_ref[0] = "join_connecting"
                        elif k == pygame.K_BACKSPACE:
                            if input_focus == "ip":
                                join_ip_ref[0] = join_ip_ref[0][:-1]
                            else:
                                join_code_buf = join_code_buf[:-1]
                        elif k == pygame.K_ESCAPE:
                            online_phase_ref[0] = "choose"
                        else:
                            ch = event.unicode
                            if input_focus == "ip" and ch in "0123456789.":
                                if len(join_ip_ref[0]) < 21:
                                    join_ip_ref[0] += ch
                            elif input_focus == "code" and ch.isalpha():
                                if len(join_code_buf) < 4:
                                    join_code_buf += ch.upper()
                    elif op == "host_connecting":
                        if k == pygame.K_ESCAPE:
                            net.close()
                            online_phase_ref[0] = "choose"
                    elif op == "host_wait":
                        if k == pygame.K_ESCAPE:
                            net.close()
                            online_phase_ref[0] = "choose"
                    elif op in ("join_connecting", "join_wait"):
                        if k == pygame.K_ESCAPE:
                            net.close()
                            online_phase_ref[0] = "choose"

                # Lobby
                elif sess.state == State.LOBBY:
                    if k == pygame.K_ESCAPE:
                        net.close()
                        sess.state = State.ONLINE_SETUP
                        online_phase_ref[0] = "choose"

                # Ready
                elif sess.state == State.READY and sess.mode != Mode.ONLINE:
                    res = _handle_fire_key(k, sess)
                    if res == "false_start":
                        snd.play_gunshot()
                        _do_false_start(sess, _key_to_player(k, sess))

                # Draw
                elif sess.state == State.DRAW:
                    if sess.mode == Mode.ONLINE:
                        if k == pygame.K_SPACE:
                            net.send({"type": "fire"})
                            snd.play_gunshot()
                    else:
                        res = _handle_fire_key(k, sess)
                        if res == "ok":
                            flash_val = 1.0
                            snd.play_gunshot()

                # Result
                elif sess.state == State.RESULT:
                    if k == pygame.K_r:
                        if sess.mode == Mode.ONLINE:
                            if sess.is_host:
                                net.send({"type": "rematch"})
                        else:
                            _start_local_round(sess)
                            draw_trigger_ref[0] = reset_draw_timer()
                    elif k == pygame.K_ESCAPE:
                        if sess.mode == Mode.ONLINE:
                            net.close()
                            online_phase_ref[0] = "choose"
                            sess.state = State.ONLINE_SETUP
                        else:
                            sess.state = State.MENU
                            _in_mode_select = True

                # Timeout
                elif sess.state == State.TIMEOUT:
                    if k == pygame.K_r:
                        _start_local_round(sess)
                        draw_trigger_ref[0] = reset_draw_timer()
                    elif k == pygame.K_ESCAPE:
                        sess.state = State.MENU
                        _in_mode_select = True

                # Settings
                elif sess.state == State.SETTINGS:
                    if settings_listening:
                        if k == pygame.K_ESCAPE:
                            settings_listening = False
                        else:
                            if settings_selected == 0:
                                sess.settings.solo_key = k
                            elif settings_selected == 1:
                                sess.settings.p1_key = k
                            elif settings_selected == 2:
                                sess.settings.p2_key = k
                            settings_listening = False
                    else:
                        if k in (pygame.K_UP, pygame.K_w):
                            settings_selected = (settings_selected - 1) % 5
                            snd.play_blip()
                        elif k in (pygame.K_DOWN, pygame.K_s):
                            settings_selected = (settings_selected + 1) % 5
                            snd.play_blip()
                        elif k in (pygame.K_RETURN, pygame.K_SPACE):
                            snd.play_confirm()
                            if settings_selected < 3:
                                settings_listening = True
                            elif settings_selected == 3:
                                sess.settings.sound_on = not sess.settings.sound_on
                            elif settings_selected == 4:
                                sess.settings.music_on = not sess.settings.music_on
                                snd.on_music_toggle()
                        elif k == pygame.K_ESCAPE:
                            sess.state = State.MENU
                            _in_mode_select = True
                            settings_listening = False

        op = online_phase_ref[0]

        # Local draw timer
        if sess.state == State.READY and sess.mode != Mode.ONLINE:
            dt_ref = draw_trigger_ref[0]
            if dt_ref and time.perf_counter() >= dt_ref:
                sess.set_draw()
                draw_trigger_ref[0] = None

        # Local resolve
        if sess.state == State.DRAW and sess.mode == Mode.SOLO:
            if 0 in sess.last_times:
                sess.resolve_local_or_wait(1)
                sess.state = State.RESULT
                flash_val = 1.0

        if sess.state == State.DRAW and sess.mode == Mode.LOCAL:
            if sess.resolve_local_or_wait(2):
                sess.state = State.RESULT
                flash_val = 1.0

        # Network polling
        if sess.mode == Mode.ONLINE or op in (
                "host_connecting", "join_connecting", "join_wait", "host_wait"):
            _poll_network(net, sess, op, join_code_buf,
                          join_ip_ref[0], sess.online_code)
            online_phase_ref[0] = _online_phase_sync(
                net, sess, op, join_code_buf)
            op = online_phase_ref[0]

        flash_val = max(0.0, flash_val - 0.04)

        if sess.state != prev_state:
            if sess.state in (State.MENU, State.READY, State.LOBBY):
                snd.start_wind()
            elif sess.state in (State.DRAW, State.RESULT, State.TIMEOUT):
                snd.stop_wind()
            prev_state = sess.state

        # Render
        p1l, p2l = player_labels(sess)
        cursor_on = (cursor_tick // 30) % 2 == 0

        st = sess.state
        if st == State.MENU and not _in_mode_select:
            render_menu(surf, fonts, tick)
        elif st == State.MENU and _in_mode_select:
            render_mode_select(surf, fonts, _mode_select_idx)
        elif st == State.ONLINE_SETUP:
            ph_disp = {"host_connecting": "host_wait",
                       "join_connecting": "join_ip",
                       "join_wait": "join_code"}.get(op, op)
            ti = join_ip_ref[0] if input_focus == "ip" else join_code_buf
            render_online_setup(surf, fonts, ph_disp, ti, input_focus,
                                sess.online_error, sess.online_code, cursor_on)
        elif st == State.LOBBY:
            render_lobby(surf, fonts, tick)
        elif st == State.READY:
            render_ready(surf, fonts, tick, sess.mode, sess.scores, p1l, p2l,
                         best_solo=sess.best_solo, settings=sess.settings)
        elif st == State.DRAW:
            render_draw(surf, fonts, tick, sess.mode, sess.scores, p1l, p2l,
                        flash_val, best_solo=sess.best_solo, settings=sess.settings)
        elif st == State.RESULT:
            render_result(surf, fonts, sess.mode, sess.winner,
                          sess.false_start_player, sess.last_times,
                          sess.scores, p1l, p2l,
                          is_online=sess.mode == Mode.ONLINE,
                          is_host=sess.is_host,
                          best_solo=sess.best_solo)
        elif st == State.TIMEOUT:
            render_timeout(surf, fonts)
        elif st == State.SETTINGS:
            render_settings(surf, fonts, sess.settings,
                            settings_selected, settings_listening)

        pygame.display.flip()

    net.close()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main_v2()
