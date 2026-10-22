<div align="center">

<img src="assets/logo.svg" alt="SHOOTER" width="480">

**A QUICK-DRAW DUELING GAME**

SHOOTER is a pixel-art Wild West quick-draw duel. Play solo, local two-player, or online.<br>
Free download for Windows, macOS, and Linux.

<a href="https://ev-98.github.io/shooter-site/"><img src="assets/steam_logo.svg" alt="Steam" width="240"></a><br>
<b>COMING SOON!</b>

### ⬇ Direct Download

[**WINDOWS**](https://github.com/ev-98/shooter/releases/latest/download/shooter-windows.zip) &nbsp;·&nbsp;
[**MAC**](https://github.com/ev-98/shooter/releases/latest/download/shooter-macos.zip) &nbsp;·&nbsp;
[**LINUX**](https://github.com/ev-98/shooter/releases/latest/download/shooter-linux.zip)

<a href="https://github.com/ev-98/shooter/releases/latest"><img src="https://img.shields.io/github/v/release/ev-98/shooter?label=latest%20build&color=d2641e" alt="Latest build"></a>

<sub><a href="https://ev-98.github.io/shooter-site/">Website</a> · <a href="https://ev4.life/">ev4.life</a></sub>

</div>

---

## About

Two cowboys, one street, one shot. Wait for the **DRAW!** signal, then fire before your opponent does. Fire too early or press the wrong key and you lose the round. First to 10 wins takes the match.

| Mode | How it plays |
|------|--------------|
| **Solo** | You against the clock. Press the key shown on **DRAW** as fast as you can and try to beat your best reaction time. |
| **Local** | Two players on one keyboard: Left Shift for P1, Right Shift for P2. Keys can be changed in Settings. |
| **Online** | Host or join a match with a 4-letter room code through the public relay server. |

## Install

### Play a release build

1. Download the zip for your platform from the links above.
2. Unzip it.
3. Run it:
   - **Windows:** `shooter\shooter.exe`
   - **macOS:** `shooter.app`
   - **Linux:** `shooter/shooter`

Save data goes in your per-user app data folder (`~/Library/Application Support/shooter`, `%APPDATA%\shooter`, or `~/.local/share/shooter`), so it carries over when you update.

### Run from source

**Dependencies**

- Python 3.10+ (CI builds with 3.13)
- [pygame](https://www.pygame.org/) ≥ 2.1
- [websockets](https://websockets.readthedocs.io/) ≥ 11.0
- [python-dotenv](https://pypi.org/project/python-dotenv/) ≥ 1.0
- [SteamworksPy](https://github.com/philippj/SteamworksPy) 1.6.5, installed from GitHub. Nothing happens until Steam is configured (see below).
- Build only: [PyInstaller](https://pyinstaller.org/) ≥ 6.10

```bash
git clone https://github.com/ev-98/shooter.git
cd shooter
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # optional, see Configuration
python main.py
```

**Configuration (`.env`, optional)**

| Variable | Purpose |
|----------|---------|
| `SERVER_URL` | Overrides the relay URL. Use `ws://localhost:8765` to develop against a local `python server.py`. Defaults to the production relay in `version.py`. |
| `SAVE_HMAC_KEY` | Key used to sign the save file. Defaults to a built-in key. |
| `STEAM_APP_ID` | Steamworks app id. Leave it at `0` and Steam features stay off. |

**Run your own relay server**

```bash
python server.py                  # listens on port 8765
```

**Build a standalone app**

```bash
pip install -r requirements-build.txt
pyinstaller main.spec             # → dist/shooter/ or dist/shooter.app
```

When you push a `v*` tag, CI (`.github/workflows/build.yml`) builds all three platforms, signs the Windows and macOS builds and notarizes the macOS one when the signing secrets are set, and publishes a GitHub release.

## Architecture

```
main.py ──► game.py       state machine + save data      (no pygame)
   │   ──► ui.py         all rendering                  (no game logic)
   │   ──► sounds.py     audio + procedural fallbacks
   │   ──► client.py ◄──── WebSocket ────► server.py   (relay + referee)
   │   ──► steam_integration.py   optional, no-op without Steam
   └──► paths.py / version.py     shared helpers + single source of truth
```

| Module | Responsibility |
|--------|----------------|
| `main.py` | Entry point and 60 FPS game loop. Handles input, moves `Session` between `State`s, applies network messages, and logs crashes. |
| `game.py` | Core state with no pygame dependency: the `Mode`/`State` enums, `Settings`, `Session` (scores, reaction times, round resolution), and HMAC-signed save load/write. |
| `ui.py` | Every `render_*` screen, the pixel-art cowboys and cacti, and a 4-minute day/night sky cycle. It never changes game state. |
| `sounds.py` | `SoundManager`. Loads `sounds/*.wav/.ogg/.mp3` and generates 8-bit square-wave tones for any file that's missing. Also handles music and wind fades. |
| `client.py` | `NetworkClient` runs an asyncio WebSocket loop on a background thread. The game loop talks to it through thread-safe `send()` and `poll()` queues so it never blocks. |
| `server.py` | Authoritative relay. Pairs players by room code, measures each player's RTT, and runs the draw timing. It rejects reactions faster than 80 ms after RTT compensation as cheating. Runs standalone or embedded via `start_background_server()`. |
| `steam_integration.py` | `SteamManager` wraps achievements, stats, and persona name. Every call quietly does nothing when Steam, the app id, or the native libraries are missing. |
| `paths.py` | Resolves bundled assets in both source and PyInstaller builds (`sys._MEIPASS`), plus per-OS user data directories. |
| `version.py` | `APP_NAME`, `VERSION`, and `DEFAULT_RELAY_URL`, read by the game, the PyInstaller spec, and CI. |

**Design notes**

- **Logic and rendering are separate.** `game.py` never imports pygame and `ui.py` never changes state, so the rules can be tested without a display.
- **The server decides online rounds.** Clients only report key presses. The server owns the random draw delay, timestamps, and the anti-cheat floor, so a modified client can't fake a faster draw.
- **One-directory builds.** `main.spec` produces an unpacked build instead of a single self-extracting exe. It launches faster, and it's the layout Steam's SteamPipe expects.

## Steam

Steam support is wired up but turned off. To turn it on, follow the steps in the docstring at the top of `steam_integration.py`. The Steamworks SDK libraries aren't committed because Valve's license doesn't allow redistributing them in a public repo.
