#!/usr/bin/env bash
# Upload a GitHub release of shooter to Steam through SteamPipe.
#
#   steam/upload.sh <steam_builder_username> [tag]
#
# Downloads the three release zips for <tag> (default: latest release), lays
# them out one folder per depot, fetches steamcmd if needed, and runs the app
# build. Nothing is set live: pick the build in Steamworks → SteamPipe → Builds.
#
# Run this in your own terminal: steamcmd asks for the password and the
# Steam Guard code interactively the first time.
#
# Env overrides: DEPOT_WIN / DEPOT_MAC / DEPOT_LINUX if your depot ids differ,
# DRY_RUN=1 to stage everything and stop before uploading.
set -euo pipefail

APP_ID=5606100
DEPOT_WIN=${DEPOT_WIN:-5606101}
DEPOT_MAC=${DEPOT_MAC:-5606102}
DEPOT_LINUX=${DEPOT_LINUX:-5606103}
REPO=ev-98/shooter

STEAM_USER=${1:?usage: steam/upload.sh <steam_builder_username> [tag]}
TAG=${2:-$(curl -fsSL "https://api.github.com/repos/$REPO/releases/latest" \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')}

HERE=$(cd "$(dirname "$0")" && pwd)
WORK="$HERE/build"
CONTENT="$WORK/content"
TOOLS="$WORK/steamcmd"

echo "==> Preparing $TAG for app $APP_ID (depots win=$DEPOT_WIN mac=$DEPOT_MAC linux=$DEPOT_LINUX)"
rm -rf "$CONTENT" "$WORK/zips" "$WORK/linux_tmp"
mkdir -p "$CONTENT/windows" "$CONTENT/macos" "$CONTENT/linux" "$WORK/zips" "$WORK/output"

for p in windows macos linux; do
    echo "==> Downloading shooter-$p.zip"
    curl -fL --progress-bar -o "$WORK/zips/shooter-$p.zip" \
        "https://github.com/$REPO/releases/download/$TAG/shooter-$p.zip"
done

# Windows zip root is shooter.exe + _internal/; macOS root is shooter.app;
# Linux wraps everything in shooter/, which we flatten so all three depots
# match the launch options (shooter.exe / shooter.app / shooter).
unzip -q "$WORK/zips/shooter-windows.zip" -d "$CONTENT/windows"
unzip -q "$WORK/zips/shooter-macos.zip"   -d "$CONTENT/macos"
unzip -q "$WORK/zips/shooter-linux.zip"   -d "$WORK/linux_tmp"
mv "$WORK/linux_tmp/shooter/"* "$CONTENT/linux/"
rm -rf "$WORK/linux_tmp"

echo "==> Checking layout"
test -f "$CONTENT/windows/shooter.exe"    || { echo "missing windows/shooter.exe"; exit 1; }
test -d "$CONTENT/macos/shooter.app"      || { echo "missing macos/shooter.app"; exit 1; }
test -x "$CONTENT/linux/shooter"          || { echo "missing or non-executable linux/shooter"; exit 1; }
if codesign --verify --deep --strict "$CONTENT/macos/shooter.app" 2>/dev/null; then
    echo "    macOS signature OK"
else
    echo "    WARNING: macOS app is unsigned or its signature is broken"
fi

if [ ! -x "$TOOLS/steamcmd.sh" ]; then
    echo "==> Fetching steamcmd"
    mkdir -p "$TOOLS"
    curl -fsSL https://steamcdn-a.akamaihd.net/client/installer/steamcmd_osx.tar.gz | tar -xz -C "$TOOLS"
fi

cat > "$WORK/app_build.vdf" <<EOF
"AppBuild"
{
	"AppID" "$APP_ID"
	"Desc" "$TAG"
	"ContentRoot" "$CONTENT/"
	"BuildOutput" "$WORK/output/"
	"Depots"
	{
		"$DEPOT_WIN"   { "FileMapping" { "LocalPath" "windows/*" "DepotPath" "." "recursive" "1" } }
		"$DEPOT_MAC"   { "FileMapping" { "LocalPath" "macos/*"   "DepotPath" "." "recursive" "1" } }
		"$DEPOT_LINUX" { "FileMapping" { "LocalPath" "linux/*"   "DepotPath" "." "recursive" "1" } }
	}
}
EOF

if [ -n "${DRY_RUN:-}" ]; then
    echo "==> DRY_RUN set: staged in $CONTENT, build script at $WORK/app_build.vdf; not uploading."
    exit 0
fi

echo "==> Uploading (steamcmd may ask for your password and Steam Guard code)"
"$TOOLS/steamcmd.sh" +login "$STEAM_USER" +run_app_build "$WORK/app_build.vdf" +quit

echo "==> Done. Set the build live in Steamworks → SteamPipe → Builds."
