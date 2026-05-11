"""Sound manager — loads from sounds/ folder, falls back to 8-bit procedural tones."""
import array
import math
import os

import pygame

_SR  = 44100
_DIR = os.path.join(os.path.dirname(__file__), "sounds")
_EXTS = (".wav", ".ogg", ".mp3")


def _find(base: str) -> str | None:
    for ext in _EXTS:
        p = os.path.join(_DIR, base + ext)
        if os.path.exists(p):
            return p
    return None


# ── Procedural 8-bit sound generators ────────────────────────────────────────

def _square(freq: float, dur: float, vol: float = 0.45) -> pygame.mixer.Sound:
    n   = int(_SR * dur)
    buf = array.array('h', [0] * (n * 2))
    amp = int(32767 * vol)
    for i in range(n):
        env = 1.0 - i / n
        v   = amp if math.sin(2 * math.pi * freq * i / _SR) >= 0 else -amp
        buf[i * 2] = buf[i * 2 + 1] = int(v * env)
    return pygame.mixer.Sound(buffer=buf)


def _make_blip() -> pygame.mixer.Sound:
    return _square(880, 0.06, 0.35)


def _make_confirm() -> pygame.mixer.Sound:
    """Two-tone blip: low note then high note."""
    dur_each = 0.05
    n        = int(_SR * dur_each)
    buf      = array.array('h', [0] * (n * 4))
    for note_i, freq in enumerate([660, 1100]):
        for i in range(n):
            env = 1.0 - i / n
            v   = int(10000 * env * (1 if math.sin(2 * math.pi * freq * i / _SR) >= 0 else -1))
            idx = (note_i * n + i) * 2
            buf[idx] = buf[idx + 1] = v
    return pygame.mixer.Sound(buffer=buf)


def _make_gunshot() -> pygame.mixer.Sound:
    """Decaying square wave — 8-bit western shot."""
    dur    = 0.22
    n      = int(_SR * dur)
    buf    = array.array('h', [0] * (n * 2))
    period = 200   # samples → ~220 Hz
    for i in range(n):
        env = (1.0 - i / n) ** 2
        v   = int(28000 * env * (1 if (i % period) < (period // 2) else -1))
        buf[i * 2] = buf[i * 2 + 1] = v
    return pygame.mixer.Sound(buffer=buf)


def _load_sfx(base: str, fallback_fn) -> pygame.mixer.Sound:
    path = _find(base)
    if path:
        return pygame.mixer.Sound(path)
    return fallback_fn()


# ── Manager ───────────────────────────────────────────────────────────────────

class SoundManager:
    def __init__(self, settings):
        self._s            = settings
        self._wind_path    = _find("wind")
        self._wind_playing = False

        self.blip    = _load_sfx("blip",    _make_blip)
        self.confirm = _load_sfx("confirm", _make_confirm)
        self.gunshot = _load_sfx("gunshot", _make_gunshot)

    # ── SFX ──────────────────────────────────────────────────────────────────

    def play_blip(self):
        if self._s.sound_on:
            self.blip.play()

    def play_confirm(self):
        if self._s.sound_on:
            self.confirm.play()

    def play_gunshot(self):
        if self._s.sound_on:
            self.gunshot.play()

    # ── Ambient music ─────────────────────────────────────────────────────────

    def start_wind(self):
        if not self._s.music_on or not self._wind_path or self._wind_playing:
            return
        pygame.mixer.music.load(self._wind_path)
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play(-1)
        self._wind_playing = True

    def stop_wind(self, fade_ms: int = 500):
        if self._wind_playing:
            pygame.mixer.music.fadeout(fade_ms)
            self._wind_playing = False

    def on_music_toggle(self):
        if self._s.music_on:
            self.start_wind()
        else:
            self.stop_wind(0)
