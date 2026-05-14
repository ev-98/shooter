"""Sound manager — loads from sounds/ folder, falls back to 8-bit procedural tones."""
import array
import math
import os
import wave

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


def _make_ping() -> pygame.mixer.Sound:
    """Short snappy ping: sine at 1800 Hz, fast exponential decay (~80ms)."""
    freq = 1800.0
    dur  = 0.15
    n    = int(_SR * dur)
    buf  = array.array('h', [0] * (n * 2))
    for i in range(n):
        t      = i / _SR
        env    = math.exp(-t * 35.0)
        sample = int(32767 * 0.6 * env * math.sin(2 * math.pi * freq * t))
        buf[i * 2] = buf[i * 2 + 1] = max(-32767, min(32767, sample))
    return pygame.mixer.Sound(buffer=buf)


def _make_gunshot() -> pygame.mixer.Sound:
    """Two-component noise-burst gunshot matching the wav file's envelope.

    Crack layer  : raw wideband noise, peaks at ~1ms, gone by ~20ms.
    Boom layer   : ~400 Hz lowpass-filtered noise, peaks at ~20ms,
                   decays over ~500ms — replicates the measured ZCR (400-650 Hz)
                   and the two-hump envelope of the real recording.
    """
    import random
    dur = 0.655
    n   = int(_SR * dur)
    buf = array.array('h', [0] * (n * 2))
    rng = random.Random(42)

    # First-order IIR lowpass, cutoff ~400 Hz, for boom warmth
    alpha = 1 - math.exp(-2 * math.pi * 400 / _SR)
    lp = 0.0

    for i in range(n):
        t = i / _SR

        # Crack: instantaneous-onset noise, half-life ~8ms
        crack_env = math.exp(-t * 120) * min(t / 0.001, 1.0)
        crack     = rng.uniform(-1, 1) * crack_env

        # Boom: 20ms linear ramp-in, then exponential decay (~93ms half-life)
        boom_env = min(t / 0.020, 1.0) * math.exp(-t * 7.5)
        white    = rng.uniform(-1, 1)
        lp       = alpha * white + (1 - alpha) * lp
        boom     = lp * boom_env

        v = int(32000 * (0.58 * crack + 0.42 * boom))
        buf[i * 2] = buf[i * 2 + 1] = max(-32767, min(32767, v))

    return pygame.mixer.Sound(buffer=buf)


def _load_boosted(path: str, gain: float) -> pygame.mixer.Sound:
    """Load a wav file and apply a gain multiplier in-memory."""
    with wave.open(path, "rb") as w:
        raw = w.readframes(w.getnframes())
    samples = array.array('h', raw)
    for i in range(len(samples)):
        samples[i] = max(-32767, min(32767, int(samples[i] * gain)))
    return pygame.mixer.Sound(buffer=samples)


def _load_sfx(base: str, fallback_fn, gain: float = 1.0) -> pygame.mixer.Sound:
    path = _find(base)
    if path:
        return _load_boosted(path, gain) if gain != 1.0 else pygame.mixer.Sound(path)
    return fallback_fn()


# ── Manager ───────────────────────────────────────────────────────────────────

class SoundManager:
    def __init__(self, settings):
        self._s            = settings
        self._wind_path    = _find("wind")
        self._wind_playing = False

        self.blip    = _load_sfx("blip",    _make_blip)
        self.confirm = _load_sfx("confirm", _make_confirm)
        self.gunshot = _load_sfx("gunshot", _make_gunshot, gain=1.15)
        self.ping    = _load_sfx("ping",    _make_ping)

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
        self.stop_wind()

    def play_ping(self):
        if self._s.sound_on:
            self.ping.play()

    # ── Ambient music ─────────────────────────────────────────────────────────

    def start_wind(self):
        if not self._s.music_on or not self._wind_path or self._wind_playing:
            return
        pygame.mixer.music.load(self._wind_path)
        pygame.mixer.music.set_volume(0.5)
        pygame.mixer.music.play(-1)
        self._wind_playing = True

    def stop_wind(self):
        if self._wind_playing:
            pygame.mixer.music.stop()
            self._wind_playing = False

    def on_music_toggle(self):
        if self._s.music_on:
            self.start_wind()
        else:
            self.stop_wind()
