from __future__ import annotations
"""All pygame rendering. No game logic here."""
import math
import pygame

# ── Palette ──────────────────────────────────────────────────────────────────
SKY_TOP    = (210, 100,  30)
SKY_BOT    = (240, 160,  50)
GROUND     = ( 90,  55,  20)
DIRT       = (120,  75,  30)
SUN        = (255, 230,  80)
COWBOY     = ( 20,  12,   5)
GUN        = ( 80,  60,  30)
TEXT_WARM  = (245, 220, 160)
TEXT_DIM   = (180, 140,  80)
DRAW_COL   = (255, 230,   0)
WIN_COL    = (255, 190,  40)
LOSE_COL   = (180,  40,  40)
FLASH_COL  = (255, 255, 200)
UI_BG      = ( 30,  18,   5)
INPUT_COL  = ( 60,  40,  15)
CURSOR_COL = (255, 200,  50)
CACTUS     = ( 40,  90,  20)
P1_COL     = (255,   0,   0)   # red for P1 in local
P2_COL     = (  0,   0, 255)   # blue for P2 in local

# ── Pixel scale for sprites ───────────────────────────────────────────────────
PX = 5   # screen pixels per logical pixel

# Cowboy sprite: right-facing, 9 cols × 13 rows
# 1 = body, 2 = gun/barrel, 0 = empty
_COWBOY_R = [
    [0,0,1,1,1,0,0,0,0],   #  0  hat top
    [0,1,1,1,1,1,0,0,0],   #  1  hat brim
    [0,0,1,1,1,0,0,0,0],   #  2  head
    [0,0,1,1,1,0,0,0,0],   #  3  head
    [0,1,1,1,1,1,0,0,0],   #  4  shoulders
    [0,1,1,1,1,1,2,2,2],   #  5  torso + gun
    [0,1,1,1,1,1,0,0,0],   #  6  torso
    [0,1,1,1,1,1,0,0,0],   #  7  torso
    [0,0,1,1,1,0,0,0,0],   #  8  hips
    [0,1,0,0,1,0,0,0,0],   #  9  legs
    [0,1,0,0,1,0,0,0,0],   # 10
    [0,1,0,0,1,0,0,0,0],   # 11
    [0,1,0,0,1,0,0,0,0],   # 12
]

def _mirror(grid):
    return [list(reversed(row)) for row in grid]

_COWBOY_L = _mirror(_COWBOY_R)

SPRITE_W = len(_COWBOY_R[0]) * PX
SPRITE_H = len(_COWBOY_R)    * PX


