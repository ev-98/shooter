from __future__ import annotations
"""Steam integration — safe no-op until the pieces below exist.

Everything here degrades gracefully when Steam isn't available (no app id
configured yet, native libraries missing, or the game just isn't running
through Steam), so the rest of the codebase can call SteamManager
unconditionally without checking `available` first.

To turn this on once Steamworks access lands:
  1. Set STEAM_APP_ID in .env (or the real environment) to the assigned app id.
  2. Drop a `steam_appid.txt` (containing that same id) next to main.py —
     required for running from source; frozen builds behave the same way
     since PyInstaller's onedir layout keeps main.py's directory as cwd.
  3. Place the SteamworksPy native module (SteamworksPy64.dll / .so / .dylib,
     from https://github.com/philippj/SteamworksPy/releases) and Valve's own
     steam_api64.dll / libsteam_api.so / libsteam_api.dylib (from the
     Steamworks SDK download, partner-only) next to main.py. Neither is
     committed to this repo — Valve's SDK license doesn't allow redistributing
     them in a public repo, so .gitignore excludes them; main.spec picks them
     up automatically for the build the moment they're present.
  4. `pip install -r requirements.txt` to pull in the `steamworks` package.

Once that's done, achievement/stat API names (e.g. "ACH_WIN_ONLINE_MATCH")
still need to be created in the Steamworks dashboard and wired up at the
actual call sites in main.py/game.py — this module only provides the
plumbing (init/shutdown/callbacks + thin achievement/stat/persona helpers).
"""
import atexit
import os

STEAM_APP_ID = int(os.environ.get("STEAM_APP_ID", "0") or "0")

try:
    from steamworks import STEAMWORKS
    _STEAMWORKS_IMPORTED = True
except ImportError:
    _STEAMWORKS_IMPORTED = False


class SteamManager:
    """Thin wrapper around the Steamworks SDK.

    Every method below is a safe no-op when `available` is False, so callers
    never need to branch on whether Steam is actually present.
    """

    def __init__(self):
        self.available = False
        self._api = None

        if not _STEAMWORKS_IMPORTED or STEAM_APP_ID <= 0:
            return

        try:
            api = STEAMWORKS()
            api.initialize()
        except Exception:
            return

        self._api = api
        self.available = True
        atexit.register(self.shutdown)

    def run_callbacks(self):
        """Pump Steam callbacks. Call once per frame from the main loop."""
        if not self.available:
            return
        try:
            self._api.run_callbacks()
        except Exception:
            pass

    def persona_name(self) -> str | None:
        """The player's Steam display name, or None if unavailable."""
        if not self.available:
            return None
        try:
            return self._api.Friends.GetPlayerName()
        except Exception:
            return None

    def request_stats(self) -> bool:
        """Must succeed before reading/writing achievements or stats."""
        if not self.available:
            return False
        try:
            return bool(self._api.UserStats.RequestCurrentStats())
        except Exception:
            return False

    def unlock_achievement(self, api_name: str):
        if not self.available:
            return
        try:
            self._api.UserStats.SetAchievement(api_name)
            self._api.UserStats.StoreStats()
        except Exception:
            pass

    def has_achievement(self, api_name: str) -> bool:
        if not self.available:
            return False
        try:
            return bool(self._api.UserStats.GetAchievement(api_name))
        except Exception:
            return False

    def set_stat(self, api_name: str, value):
        if not self.available:
            return
        try:
            self._api.UserStats.SetStat(api_name, value)
            self._api.UserStats.StoreStats()
        except Exception:
            pass

    def shutdown(self):
        if self.available and self._api is not None:
            try:
                self._api.unload()
            except Exception:
                pass
            self.available = False
