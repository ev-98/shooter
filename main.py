#!/usr/bin/env python3
from __future__ import annotations
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
import math
import os
import random
import sys
import time

import pygame

from client import NetworkClient
from game import Mode, Session, Settings, State, WIN_SCORE, load_save, write_save
from server import start_background_server
from sounds import SoundManager
from ui import (
    make_fonts,
    render_data,
    render_draw,
    render_lobby,
    render_match_intro,
    render_menu,
    render_mode_select,
    render_online_setup,
    render_quit_confirm,
    render_ready,
    render_result,
    render_settings,
    render_splash,
    render_timeout,
    render_victory,
)

# ── Constants ─────────────────────────────────────────────────────────────────
W, H       = 800, 500
FPS        = 60
TITLE      = "shooter"

# Relay server — change to a hosted URL for internet play
RELAY_URL  = os.environ.get("SERVER_URL", "ws://localhost:8765")

# Solo / local draw timer bounds (seconds)
DRAW_MIN   = 1.5
DRAW_MAX   = 5.0

# ── Helpers ───────────────────────────────────────────────────────────────────

def player_labels(session: Session):
    if session.mode == Mode.ONLINE:
        my_name  = (session.settings.player_name or "YOU").upper()
        opp_name = (session.opponent_name or "OPPONENT").upper()
        if session.player_idx == 0:
            return my_name, opp_name
        return opp_name, my_name
    if session.mode == Mode.SOLO:
        return (session.settings.player_name or "PLAYER").upper(), ""
    return "P1", "P2"


def reset_draw_timer() -> float:
    return time.perf_counter() + random.uniform(DRAW_MIN, DRAW_MAX)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    pygame.init()
    surf  = pygame.display.set_mode((W, H))
    pygame.display.set_caption(TITLE)
    try:
        pygame.display.set_icon(pygame.image.load("icon.png"))
    except Exception:
        pass
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
                            sess.online_error = ""
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
            _poll_network(net, sess, online_phase, join_code_buf, sess.online_code)
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
                  online_phase: str, join_code_buf: str, room_code: str,
                  online_phase_ref: list | None = None):
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
            sess.online_error = ""

        elif t == "start":
            names = msg.get("names", {})
            opp_idx = str(1 - (sess.player_idx or 0))
            sess.opponent_name = names.get(opp_idx, "OPPONENT")
            sess.scores = [0, 0]
            sess.reset_round()
            sess.state = State.MATCH_INTRO

        elif t == "ready":
            if sess.state == State.MATCH_INTRO:
                # Don't cut the "FIRST TO 10" intro short — the server starts
                # the round immediately after "start", often in the same
                # network batch. Apply it once the local intro timer ends.
                sess.online_ready_pending = True
            else:
                sess.reset_round()
                sess.state = State.READY

        elif t == "draw":
            sess.prompt_char = msg.get("key")
            sess.set_draw()

        elif t == "fire":
            net.send({"type": "fire"})

        elif t == "false_start":
            sess.false_start_player = msg["offender"]
            sess.winner = msg["winner"]
            if sess.winner is not None:
                sess.scores[sess.winner % 2] += 1
            sess.state = State.RESULT

        elif t == "misfire":
            sess.misfire_player = msg["offender"]
            sess.winner = msg["winner"]
            if sess.winner is not None:
                sess.scores[sess.winner % 2] += 1
            sess.state = State.RESULT

        elif t == "cheat":
            sess.cheat_player = msg["offender"]
            sess.winner = msg["winner"]
            if sess.winner is not None:
                sess.scores[sess.winner % 2] += 1
            sess.state = State.RESULT

        elif t == "result":
            sess.winner = msg["winner"]
            sess.last_times = {int(k): v for k, v in msg["times"].items()}
            if sess.winner is not None:
                sess.scores[sess.winner % 2] += 1
            # Derive pressed key for any player whose fire was recorded.
            # Falls back gracefully when the server doesn't relay key_pressed.
            if sess.prompt_char:
                for p in sess.last_times:
                    if not sess.pressed_display[p]:
                        sess.pressed_display[p] = sess.prompt_char
            sess.state = State.RESULT

        elif t == "timeout":
            sess.state = State.TIMEOUT

        elif t == "key_pressed":
            player = msg.get("player")
            key = msg.get("key", "")
            if player is not None and key:
                sess.pressed_display[player] = key

        elif t == "rematch_vote":
            pass  # server sends "start" when both votes arrive; tracked for UI by rematch_voted

        elif t == "opponent_left":
            _active = {State.MATCH_INTRO, State.LOBBY, State.READY, State.DRAW, State.RESULT}
            if sess.state in _active:
                my_idx = sess.player_idx or 0
                sess.winner = my_idx
                sess.false_start_player = None
                sess.last_times = {}
                sess.state = State.RESULT
                net.close()
            elif sess.state == State.VICTORY:
                sess.rematch_declined = True
            else:
                sess.online_error = "Opponent disconnected."
                sess.state = State.MENU

        elif t == "error":
            sess.online_error = msg.get("msg", "Unknown error")
            if online_phase_ref is not None and online_phase in ("join_wait", "join_connecting"):
                net.close()
                online_phase_ref[0] = "join_code"

        elif t == "connect_error":
            sess.online_error = msg.get("msg", "Connection failed")


