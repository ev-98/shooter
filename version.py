"""Single source of truth for the app's identity and version.

Read by the UI (title-screen version label) and by build tooling
(PyInstaller spec, CI workflow) for artifact naming and platform metadata.
Bump VERSION here before cutting a release.
"""
APP_NAME = "shooter"
VERSION  = "1.0.2"

# Public relay server, used by both the packaged client (client.py) and the
# game's own fallback (main.py) when SERVER_URL isn't set via env/.env —
# which is the case for shipped builds, since .env isn't bundled. Keeping
# one definition here avoids the two drifting out of sync with each other.
DEFAULT_RELAY_URL = "wss://164-92-79-212.nip.io"
