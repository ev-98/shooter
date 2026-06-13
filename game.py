"""Core game state — no pygame dependency."""
import json
import os
import random
import string
import time
from enum import Enum, auto

SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "save.json")

def load_save() -> dict:
    try:
        with open(SAVE_PATH) as f:
            return json.load(f)
    except Exception:
        return {}

def write_save(data: dict):
    try:
        with open(SAVE_PATH, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


class Mode(Enum):
    LOCAL = auto()
    SOLO = auto()
    ONLINE = auto()


WIN_SCORE = 10  # first to this many wins takes the match


class State(Enum):
    MENU = auto()
    ONLINE_SETUP = auto()   # host/join selection + text input
    LOBBY = auto()          # waiting for opponent online
    READY = auto()          # tension phase (waiting for DRAW)
    DRAW = auto()           # DRAW signal active
    FALSE_START = auto()    # someone jumped the gun
    RESULT = auto()         # round over, show winner
    TIMEOUT = auto()        # nobody fired in time
    SETTINGS = auto()       # settings screen
    DATA = auto()           # stats / data viewer
    VICTORY = auto()        # match over — someone reached WIN_SCORE
    MATCH_INTRO = auto()    # brief "first to N" splash before first round


class Settings:
    # pygame key constant integers (no pygame import needed here)
    # K_SPACE=32, K_LSHIFT=1073742049, K_RSHIFT=1073742053 (SDL2 values)
    def __init__(self):
        self.solo_key: int = 32          # pygame.K_SPACE
        self.p1_key:   int = 1073742049  # pygame.K_LSHIFT
        self.p2_key:   int = 1073742053  # pygame.K_RSHIFT
        self.sound_on: bool = True
        self.music_on: bool = True
        self.player_name: str = "PLAYER"


class Session:
    def __init__(self):
        self.mode: Mode = Mode.SOLO
        self.state: State = State.MENU
        self.scores = [0, 0]
        self.last_times: dict = {}      # {player_idx: reaction_ms}
        self.winner: int | None = None
        self.false_start_player: int | None = None
        self.draw_time: float | None = None
        self.best_solo: int | None = None
        self.online_code: str = ""
        self.player_idx: int | None = None   # online: which seat am I?
        self.is_host: bool = False
        self.text_input: str = ""           # reused for IP / room code entry
        self.online_error: str = ""
        self.opponent_name: str = ""
        self.settings: Settings = Settings()
        self.prompt_char: str | None = None  # random alphanumeric shown on DRAW (None = LOCAL)
        self.misfire_player: int | None = None
        self.online_wins: int = 0
        self.pressed_display: list = ["", ""]  # key shown above each player after press

    def reset_round(self):
        self.last_times = {}
        self.winner = None
        self.false_start_player = None
        self.misfire_player = None
        self.draw_time = None
        self.prompt_char = None
        self.pressed_display = ["", ""]

    def set_draw(self):
        self.draw_time = time.perf_counter()
        if self.mode == Mode.SOLO:
            self.prompt_char = random.choice(string.ascii_uppercase)
        self.state = State.DRAW

    def do_misfire(self, player_idx: int):
        """Wrong key pressed during DRAW — that player loses the round."""
        self.misfire_player = player_idx
        if self.mode != Mode.SOLO:
            self.winner = 1 - player_idx
            self.scores[self.winner] += 1

    def fire(self, player_idx: int) -> str:
        """
        Process a local fire event. Returns one of:
          'false_start' | 'ok' | 'already_fired' | 'ignored'
        """
        if self.state == State.READY:
            return "false_start"
        if self.state != State.DRAW:
            return "ignored"
        if player_idx in self.last_times:
            return "already_fired"
        ms = int((time.perf_counter() - self.draw_time) * 1000)
        self.last_times[player_idx] = ms
        return "ok"

    def resolve_local_or_wait(self, num_players: int = 2) -> bool:
        """
        Check if all players have fired. If so, set winner and return True.
        For solo: num_players=1.
        """
        if len(self.last_times) < num_players:
            return False
        self.winner = min(self.last_times, key=self.last_times.get)
        self.scores[self.winner] += 1
        if self.mode == Mode.SOLO:
            t = self.last_times[0]
            if self.best_solo is None or t < self.best_solo:
                self.best_solo = t
        return True
