"""Core game state — no pygame dependency."""
import time
from enum import Enum, auto


class Mode(Enum):
    LOCAL = auto()
    SOLO = auto()
    ONLINE = auto()


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


class Settings:
    # pygame key constant integers (no pygame import needed here)
    # K_SPACE=32, K_LSHIFT=304, K_RSHIFT=303
    def __init__(self):
        self.solo_key: int = 32   # pygame.K_SPACE
        self.p1_key:   int = 304  # pygame.K_LSHIFT
        self.p2_key:   int = 303  # pygame.K_RSHIFT
        self.sound_on: bool = True
        self.music_on: bool = True


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
        self.settings: Settings = Settings()

    def reset_round(self):
        self.last_times = {}
        self.winner = None
        self.false_start_player = None
        self.draw_time = None

    def set_draw(self):
        self.draw_time = time.perf_counter()
        self.state = State.DRAW

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