def draw_cowboy(surf: pygame.Surface, cx: int, cy: int, facing_right: bool,
                fired: bool = False):
    """Draw cowboy silhouette centred at (cx, cy)."""
    grid = _COWBOY_R if facing_right else _COWBOY_L
    phase = 0 if facing_right else 1
    bob = not fired and (pygame.time.get_ticks() // 600 + phase) % 2 == 1
    ox = cx - SPRITE_W // 2
    oy = cy - SPRITE_H // 2 - (PX if bob else 0)
    col = (80, 60, 40) if fired else COWBOY
    for ry, row in enumerate(grid):
        for rx, cell in enumerate(row):
            if cell == 0:
                continue
            c = GUN if cell == 2 else col
            pygame.draw.rect(surf, c,
                             (ox + rx * PX, oy + ry * PX, PX, PX))
    if bob:
        extra_y = oy + len(grid) * PX
        for rx, cell in enumerate(grid[-1]):
            if cell == 1:
                pygame.draw.rect(surf, col, (ox + rx * PX, extra_y, PX, PX))


def draw_cactus(surf: pygame.Surface, x: int, y: int, h: int = 60):
    """Draw a pixel cactus silhouette."""
    w = PX * 2
    pygame.draw.rect(surf, CACTUS, (x - w // 2, y - h, w, h))
    arm_y = y - h * 2 // 3
    pygame.draw.rect(surf, CACTUS, (x - w * 3, arm_y - h // 4, w * 3, w))
    pygame.draw.rect(surf, CACTUS, (x - w * 3, arm_y - h // 2, w, h // 4))
    pygame.draw.rect(surf, CACTUS, (x + w // 2, arm_y - h // 4, w * 3, w))
    pygame.draw.rect(surf, CACTUS, (x + w * 5 // 2, arm_y - h // 2, w, h // 4))


def draw_bg(surf: pygame.Surface, flash: float = 0.0):
    """Render the western background. flash: 0–1 white flash intensity."""
    W, H = surf.get_size()
    horizon = int(H * 0.62)

    # Sky gradient (two rects approximation)
    surf.fill(SKY_TOP, (0, 0, W, horizon // 2))
    surf.fill(SKY_BOT, (0, horizon // 2, W, horizon - horizon // 2))

    # Sun
    pygame.draw.circle(surf, SUN, (W // 2, horizon // 2 - 20), 28)

    # Ground
    surf.fill(GROUND, (0, horizon, W, H - horizon))
    surf.fill(DIRT, (0, horizon, W, 8))

    # Cacti (decorative)
    draw_cactus(surf, 80, horizon, 55)
    draw_cactus(surf, W - 80, horizon, 65)
    draw_cactus(surf, 180, horizon, 35)
    draw_cactus(surf, W - 170, horizon, 42)

    # Flash overlay
    if flash > 0.0:
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((255, 255, 220, int(flash * 220)))
        surf.blit(overlay, (0, 0))


def pixel_text(surf: pygame.Surface, text: str, font: pygame.font.Font,
               colour, cx: int, cy: int, shadow: bool = True):
    """Render text centred at (cx, cy) with optional drop shadow."""
    if shadow:
        s = font.render(text, False, (0, 0, 0))
        surf.blit(s, s.get_rect(center=(cx + 2, cy + 2)))
    r = font.render(text, False, colour)
    surf.blit(r, r.get_rect(center=(cx, cy)))


def pixel_text_left(surf: pygame.Surface, text: str, font: pygame.font.Font,
                    colour, x: int, y: int):
    r = font.render(text, False, colour)
    surf.blit(r, (x, y))


# ── Screen renderers ──────────────────────────────────────────────────────────

def render_splash(surf: pygame.Surface, fonts: dict, show_text: bool = False):
    """Boot splash: black screen, then 'GAME BY EV4' appears."""
    W, H = surf.get_size()
    surf.fill((0, 0, 0))
    if show_text:
        pixel_text(surf, "GAME BY EV4", fonts["med"], DRAW_COL, W // 2, H // 2)


def render_menu(surf: pygame.Surface, fonts: dict, tick: int, intro_fade: float = 1.0):
    draw_bg(surf)
    W, H = surf.get_size()

    # Title pops in after a short pause once background is fully revealed
    if intro_fade >= 1.25:
        tcol = DRAW_COL if (tick // 20) % 2 == 0 else WIN_COL
        pixel_text(surf, "SHOOTER", fonts["big"], tcol, W // 2, H // 4)

    # Help text appears ~1 s after the title and flashes arcade-style
    if intro_fade >= 1.6 and (tick // 30) % 2 == 0:
        pixel_text(surf, "[ PRESS SPACE TO START ]", fonts["med"], TEXT_DIM,
                   W // 2, H // 2 + 20)

    if intro_fade >= 1.25:
        pixel_text(surf, "v1.0", fonts["med"], TEXT_DIM, W // 2, H - 22)

    # Stepped black overlay — quantised to 8 levels for 8-bit feel
    if intro_fade < 1.0:
        raw = (1.0 - intro_fade) * 255
        stepped = min(255, round(raw / 32) * 32)
        overlay = pygame.Surface((W, H))
        overlay.set_alpha(stepped)
        overlay.fill((0, 0, 0))
        surf.blit(overlay, (0, 0))


def render_mode_select(surf: pygame.Surface, fonts: dict, selected: int):
    draw_bg(surf)
    W, H = surf.get_size()
    pixel_text(surf, "SELECT MODE", fonts["med"], DRAW_COL, W // 2, H // 5)
    options = [
        ("1  SOLO   PRACTICE", "BEAT YOUR BEST REACTION TIME"),
        ("2  LOCAL  DUEL", "SAME KEYBOARD, TWO COWBOYS"),
        ("3  ONLINE DUEL", "CONNECT WITH A FRIEND VIA CODE"),
        ("4  SETTINGS", "CONFIGURE CONTROLS, SOUND & MUSIC"),
    ]
    for i, (label, sub) in enumerate(options):
        cy = H // 3 + i * 72
        col = WIN_COL if i == selected else TEXT_WARM
        if i == selected:
            pygame.draw.rect(surf, (60, 40, 10),
                             (W // 2 - 200, cy - 22, 400, 44), border_radius=4)
        pixel_text(surf, label, fonts["med"], col, W // 2, cy)
    pixel_text(surf, "UP / DOWN  TO CHOOSE   |   SPACE  TO CONFIRM",
               fonts["hint"], TEXT_DIM, W // 2, H - 40)


def render_settings(surf: pygame.Surface, fonts: dict, settings,
                    selected: int, name_editing: bool = False):
    draw_bg(surf)
    W, H = surf.get_size()
    pixel_text(surf, "SETTINGS", fonts["med"], DRAW_COL, W // 2, H // 6)

    name_display = settings.player_name + ("|" if name_editing else "")
    items = [
        ("NAME",  name_display),
        ("SOUND", "ON" if settings.sound_on else "OFF"),
        ("MUSIC", "ON" if settings.music_on else "OFF"),
        ("DATA",  ">"),
    ]

    for i, (label, value) in enumerate(items):
        cy = H // 3 + i * 52
        col = WIN_COL if i == selected else TEXT_WARM
        if i == selected:
            pygame.draw.rect(surf, (60, 40, 10),
                             (W // 2 - 210, cy - 20, 420, 40), border_radius=4)
            if name_editing and i == 0:
                col = DRAW_COL
        pixel_text(surf, label, fonts["med"], col, W // 2 - 80, cy)
        pixel_text(surf, value, fonts["med"], col, W // 2 + 90, cy)

    hint = "TYPE NAME   |   ENTER  CONFIRM   |   ESC  CANCEL" if name_editing else \
           "UP / DOWN  SELECT   |   SPACE  CHANGE   |   ESC  BACK"
    pixel_text(surf, hint, fonts["hint"], TEXT_DIM, W // 2, H - 40)


def render_online_setup(surf: pygame.Surface, fonts: dict,
                        phase: str, join_code_buf: str,
                        error: str, code: str, cursor_on: bool):
    """phase: 'choose' | 'host_wait' | 'join_code'"""
    draw_bg(surf)
    W, H = surf.get_size()
    pixel_text(surf, "ONLINE DUEL", fonts["med"], DRAW_COL, W // 2, H // 6)

    if phase == "choose":
        pixel_text(surf, "H  HOST A ROOM", fonts["med"], TEXT_WARM, W // 2, H // 3 + 20)
        pixel_text(surf, "J  JOIN A ROOM", fonts["med"], TEXT_WARM, W // 2, H // 3 + 80)
        pixel_text(surf, "ESC   BACK", fonts["hint"], TEXT_DIM, W // 2, H - 40)

    elif phase == "host_wait":
        pixel_text(surf, "YOUR ROOM CODE", fonts["med"], TEXT_DIM, W // 2, H // 3)
        pixel_text(surf, code if code else "...", fonts["big"], DRAW_COL, W // 2, H // 3 + 60)
        pixel_text(surf, "SHARE THIS CODE WITH YOUR OPPONENT",
                   fonts["small"], TEXT_DIM, W // 2, H // 3 + 110)
        pixel_text(surf, "WAITING FOR OPPONENT...", fonts["small"], TEXT_WARM,
                   W // 2, H * 2 // 3)
        pixel_text(surf, "ESC   CANCEL", fonts["hint"], TEXT_DIM, W // 2, H - 40)

    elif phase == "join_code":
        pixel_text(surf, "ENTER ROOM CODE", fonts["med"], TEXT_DIM, W // 2, H // 3)
        pygame.draw.rect(surf, INPUT_COL, (W // 2 - 120, H // 2 - 10, 240, 48),
                         border_radius=4)
        pygame.draw.rect(surf, DRAW_COL, (W // 2 - 120, H // 2 - 10, 240, 48),
                         2, border_radius=4)
        cursor = "|" if cursor_on else ""
        pixel_text(surf, join_code_buf + cursor, fonts["big"], DRAW_COL,
                   W // 2, H // 2 + 14)
        pixel_text(surf, "SPACE  TO CONNECT   |   ESC  BACK",
                   fonts["hint"], TEXT_DIM, W // 2, H - 40)

    if error:
        pixel_text(surf, error, fonts["med"], LOSE_COL, W // 2, H * 5 // 6)


def render_lobby(surf: pygame.Surface, fonts: dict, tick: int):
    draw_bg(surf)
    W, H = surf.get_size()
    dots = "." * ((tick // 20) % 4)
    pixel_text(surf, f"WAITING FOR OPPONENT{dots}",
               fonts["med"], TEXT_WARM, W // 2, H // 2)
    pixel_text(surf, "ESC  cancel", fonts["small"], TEXT_DIM, W // 2, H - 40)


def _label_colour(online_wins: int):
    if online_wins >= 200:
        return (255,   0, 255)   # magenta at 200+
    if online_wins >= 100:
        return (  0, 255, 255)   # cyan at 100+
    if online_wins >= 50:
        return (  0, 255,   0)   # green at 50+
    return DRAW_COL              # default yellow


def _draw_pressed_key_box(surf, fonts, char, col, cx, cy):
    """Render a key indicator in the same bordered-box style as the DRAW prompt."""
    box_w, box_h = 52, 52
    bx = cx - box_w // 2
    by = cy - box_h // 2
    pygame.draw.rect(surf, (60, 40, 10), (bx, by, box_w, box_h), border_radius=5)
    pygame.draw.rect(surf, col, (bx, by, box_w, box_h), 3, border_radius=5)
    pixel_text(surf, char, fonts["score"], col, cx, cy)


def _draw_cowboy_labels(surf, fonts, mode, p1_label, p2_label, W, H,
                        online_wins=0, pressed_display=None, misfire_player=None):
    from game import Mode
    horizon = int(H * 0.62)
    ground_y = horizon + 30
    label_y = ground_y - SPRITE_H - 22
    key_y   = label_y - 40
    # P1 hat sits ~5px left of sprite centre; P2 (mirrored) sits ~5px right
    p1_x = W // 4     - 5
    p2_x = W * 3 // 4 + 5
    col = _label_colour(online_wins)

    def _key_col(player_idx):
        if misfire_player is not None and misfire_player == player_idx:
            return LOSE_COL
        return DRAW_COL

    if mode == Mode.SOLO:
        pixel_text(surf, p1_label, fonts["med"], col, p1_x, label_y)
        if pressed_display and pressed_display[0]:
            _draw_pressed_key_box(surf, fonts, pressed_display[0], _key_col(0), p1_x, key_y)
    elif mode == Mode.LOCAL:
        pixel_text(surf, "P1", fonts["med"], P1_COL, p1_x, label_y)
        pixel_text(surf, "P2", fonts["med"], P2_COL, p2_x, label_y)
    elif mode == Mode.ONLINE:
        pixel_text(surf, p1_label, fonts["med"], col, p1_x, label_y)
        pixel_text(surf, p2_label, fonts["med"], col, p2_x, label_y)
        if pressed_display:
            if pressed_display[0]:
                _draw_pressed_key_box(surf, fonts, pressed_display[0], _key_col(0), p1_x, key_y)
            if pressed_display[1]:
                _draw_pressed_key_box(surf, fonts, pressed_display[1], _key_col(1), p2_x, key_y)


def render_ready(surf: pygame.Surface, fonts: dict, tick: int,
                 mode, scores: list, p1_label: str, p2_label: str,
                 best_solo=None, settings=None, online_wins=0):
    draw_bg(surf)
    W, H = surf.get_size()
    horizon = int(H * 0.62)
    ground_y = horizon + 30

    # Cowboys in stance
    draw_cowboy(surf, W // 4,    ground_y - SPRITE_H // 2, facing_right=True)
    draw_cowboy(surf, W * 3 // 4, ground_y - SPRITE_H // 2, facing_right=False)
    _draw_cowboy_labels(surf, fonts, mode, p1_label, p2_label, W, H, online_wins)

    # Scores
    _draw_scores(surf, fonts, scores, mode, p1_label, p2_label, W, H, best_solo)

    # Tension dot animation
    n = (tick // 15) % 4
    dots = " . " * n
    pixel_text(surf, dots or "...", fonts["med"], TEXT_DIM, W // 2, H // 8)

    pixel_text(surf, "HAND ON YOUR IRON...", fonts["hint"], TEXT_DIM,
               W // 2, H - 62)
    from game import Mode as _Mode
    if mode == _Mode.LOCAL:
        _draw_key_hints(surf, fonts, mode, W, H, settings)


def render_draw(surf: pygame.Surface, fonts: dict, tick: int,
                mode, scores: list, p1_label: str, p2_label: str,
                flash: float = 0.0, best_solo=None, settings=None, prompt_char=None,
                online_wins=0, pressed_display=None):
    draw_bg(surf, flash)
    W, H = surf.get_size()
    horizon = int(H * 0.62)
    ground_y = horizon + 30

    draw_cowboy(surf, W // 4,    ground_y - SPRITE_H // 2, facing_right=True)
    draw_cowboy(surf, W * 3 // 4, ground_y - SPRITE_H // 2, facing_right=False)
    _draw_cowboy_labels(surf, fonts, mode, p1_label, p2_label, W, H, online_wins,
                        pressed_display=pressed_display)

    _draw_scores(surf, fonts, scores, mode, p1_label, p2_label, W, H, best_solo)

    # Pulsing DRAW!
    scale_offset = math.sin(tick * 0.3) * 4
    _ = scale_offset  # reserved for future surface scaling
    pixel_text(surf, "D R A W !", fonts["big"], DRAW_COL, W // 2, H // 5)

    if prompt_char is not None:
        box_w, box_h = 90, 90
        bx, by = W // 2 - box_w // 2, H // 2 - box_h // 2 - 10
        pygame.draw.rect(surf, (60, 40, 10), (bx, by, box_w, box_h), border_radius=6)
        pygame.draw.rect(surf, DRAW_COL, (bx, by, box_w, box_h), 3, border_radius=6)
        pixel_text(surf, prompt_char, fonts["big"], DRAW_COL, W // 2, by + box_h // 2)

    _draw_key_hints(surf, fonts, mode, W, H, settings, prompt_char)


def render_result(surf: pygame.Surface, fonts: dict, mode,
                  winner: int | None, false_start_player: int | None,
                  times: dict, scores: list,
                  p1_label: str, p2_label: str, is_online: bool, is_host: bool,
                  best_solo=None, flash: float = 0.0, countdown: int | None = 3,
                  misfire_player: int | None = None, online_wins=0,
                  pressed_display=None, cheat_player: int | None = None,
                  disconnect_label: str | None = None):
    draw_bg(surf, flash)
    W, H = surf.get_size()
    horizon = int(H * 0.62)
    ground_y = horizon + 30

    # Draw cowboys — loser slumps (fired flag = grey)
    from game import Mode as _Mode
    p1_fired = winner != 0
    p2_fired = winner != 1
    if mode == _Mode.SOLO and winner is None:
        p2_fired = False  # CPU wins when solo player misfires/false-starts
    draw_cowboy(surf, W // 4,    ground_y - SPRITE_H // 2, facing_right=True,  fired=p1_fired)
    draw_cowboy(surf, W * 3 // 4, ground_y - SPRITE_H // 2, facing_right=False, fired=p2_fired)
    _draw_cowboy_labels(surf, fonts, mode, p1_label, p2_label, W, H, online_wins,
                        pressed_display=pressed_display, misfire_player=misfire_player)

    _draw_scores(surf, fonts, scores, mode, p1_label, p2_label, W, H, best_solo)

    if cheat_player is not None:
        labels = [p1_label, p2_label]
        pixel_text(surf, f"{labels[cheat_player]} IS CHEATING!",
                   fonts["med"], LOSE_COL, W // 2, H // 5)
        pixel_text(surf, f"{labels[1 - cheat_player]} WINS",
                   fonts["big"], WIN_COL, W // 2, H // 5 + 60)
    elif misfire_player is not None:
        from game import Mode
        if mode == Mode.SOLO:
            pixel_text(surf, "MISFIRE!", fonts["big"], LOSE_COL, W // 2, H // 5)
            pixel_text(surf, "WRONG KEY", fonts["med"], TEXT_DIM, W // 2, H // 5 + 60)
        else:
            labels = [p1_label, p2_label]
            pixel_text(surf, f"{labels[misfire_player]} MISFIRED!",
                       fonts["med"], LOSE_COL, W // 2, H // 5)
            pixel_text(surf, f"{labels[1 - misfire_player]} WINS",
                       fonts["big"], WIN_COL, W // 2, H // 5 + 60)
    elif false_start_player is not None:
        from game import Mode
        if mode == Mode.SOLO:
            pixel_text(surf, "YOU JUMPED THE GUN!", fonts["big"], LOSE_COL, W // 2, H // 5)
        else:
            labels = [p1_label, p2_label]
            pixel_text(surf, f"{labels[false_start_player]} JUMPED THE GUN!",
                       fonts["med"], LOSE_COL, W // 2, H // 5)
            pixel_text(surf, f"{labels[1 - false_start_player]} WINS",
                       fonts["big"], WIN_COL, W // 2, H // 5 + 60)
    elif winner is not None:
        from game import Mode
        if mode == Mode.SOLO:
            ms = times.get(0)
            is_new_record = ms is not None and ms == best_solo
            if is_new_record:
                pixel_text(surf, "NEW RECORD!", fonts["big"], WIN_COL, W // 2, H // 5)
            if ms is not None:
                cy = H // 5 + (60 if is_new_record else 0)
                col = WIN_COL if is_new_record else TEXT_WARM
                pixel_text(surf, f"{int(ms)} ms", fonts["med"], col, W // 2, cy)
        else:
            labels = [p1_label, p2_label]
            pixel_text(surf, f"{labels[winner]}  WINS!", fonts["big"],
                       WIN_COL, W // 2, H // 5)
            if disconnect_label:
                pixel_text(surf, disconnect_label, fonts["med"], LOSE_COL, W // 2, H // 5 + 60)
            else:
                time_vals = list(times.values())
                show_decimal = len(time_vals) == 2 and int(time_vals[0]) == int(time_vals[1])
                for idx, ms in sorted(times.items()):
                    col = WIN_COL if idx == winner else TEXT_DIM
                    label = labels[idx]
                    cy = H // 5 + 60 + (idx * 32)
                    ms_str = f"{ms:.2f}" if show_decimal else str(int(ms))
                    pixel_text(surf, f"{label}  {ms_str} ms", fonts["med"], col, W // 2, cy)

    # Rematch prompt
    if is_online:
        if countdown is not None:
            pixel_text(surf, f"NEXT ROUND IN {countdown}...", fonts["small"], TEXT_DIM, W // 2, H - 40)
        pixel_text(surf, "ESC  quit", fonts["small"], TEXT_DIM, W // 2, H - 20)
    else:
        if countdown is not None:
            pixel_text(surf, f"NEXT ROUND IN {countdown}...", fonts["small"], TEXT_DIM, W // 2, H - 50)
        pixel_text(surf, "ESC  menu", fonts["small"], TEXT_DIM, W // 2, H - 30)


def render_quit_confirm(surf: pygame.Surface, fonts: dict, selected: int = 0):
    W, H = surf.get_size()
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 160))
    surf.blit(overlay, (0, 0))
    pw, ph = 360, 175
    px, py = W // 2 - pw // 2, H // 2 - ph // 2
    pygame.draw.rect(surf, UI_BG, (px, py, pw, ph))
    pygame.draw.rect(surf, WIN_COL, (px, py, pw, ph), 3)
    pixel_text(surf, "QUIT THIS DUEL?", fonts["med"], TEXT_WARM, W // 2, py + 30)
    options = [("1  YES", True), ("2  NO", False)]
    for i, (label, _) in enumerate(options):
        oy = py + 80 + i * 52
        col = WIN_COL if i == selected else TEXT_WARM
        if i == selected:
            pygame.draw.rect(surf, (60, 40, 10),
                             (W // 2 - 120, oy - 18, 240, 38), border_radius=4)
        pixel_text(surf, label, fonts["med"], col, W // 2, oy)


def render_match_intro(surf: pygame.Surface, fonts: dict, show_text: bool = True,
                       intro_label: str = "FIRST TO 10"):
    draw_bg(surf)
    W, H = surf.get_size()
    horizon = int(H * 0.62)
    ground_y = horizon + 30
    draw_cowboy(surf, W // 4,     ground_y - SPRITE_H // 2, facing_right=True)
    draw_cowboy(surf, W * 3 // 4, ground_y - SPRITE_H // 2, facing_right=False)
    if show_text:
        pixel_text(surf, intro_label, fonts["big"], WIN_COL, W // 2, H // 3)


def render_victory(surf: pygame.Surface, fonts: dict, scores: list,
                   p1_label: str, p2_label: str, is_online: bool = False,
                   rematch_voted: bool = False, opponent_declined: bool = False,
                   show_text: bool = True):
    draw_bg(surf)
    W, H = surf.get_size()
    winner_idx = 0 if scores[0] >= scores[1] else 1
    winner_label = p1_label if winner_idx == 0 else p2_label

    if show_text:
        pixel_text(surf, "MATCH OVER", fonts["med"], TEXT_DIM, W // 2, H // 6)
        pixel_text(surf, f"{winner_label}  WINS THE MATCH!", fonts["big"],
                   WIN_COL, W // 2, H // 3)
        pixel_text(surf, f"{p1_label}  {scores[0]}  -  {scores[1]}  {p2_label}",
                   fonts["med"], TEXT_WARM, W // 2, H // 2)

        if is_online:
            if opponent_declined:
                pixel_text(surf, "Opponent declined rematch     ESC  leave",
                           fonts["small"], TEXT_DIM, W // 2, H - 40)
            elif rematch_voted:
                pixel_text(surf, "Waiting for opponent...     ESC  leave",
                           fonts["small"], TEXT_DIM, W // 2, H - 40)
            else:
                pixel_text(surf, "SPACE  rematch     ESC  leave",
                           fonts["small"], TEXT_DIM, W // 2, H - 40)
        else:
            pixel_text(surf, "SPACE  new match     ESC  menu",
                       fonts["small"], TEXT_DIM, W // 2, H - 40)


def render_false_start_flash(surf: pygame.Surface, fonts: dict,
                              offender_label: str):
    W, H = surf.get_size()
    overlay = pygame.Surface((W, H), pygame.SRCALPHA)
    overlay.fill((180, 20, 20, 160))
    surf.blit(overlay, (0, 0))
    pixel_text(surf, "FALSE START!", fonts["big"], (255, 80, 80), W // 2, H // 2 - 30)
    pixel_text(surf, f"{offender_label} fired too early!",
               fonts["med"], TEXT_WARM, W // 2, H // 2 + 30)


def render_timeout(surf: pygame.Surface, fonts: dict):
    draw_bg(surf)
    W, H = surf.get_size()
    pixel_text(surf, "NOBODY DREW.", fonts["big"], TEXT_DIM, W // 2, H // 2 - 20)
    pixel_text(surf, "R  try again     ESC  menu",
               fonts["small"], TEXT_DIM, W // 2, H - 40)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _draw_scores(surf, fonts, scores, mode, p1_label, p2_label, W, H,
                 best_solo=None):
    from game import Mode
    if mode == Mode.SOLO:
        best_str = f"{best_solo} ms" if best_solo is not None else "--"
        pixel_text(surf, f"BEST  {best_str}",
                   fonts["score"], TEXT_DIM, W // 2, 24)
    else:
        pixel_text_left(surf, f"{p1_label}  {scores[0]}",
                        fonts["score"], TEXT_WARM, 20, 10)
        r = fonts["score"].render(f"{scores[1]}  {p2_label}", False, TEXT_WARM)
        surf.blit(r, (W - r.get_width() - 20, 10))


def _draw_key_hints(surf, fonts, mode, W, H, settings=None, prompt_char=None):
    from game import Mode
    if mode == Mode.LOCAL:
        p1_name = pygame.key.name(settings.p1_key).upper() if settings else "LEFT SHIFT"
        p2_name = pygame.key.name(settings.p2_key).upper() if settings else "RIGHT SHIFT"
        pixel_text(surf, f"[{p1_name}]  P1 FIRE          P2 FIRE  [{p2_name}]",
                   fonts["small"], TEXT_DIM, W // 2, H - 30)
    elif prompt_char is not None:
        pass
    elif mode in (Mode.SOLO, Mode.ONLINE):
        pixel_text(surf, "WATCH FOR YOUR KEY...", fonts["hint"], TEXT_DIM, W // 2, H - 30)
    else:
        solo_name = pygame.key.name(settings.solo_key).upper() if settings else "SPACE"
        pixel_text(surf, f"[{solo_name}]  FIRE",
                   fonts["hint"], TEXT_DIM, W // 2, H - 30)


def render_data(surf: pygame.Surface, fonts: dict,
                best_solo, online_wins: int, time_played: float):
    draw_bg(surf)
    W, H = surf.get_size()
    pixel_text(surf, "DATA", fonts["med"], DRAW_COL, W // 2, H // 6)

    s = int(time_played)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    time_str = f"{h}h {m:02d}m {sec:02d}s" if h > 0 else f"{m}m {sec:02d}s"

    rows = [
        ("SOLO BEST",   f"{best_solo} ms" if best_solo is not None else "--"),
        ("ONLINE WINS", str(online_wins)),
        ("TIME PLAYED", time_str),
    ]
    for i, (label, value) in enumerate(rows):
        cy = H // 3 + i * 52
        pixel_text(surf, label, fonts["med"], TEXT_DIM,  W // 2 - 80, cy)
        pixel_text(surf, value, fonts["med"], TEXT_WARM, W // 2 + 90, cy)

    pixel_text(surf, "ESC   BACK", fonts["hint"], TEXT_DIM, W // 2, H - 40)


def make_fonts() -> dict:
    """Return the font dict used by all renderers."""
    pygame.font.init()
    # Prefer a bitmap-style monospace; fall back to any mono
    candidates = ["Courier New", "Courier", "monospace"]
    name = pygame.font.match_font(" ".join(candidates)) or ""
    return {
        "big":   pygame.font.Font(name or None, 48),
        "score": pygame.font.Font(name or None, 36),
        "med":   pygame.font.Font(name or None, 28),
        "hint":  pygame.font.Font(name or None, 22),
        "small": pygame.font.Font(name or None, 18),
    }