def _online_phase_sync(net: NetworkClient, sess: Session,
                       online_phase: str, join_code_buf: str) -> str:
    """Transition online_phase based on connection + session state."""
    if online_phase == "host_connecting" and net.connected:
        net.send({"type": "create", "name": sess.settings.player_name})
        return "host_wait"
    if online_phase == "join_connecting" and net.connected:
        net.send({"type": "join", "code": join_code_buf,
                  "name": sess.settings.player_name})
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
            "join_connecting": "join_code",
            "join_wait": "join_code",
        }
        display_phase = phase_map.get(online_phase, online_phase)
        render_online_setup(surf, fonts, display_phase, join_code_buf,
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
                      is_host=sess.is_host,
                      flash=flash,
                      cheat_player=sess.cheat_player)

    elif st == State.TIMEOUT:
        render_timeout(surf, fonts)


# ── Mode-select key handler (called from main event loop) ─────────────────────

def handle_mode_select_key(key, sess: Session, net: NetworkClient,
                           draw_trigger_ref: list,
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
    _direct = {pygame.K_1: 0, pygame.K_2: 1, pygame.K_3: 2, pygame.K_4: 3}
    if key in _direct:
        _mode_select_idx = _direct[key]
    if key in (pygame.K_RETURN, pygame.K_SPACE) or key in _direct:
        _in_mode_select = False
        if _mode_select_idx == 0:       # SOLO
            sess.mode = Mode.SOLO
            sess.scores = [0, 0]
            sess.reset_round()
            sess.state = State.MATCH_INTRO
        elif _mode_select_idx == 1:     # LOCAL
            sess.mode = Mode.LOCAL
            sess.scores = [0, 0]
            sess.reset_round()
            sess.state = State.MATCH_INTRO
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
    start_background_server()   # embedded relay; silently skips if port busy
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    surf  = pygame.display.set_mode((W, H))
    pygame.display.set_caption(TITLE)
    try:
        pygame.display.set_icon(pygame.image.load("icon.png"))
    except Exception:
        pass
    clock = pygame.time.Clock()
    fonts = make_fonts()

    sess   = Session()
    net    = NetworkClient()

    _save = load_save()
    sess.settings.player_name = _save.get("player_name", "PLAYER")
    sess.settings.sound_on    = _save.get("sound_on", True)
    sess.settings.music_on    = _save.get("music_on", True)
    sess.best_solo            = _save.get("best_solo", None)
    sess.online_wins          = _save.get("online_wins", 0)
    time_played_total         = float(_save.get("time_played", 0.0))
    session_start             = time.perf_counter()

    snd    = SoundManager(sess.settings)
    tick   = 0

    draw_trigger_ref  = [None]     # mutable reference trick
    online_phase_ref  = ["choose"]
    join_code_buf     = ""
    cursor_tick       = 0
    flash_val         = 0.0
    match_intro_until = 0.0
    result_entered_at:  float | None = None
    victory_entered_at: float | None = None
    intro_fade        = 0.0   # 0 = black, 1 = fully visible; plays once on launch
    splash_done       = False
    splash_gun_fired  = False
    splash_start      = time.perf_counter()

    settings_selected  = 0    # cursor in settings screen
    name_editing       = False
    online_fired       = False  # prevents sending more than one fire/misfire per round
    rematch_voted      = False  # local player pressed SPACE on victory screen
    bell_pending_at:  float | None = None
    local_grace_deadline: float | None = None  # 1 s window after first LOCAL fire
    quit_confirm       = False
    quit_confirm_at    = 0.0
    quit_selected      = 0   # 0 = YES, 1 = NO

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

                # Any key skips the splash
                if not splash_done:
                    splash_done = True
                    snd.play_bell()
                    snd.start_wind()
                    continue

                # Mode select screen takes priority
                _old_idx = _mode_select_idx
                if handle_mode_select_key(k, sess, net,
                                          draw_trigger_ref, online_phase_ref):
                    op = online_phase_ref[0]
                    if _mode_select_idx != _old_idx:
                        snd.play_blip()
                    elif k == pygame.K_SPACE:
                        snd.play_confirm()
                    continue

                # Quit confirm popup
                _QUITTABLE = {State.MATCH_INTRO, State.LOBBY,
                               State.RESULT, State.VICTORY, State.TIMEOUT}
                if quit_confirm:
                    do_quit = False
                    do_cancel = False
                    if k in (pygame.K_UP, pygame.K_w):
                        quit_selected = (quit_selected - 1) % 2
                        snd.play_blip()
                    elif k in (pygame.K_DOWN, pygame.K_s):
                        quit_selected = (quit_selected + 1) % 2
                        snd.play_blip()
                    elif k == pygame.K_1:
                        quit_selected = 0
                        do_quit = True
                        snd.play_confirm()
                    elif k == pygame.K_2:
                        quit_selected = 1
                        do_cancel = True
                        snd.play_confirm()
                    elif k in (pygame.K_RETURN, pygame.K_SPACE):
                        snd.play_confirm()
                        if quit_selected == 0:
                            do_quit = True
                        else:
                            do_cancel = True
                    elif k == pygame.K_ESCAPE:
                        do_cancel = True
                    if do_quit:
                        if sess.mode == Mode.ONLINE:
                            net.close()
                            online_phase_ref[0] = "choose"
                            sess.state = State.ONLINE_SETUP
                        else:
                            sess.state = State.MENU
                            _in_mode_select = True
                        quit_confirm = False
                    elif do_cancel:
                        frozen = time.perf_counter() - quit_confirm_at
                        if draw_trigger_ref[0]:
                            draw_trigger_ref[0] += frozen
                        match_intro_until += frozen
                        if result_entered_at is not None:
                            result_entered_at += frozen
                        quit_confirm = False
                    continue
                if k == pygame.K_ESCAPE and sess.state in _QUITTABLE and sess.mode != Mode.ONLINE:
                    quit_confirm = True
                    quit_confirm_at = time.perf_counter()
                    quit_selected = 0
                    continue

                # Main menu
                if sess.state == State.MENU and not _in_mode_select:
                    if k == pygame.K_SPACE:
                        _in_mode_select = True
                        _mode_select_idx = 0
                        snd.play_confirm()

                # Online setup
                elif sess.state == State.ONLINE_SETUP:
                    op = online_phase_ref[0]
                    if op == "choose":
                        if k == pygame.K_h:
                            net = NetworkClient()
                            net.connect(RELAY_URL)
                            online_phase_ref[0] = "host_connecting"
                            sess.is_host = True
                            sess.player_idx = 0
                            sess.opponent_name = ""
                        elif k == pygame.K_j:
                            online_phase_ref[0] = "join_code"
                            join_code_buf = ""
                        elif k == pygame.K_ESCAPE:
                            sess.state = State.MENU
                            _in_mode_select = True
                    elif op == "join_code":
                        if k in (pygame.K_RETURN, pygame.K_SPACE):
                            if join_code_buf:
                                net = NetworkClient()
                                net.connect(RELAY_URL)
                                sess.is_host = False
                                sess.player_idx = 1
                                online_phase_ref[0] = "join_connecting"
                        elif k == pygame.K_BACKSPACE:
                            join_code_buf = join_code_buf[:-1]
                        elif k == pygame.K_ESCAPE:
                            online_phase_ref[0] = "choose"
                            sess.online_error = ""
                        else:
                            ch = event.unicode
                            if ch.isalpha() and len(join_code_buf) < 4:
                                join_code_buf += ch.upper()
                    elif op in ("host_connecting", "host_wait",
                                "join_connecting", "join_wait"):
                        if k == pygame.K_ESCAPE:
                            net.close()
                            online_phase_ref[0] = "choose"
                            sess.online_error = ""

                # Ready
                elif sess.state == State.READY:
                    if sess.mode == Mode.LOCAL:
                        res = _handle_fire_key(k, sess)
                        if res == "false_start":
                            snd.play_gunshot()
                            _do_false_start(sess, _key_to_player(k, sess))
                    elif event.unicode:  # SOLO / ONLINE — any non-modifier key jumps the gun
                        snd.play_gunshot()
                        if sess.mode == Mode.ONLINE:
                            if not online_fired:
                                net.send({"type": "fire", "key": event.unicode.upper()})
                                online_fired = True
                        else:
                            _do_false_start(sess, 0)

                # Draw
                elif sess.state == State.DRAW:
                    ch = event.unicode.upper()
                    if sess.mode == Mode.ONLINE:
                        if ch and not online_fired:  # ignore bare modifier keys; only fire once
                            if ch == sess.prompt_char:
                                t_ms = int((time.perf_counter() - sess.draw_time) * 1000) \
                                       if sess.draw_time else 0
                                net.send({"type": "fire", "client_time_ms": t_ms, "key": ch})
                                snd.play_gunshot()
                                online_fired = True
                            else:
                                net.send({"type": "misfire", "key": ch})
                                snd.play_gunshot()
                                online_fired = True
                    elif sess.prompt_char is not None:  # SOLO
                        if ch:
                            sess.pressed_display[0] = ch
                            if ch == sess.prompt_char:
                                res = sess.fire(0)
                                if res == "ok":
                                    flash_val = 1.0
                                    snd.play_gunshot()
                            else:
                                snd.play_gunshot()
                                sess.do_misfire(0)
                                sess.state = State.RESULT
                    else:  # LOCAL
                        res = _handle_fire_key(k, sess)
                        if res == "ok":
                            flash_val = 1.0
                            snd.play_gunshot()
                            if len(sess.last_times) == 1 and local_grace_deadline is None:
                                local_grace_deadline = time.perf_counter() + 1.0

                # Result
                elif sess.state == State.RESULT:
                    if k == pygame.K_r:
                        if sess.mode == Mode.ONLINE:
                            if sess.is_host:
                                net.send({"type": "rematch"})
                        elif sess.mode == Mode.LOCAL:
                            _start_local_round(sess)
                            draw_trigger_ref[0] = reset_draw_timer()

                # Victory (match over)
                elif sess.state == State.VICTORY:
                    if sess.mode == Mode.ONLINE:
                        if k == pygame.K_SPACE and not rematch_voted and not sess.rematch_declined:
                            rematch_voted = True
                            net.send({"type": "rematch_vote"})
                        elif k == pygame.K_ESCAPE:
                            net.close()
                            online_phase_ref[0] = "choose"
                            sess.state = State.ONLINE_SETUP
                    elif k == pygame.K_SPACE:
                        sess.scores = [0, 0]
                        sess.reset_round()
                        sess.state = State.MATCH_INTRO

                # Timeout
                elif sess.state == State.TIMEOUT:
                    if k == pygame.K_r:
                        _start_local_round(sess)
                        draw_trigger_ref[0] = reset_draw_timer()

                # Settings
                elif sess.state == State.SETTINGS:
                    if name_editing:
                        if k == pygame.K_ESCAPE or k in (pygame.K_RETURN, pygame.K_SPACE):
                            if not sess.settings.player_name:
                                sess.settings.player_name = "PLAYER"
                            name_editing = False
                        elif k == pygame.K_BACKSPACE:
                            sess.settings.player_name = sess.settings.player_name[:-1]
                        else:
                            ch = event.unicode.upper()
                            if ch.isalnum() and len(sess.settings.player_name) < 8:
                                sess.settings.player_name += ch
                    else:
                        if k in (pygame.K_UP, pygame.K_w):
                            settings_selected = (settings_selected - 1) % 4
                            snd.play_blip()
                        elif k in (pygame.K_DOWN, pygame.K_s):
                            settings_selected = (settings_selected + 1) % 4
                            snd.play_blip()
                        elif k in (pygame.K_RETURN, pygame.K_SPACE):
                            snd.play_confirm()
                            if settings_selected == 0:
                                name_editing = True
                            elif settings_selected == 1:
                                sess.settings.sound_on = not sess.settings.sound_on
                                snd.on_sound_toggle()
                            elif settings_selected == 2:
                                sess.settings.music_on = not sess.settings.music_on
                                snd.on_music_toggle()
                            elif settings_selected == 3:
                                sess.state = State.DATA
                                name_editing = False
                        elif k == pygame.K_ESCAPE:
                            sess.state = State.MENU
                            _in_mode_select = True

                # Data screen
                elif sess.state == State.DATA:
                    if k == pygame.K_ESCAPE:
                        sess.state = State.SETTINGS

        op = online_phase_ref[0]

        # Local draw timer
        if sess.state == State.READY and sess.mode != Mode.ONLINE and not quit_confirm:
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
                local_grace_deadline = None
                sess.state = State.RESULT
                flash_val = 1.0
            elif local_grace_deadline and time.perf_counter() >= local_grace_deadline:
                local_grace_deadline = None
                sess.winner = min(sess.last_times, key=sess.last_times.get)
                sess.scores[sess.winner] += 1
                sess.state = State.RESULT
                flash_val = 1.0

        # Network polling
        if sess.mode == Mode.ONLINE or op in (
                "host_connecting", "join_connecting", "join_wait", "host_wait"):
            _poll_network(net, sess, op, join_code_buf, sess.online_code, online_phase_ref)
            if online_phase_ref[0] == op:
                online_phase_ref[0] = _online_phase_sync(net, sess, op, join_code_buf)
            op = online_phase_ref[0]



        flash_val = max(0.0, flash_val - 0.04)

        if sess.state != prev_state:
            if sess.state == State.READY:
                online_fired = False
                local_grace_deadline = None
            if sess.state == State.VICTORY:
                rematch_voted = False
                sess.rematch_declined = False
                victory_entered_at = time.perf_counter()
                if sess.mode != Mode.SOLO:
                    bell_pending_at = victory_entered_at + 1.0
                if sess.mode == Mode.ONLINE:
                    my = sess.player_idx or 0
                    if sess.scores[my] > sess.scores[1 - my]:
                        sess.online_wins += 1
            elif sess.state != State.VICTORY:
                victory_entered_at = None
            if sess.state == State.RESULT:
                result_entered_at = time.perf_counter()
            elif sess.state != State.RESULT:
                result_entered_at = None
            if sess.state == State.MATCH_INTRO:
                match_intro_until = time.perf_counter() + 3.0
                bell_pending_at = match_intro_until - 2.0
            if sess.state in (State.MENU, State.READY, State.LOBBY, State.MATCH_INTRO):
                snd.start_wind()
            elif sess.state in (State.DRAW, State.RESULT, State.TIMEOUT, State.VICTORY):
                snd.stop_wind()
            if sess.state == State.DRAW:
                snd.play_ping()
            prev_state = sess.state

        # Splash screen tick
        if not splash_done:
            splash_elapsed = time.perf_counter() - splash_start
            if splash_elapsed >= 2.0 and not splash_gun_fired:
                snd.play_gunshot()
                splash_gun_fired = True
            if splash_elapsed >= 5.0:
                splash_done = True
                snd.play_bell()
                snd.start_wind()

        # Bell on match intro text appear
        if bell_pending_at is not None and time.perf_counter() >= bell_pending_at:
            snd.play_bell()
            bell_pending_at = None

        # Match intro auto-advance after 2 seconds
        if sess.state == State.MATCH_INTRO and not quit_confirm:
            if time.perf_counter() >= match_intro_until:
                if sess.mode == Mode.ONLINE:
                    if sess.online_ready_pending:
                        sess.online_ready_pending = False
                        sess.reset_round()
                        sess.state = State.READY
                    else:
                        sess.state = State.LOBBY
                else:
                    _start_local_round(sess)
                    draw_trigger_ref[0] = reset_draw_timer()

        # Ensure result timer is set even when RESULT was re-entered mid-frame
        if sess.state == State.RESULT and result_entered_at is None:
            result_entered_at = time.perf_counter()

        # Result auto-advance (2s on final winning round, 3s otherwise)
        _final_round = sess.mode != Mode.SOLO and max(sess.scores) >= WIN_SCORE
        if sess.state == State.RESULT and result_entered_at is not None and not quit_confirm:
            _result_duration = 2.0 if _final_round else 3.0
            if time.perf_counter() - result_entered_at >= _result_duration:
                result_entered_at = None
                if sess.mode != Mode.SOLO and max(sess.scores) >= WIN_SCORE:
                    sess.state = State.VICTORY
                elif sess.mode == Mode.ONLINE:
                    if net.connected:
                        if sess.is_host:
                            net.send({"type": "rematch"})
                    else:
                        online_phase_ref[0] = "choose"
                        sess.state = State.ONLINE_SETUP
                else:
                    _start_local_round(sess)
                    draw_trigger_ref[0] = reset_draw_timer()

        # Render
        if not splash_done:
            splash_elapsed = time.perf_counter() - splash_start
            render_splash(surf, fonts, show_text=2.0 <= splash_elapsed < 3.0)
        else:
            p1l, p2l = player_labels(sess)
            cursor_on = (cursor_tick // 30) % 2 == 0
            st = sess.state
            if st == State.MENU and not _in_mode_select:
                render_menu(surf, fonts, tick, intro_fade)
            elif st == State.MENU and _in_mode_select:
                render_mode_select(surf, fonts, _mode_select_idx)
            elif st == State.ONLINE_SETUP:
                ph_disp = {"host_connecting": "host_wait",
                           "join_connecting": "join_code",
                           "join_wait": "join_code"}.get(op, op)
                render_online_setup(surf, fonts, ph_disp, join_code_buf,
                                    sess.online_error, sess.online_code, cursor_on)
            elif st == State.MATCH_INTRO:
                _now = quit_confirm_at if quit_confirm else time.perf_counter()
                _intro_label = "ENDLESS FIRE" if sess.mode == Mode.SOLO else "FIRST TO 10"
                render_match_intro(surf, fonts,
                                   show_text=match_intro_until - 2.0 <= _now < match_intro_until - 1.0,
                                   intro_label=_intro_label)
            elif st == State.LOBBY:
                render_lobby(surf, fonts, tick)
            elif st == State.READY:
                render_ready(surf, fonts, tick, sess.mode, sess.scores, p1l, p2l,
                             best_solo=sess.best_solo, settings=sess.settings,
                             online_wins=sess.online_wins)
            elif st == State.DRAW:
                render_draw(surf, fonts, tick, sess.mode, sess.scores, p1l, p2l,
                            flash_val, best_solo=sess.best_solo, settings=sess.settings,
                            prompt_char=sess.prompt_char, online_wins=sess.online_wins,
                            pressed_display=sess.pressed_display)
            elif st == State.RESULT:
                if _final_round:
                    _cd = None
                elif result_entered_at is not None:
                    _t = quit_confirm_at if quit_confirm else time.perf_counter()
                    _cd = max(1, math.ceil(3.0 - (_t - result_entered_at)))
                else:
                    _cd = 3
                render_result(surf, fonts, sess.mode, sess.winner,
                              sess.false_start_player, sess.last_times,
                              sess.scores, p1l, p2l,
                              is_online=sess.mode == Mode.ONLINE,
                              is_host=sess.is_host,
                              best_solo=sess.best_solo,
                              flash=flash_val,
                              countdown=_cd,
                              misfire_player=sess.misfire_player,
                              online_wins=sess.online_wins,
                              pressed_display=sess.pressed_display,
                              cheat_player=sess.cheat_player,
                              disconnect_label=(
                                  f"{sess.opponent_name}  DISCONNECTED"
                                  if sess.mode == Mode.ONLINE and not net.connected
                                  else None
                              ))
            elif st == State.TIMEOUT:
                render_timeout(surf, fonts)
            elif st == State.VICTORY:
                _vic_text = (victory_entered_at is not None and
                             time.perf_counter() - victory_entered_at >= 1.0)
                render_victory(surf, fonts, sess.scores, p1l, p2l,
                               is_online=sess.mode == Mode.ONLINE,
                               rematch_voted=rematch_voted,
                               opponent_declined=sess.rematch_declined,
                               show_text=_vic_text)
            elif st == State.SETTINGS:
                render_settings(surf, fonts, sess.settings, settings_selected, name_editing)
            elif st == State.DATA:
                render_data(surf, fonts, sess.best_solo, sess.online_wins,
                            time_played_total + (time.perf_counter() - session_start))

        if quit_confirm and splash_done:
            render_quit_confirm(surf, fonts, quit_selected)

        if splash_done and intro_fade < 1.6 and tick % 3 == 0:
            intro_fade = min(1.6, intro_fade + 1 / 60)  # overlay clears at 1.0, title at 1.25, help text at 1.6

        pygame.display.flip()

    write_save({
        "player_name": sess.settings.player_name,
        "sound_on":    sess.settings.sound_on,
        "music_on":    sess.settings.music_on,
        "best_solo":   sess.best_solo,
        "online_wins": sess.online_wins,
        "time_played": time_played_total + (time.perf_counter() - session_start),
    })
    net.close()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main_v2()
