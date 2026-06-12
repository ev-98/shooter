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
    ox = cx - SPRITE_W // 2
    oy = cy - SPRITE_H // 2
    col = (80, 60, 40) if fired else COWBOY
    for ry, row in enumerate(grid):
        for rx, cell in enumerate(row):
            if cell == 0:
                continue
            c = GUN if cell == 2 else col
            pygame.draw.rect(surf, c,
                             (ox + rx * PX, oy + ry * PX, PX, PX))


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

def render_menu(surf: pygame.Surface, fonts: dict, tick: int):
    draw_bg(surf)
    W, H = surf.get_size()
    # Title flicker every 40 frames
    tcol = DRAW_COL if (tick // 20) % 2 == 0 else WIN_COL
    pixel_text(surf, "PY NOON", fonts["big"], tcol, W // 2, H // 4)
    pixel_text(surf, "[ PRESS ENTER TO START ]", fonts["med"], TEXT_DIM,
               W // 2, H // 2 + 20)


def render_mode_select(surf: pygame.Surface, fonts: dict, selected: int):
    draw_bg(surf)
    W, H = surf.get_size()
    pixel_text(surf, "SELECT MODE", fonts["med"], TEXT_WARM, W // 2, H // 5)
    options = [
        ("1  SOLO   PRACTICE", "beat your best reaction time"),
        ("2  LOCAL  DUEL", "same keyboard, two cowboys"),
        ("3  ONLINE DUEL", "connect with a friend via code"),
        ("4  SETTINGS", "configure controls, sound & music"),
    ]
    for i, (label, sub) in enumerate(options):
        cy = H // 3 + i * 72
        col = WIN_COL if i == selected else TEXT_WARM
        if i == selected:
            pygame.draw.rect(surf, (60, 40, 10),
                             (W // 2 - 200, cy - 22, 400, 44), border_radius=4)
        pixel_text(surf, label, fonts["med"], col, W // 2, cy)
    pixel_text(surf, "UP / DOWN  to choose   ENTER to confirm",
               fonts["small"], TEXT_DIM, W // 2, H - 40)


def render_settings(surf: pygame.Surface, fonts: dict, settings,
                    selected: int, listening: bool):
    draw_bg(surf)
    W, H = surf.get_size()
    pixel_text(surf, "SETTINGS", fonts["med"], TEXT_WARM, W // 2, H // 6)

    solo_name  = pygame.key.name(settings.solo_key).upper()
    p1_name    = pygame.key.name(settings.p1_key).upper()
    p2_name    = pygame.key.name(settings.p2_key).upper()
    items = [
        ("SOLO FIRE",  solo_name),
        ("P1 FIRE",    p1_name),
        ("P2 FIRE",    p2_name),
        ("SOUND",      "ON" if settings.sound_on else "OFF"),
        ("MUSIC",      "ON" if settings.music_on else "OFF"),
    ]

    for i, (label, value) in enumerate(items):
        cy = H // 3 + i * 52
        col = WIN_COL if i == selected else TEXT_WARM
        if i == selected:
            pygame.draw.rect(surf, (60, 40, 10),
                             (W // 2 - 210, cy - 20, 420, 40), border_radius=4)
            if listening and i < 3:
                value = "[ PRESS KEY ]"
                col = DRAW_COL
        # label left-of-centre, value right-of-centre
        pixel_text(surf, label, fonts["med"], col, W // 2 - 80, cy)
        pixel_text(surf, value, fonts["med"], col, W // 2 + 90, cy)

    hint = "ENTER to listen for key   ESC cancel" if listening else \
           "UP/DOWN select   ENTER change   ESC back"
    pixel_text(surf, hint, fonts["small"], TEXT_DIM, W // 2, H - 40)


def render_online_setup(surf: pygame.Surface, fonts: dict,
                        phase: str, text_input: str,
                        input_focus: str, error: str, code: str,
                        cursor_on: bool):
    """
    phase: 'choose' | 'host_wait' | 'join_ip' | 'join_code'
    input_focus: 'ip' | 'code'
    """
    draw_bg(surf)
    W, H = surf.get_size()
    pixel_text(surf, "ONLINE DUEL", fonts["med"], DRAW_COL, W // 2, H // 6)

    if phase == "choose":
        pixel_text(surf, "H  HOST a room", fonts["med"], TEXT_WARM, W // 2, H // 3 + 20)
        pixel_text(surf, "J  JOIN a room", fonts["med"], TEXT_WARM, W // 2, H // 3 + 80)
        pixel_text(surf, "ESC  back", fonts["small"], TEXT_DIM, W // 2, H - 40)

    elif phase == "host_wait":
        pixel_text(surf, "YOUR ROOM CODE", fonts["med"], TEXT_DIM, W // 2, H // 3)
        pixel_text(surf, code, fonts["big"], DRAW_COL, W // 2, H // 3 + 60)
        pixel_text(surf, "Share this code with your opponent",
                   fonts["small"], TEXT_DIM, W // 2, H // 3 + 110)
        pixel_text(surf, "Waiting for opponent...", fonts["small"], TEXT_WARM,
                   W // 2, H * 2 // 3)
        pixel_text(surf, "ESC  cancel", fonts["small"], TEXT_DIM, W // 2, H - 40)

    elif phase in ("join_ip", "join_code"):
        # IP field
        ip_col = DRAW_COL if input_focus == "ip" else TEXT_DIM
        pygame.draw.rect(surf, INPUT_COL, (W // 2 - 180, H // 3 - 10, 360, 40),
                         border_radius=3)
        if input_focus == "ip":
            pygame.draw.rect(surf, DRAW_COL, (W // 2 - 180, H // 3 - 10, 360, 40),
                             2, border_radius=3)
        ip_str = text_input if input_focus == "ip" else (text_input or "server IP")
        cursor = "|" if (input_focus == "ip" and cursor_on) else ""
        pixel_text(surf, ip_str + cursor, fonts["med"], ip_col,
                   W // 2, H // 3 + 10)
        pixel_text(surf, "Server IP (enter to confirm)",
                   fonts["small"], TEXT_DIM, W // 2, H // 3 - 20)

        # Code field
        code_col = DRAW_COL if input_focus == "code" else TEXT_DIM
        pygame.draw.rect(surf, INPUT_COL, (W // 2 - 100, H // 2, 200, 40),
                         border_radius=3)
        if input_focus == "code":
            pygame.draw.rect(surf, DRAW_COL, (W // 2 - 100, H // 2, 200, 40),
                             2, border_radius=3)
        code_str = text_input if input_focus == "code" else ""
        cursor2 = "|" if (input_focus == "code" and cursor_on) else ""
        pixel_text(surf, code_str + cursor2, fonts["med"], code_col,
                   W // 2, H // 2 + 20)
        pixel_text(surf, "Room code", fonts["small"], TEXT_DIM, W // 2, H // 2 - 14)

        pixel_text(surf, "TAB switch field   ENTER connect   ESC back",
                   fonts["small"], TEXT_DIM, W // 2, H - 40)

    if error:
        pixel_text(surf, error, fonts["small"], LOSE_COL, W // 2, H * 5 // 6)


def render_lobby(surf: pygame.Surface, fonts: dict, tick: int):
    draw_bg(surf)
    W, H = surf.get_size()
    dots = "." * ((tick // 20) % 4)
    pixel_text(surf, f"Waiting for opponent{dots}",
               fonts["med"], TEXT_WARM, W // 2, H // 2)
    pixel_text(surf, "ESC  cancel", fonts["small"], TEXT_DIM, W // 2, H - 40)


def render_ready(surf: pygame.Surface, fonts: dict, tick: int,
                 mode, scores: list, p1_label: str, p2_label: str,
                 best_solo=None, settings=None):
    draw_bg(surf)
    W, H = surf.get_size()
    horizon = int(H * 0.62)
    ground_y = horizon + 30

    # Cowboys in stance
    draw_cowboy(surf, W // 4,    ground_y - SPRITE_H // 2, facing_right=True)
    draw_cowboy(surf, W * 3 // 4, ground_y - SPRITE_H // 2, facing_right=False)

    # Scores
    _draw_scores(surf, fonts, scores, mode, p1_label, p2_label, W, H, best_solo)

    # Tension dot animation
    n = (tick // 15) % 4
    dots = " . " * n
    pixel_text(surf, dots or "...", fonts["med"], TEXT_DIM, W // 2, H // 8)

    pixel_text(surf, "HAND ON YOUR IRON...", fonts["small"], TEXT_DIM,
               W // 2, H - 50)
    _draw_key_hints(surf, fonts, mode, W, H, settings)


def render_draw(surf: pygame.Surface, fonts: dict, tick: int,
                mode, scores: list, p1_label: str, p2_label: str,
                flash: float = 0.0, best_solo=None, settings=None):
    draw_bg(surf, flash)
    W, H = surf.get_size()
    horizon = int(H * 0.62)
    ground_y = horizon + 30

    draw_cowboy(surf, W // 4,    ground_y - SPRITE_H // 2, facing_right=True)
    draw_cowboy(surf, W * 3 // 4, ground_y - SPRITE_H // 2, facing_right=False)

    _draw_scores(surf, fonts, scores, mode, p1_label, p2_label, W, H, best_solo)

    # Pulsing DRAW!
    scale_offset = math.sin(tick * 0.3) * 4
    _ = scale_offset  # reserved for future surface scaling
    pixel_text(surf, "D R A W !", fonts["big"], DRAW_COL, W // 2, H // 5)
    _draw_key_hints(surf, fonts, mode, W, H, settings)


def render_result(surf: pygame.Surface, fonts: dict, mode,
                  winner: int | None, false_start_player: int | None,
                  times: dict, scores: list,
                  p1_label: str, p2_label: str, is_online: bool, is_host: bool,
                  best_solo=None, flash: float = 0.0):
    draw_bg(surf, flash)
    W, H = surf.get_size()
    horizon = int(H * 0.62)
    ground_y = horizon + 30

    # Draw cowboys — loser slumps (fired flag = grey)
    p1_fired = winner != 0
    p2_fired = winner != 1
    draw_cowboy(surf, W // 4,    ground_y - SPRITE_H // 2, facing_right=True,  fired=p1_fired)
    draw_cowboy(surf, W * 3 // 4, ground_y - SPRITE_H // 2, facing_right=False, fired=p2_fired)

    _draw_scores(surf, fonts, scores, mode, p1_label, p2_label, W, H, best_solo)

    if false_start_player is not None:
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
                pixel_text(surf, f"{ms} ms", fonts["med"], col, W // 2, cy)
        else:
            labels = [p1_label, p2_label]
            pixel_text(surf, f"{labels[winner]}  WINS!", fonts["big"],
                       WIN_COL, W // 2, H // 5)
            for idx, ms in sorted(times.items()):
                col = WIN_COL if idx == winner else TEXT_DIM
                label = labels[idx]
                cy = H // 5 + 60 + (idx * 32)
                pixel_text(surf, f"{label}  {ms} ms", fonts["med"], col, W // 2, cy)

    # Rematch prompt
    if is_online:
        if is_host:
            pixel_text(surf, "R  rematch     ESC  quit",
                       fonts["small"], TEXT_DIM, W // 2, H - 40)
        else:
            pixel_text(surf, "Waiting for host...    ESC  quit",
                       fonts["small"], TEXT_DIM, W // 2, H - 40)
    else:
        pixel_text(surf, "R  play again     ESC  menu",
                   fonts["small"], TEXT_DIM, W // 2, H - 40)


def render_match_intro(surf: pygame.Surface, fonts: dict):
    draw_bg(surf)
    W, H = surf.get_size()
    pixel_text(surf, "FIRST TO 10", fonts["big"], WIN_COL, W // 2, H // 3)


def render_victory(surf: pygame.Surface, fonts: dict, scores: list,
                   p1_label: str, p2_label: str, is_online: bool = False):
    draw_bg(surf)
    W, H = surf.get_size()
    winner_idx = 0 if scores[0] >= scores[1] else 1
    winner_label = p1_label if winner_idx == 0 else p2_label

    pixel_text(surf, "MATCH OVER", fonts["med"], TEXT_DIM, W // 2, H // 6)
    pixel_text(surf, f"{winner_label}  WINS THE MATCH!", fonts["big"],
               WIN_COL, W // 2, H // 3)
    pixel_text(surf, f"{p1_label}  {scores[0]}  -  {scores[1]}  {p2_label}",
               fonts["med"], TEXT_WARM, W // 2, H // 2)

    if is_online:
        pixel_text(surf, "ESC  menu", fonts["small"], TEXT_DIM, W // 2, H - 40)
    else:
        pixel_text(surf, "R  new match     ESC  menu",
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


def _draw_key_hints(surf, fonts, mode, W, H, settings=None):
    from game import Mode
    if mode == Mode.LOCAL:
        p1_name = pygame.key.name(settings.p1_key).upper() if settings else "LEFT SHIFT"
        p2_name = pygame.key.name(settings.p2_key).upper() if settings else "RIGHT SHIFT"
        pixel_text(surf, f"[{p1_name}]  P1 FIRE          P2 FIRE  [{p2_name}]",
                   fonts["small"], TEXT_DIM, W // 2, H - 30)
    elif mode == Mode.SOLO:
        solo_name = pygame.key.name(settings.solo_key).upper() if settings else "SPACE"
        pixel_text(surf, f"[{solo_name}]  FIRE",
                   fonts["small"], TEXT_DIM, W // 2, H - 30)
    else:
        pixel_text(surf, "[SPACE]  FIRE",
                   fonts["small"], TEXT_DIM, W // 2, H - 30)


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
        "small": pygame.font.Font(name or None, 18),
    }
