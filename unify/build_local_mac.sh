#!/bin/bash
# Build Unify Slicer locally on an Apple silicon Mac.
# Run in Terminal:  bash <(curl -fsSL https://raw.githubusercontent.com/MagpulX720/unify-slicer/main/unify/build_local_mac.sh)
# Everything goes in ~/unify-build. Progress is logged to ~/unify-build/build.log.
# Safe to re-run: finished steps (dependencies) are skipped.
set -eo pipefail

WORK="$HOME/unify-build"
SRC="$WORK/src"
LOG="$WORK/build.log"
ARCH="$(uname -m)"
mkdir -p "$WORK"
exec > >(tee -a "$LOG") 2>&1
step() { echo; echo "===== [$(date '+%H:%M:%S')] $* ====="; }

step "Unify Slicer local build ($ARCH)"

# Keep the Mac awake until this script ends.
caffeinate -dimsu -w $$ &

step "Xcode"
if [ ! -d /Applications/Xcode.app ]; then
  echo "Xcode.app not found in /Applications. Install it from the App Store, open it once, then re-run."; exit 1
fi
if [ "$(xcode-select -p)" != "/Applications/Xcode.app/Contents/Developer" ]; then
  echo "Pointing command-line tools at Xcode (asks for your Mac password)..."
  sudo xcode-select -s /Applications/Xcode.app
fi
if ! xcodebuild -checkFirstLaunchStatus >/dev/null 2>&1; then
  echo "Accepting Xcode licence / finishing first-launch setup (asks for your Mac password)..."
  sudo xcodebuild -license accept
  sudo xcodebuild -runFirstLaunch
fi
xcodebuild -version

step "Homebrew and build tools"
if ! command -v brew >/dev/null 2>&1; then
  if [ -x /opt/homebrew/bin/brew ]; then eval "$(/opt/homebrew/bin/brew shellenv)"
  else
    echo "Installing Homebrew (asks for your Mac password)..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)"
  fi
fi
brew install git git-lfs automake texinfo libtool gettext pkgconf || true
git lfs install >/dev/null 2>&1 || true

# The bundled libraries need CMake 3.x (CMake 4 refuses them) -> private copy in a venv.
if [ ! -x "$WORK/venv/bin/cmake" ]; then
  python3 -m venv "$WORK/venv"
  "$WORK/venv/bin/pip" install --upgrade pip >/dev/null
  "$WORK/venv/bin/pip" install "cmake~=3.28.0" ninja
fi
export PATH="$WORK/venv/bin:$PATH"
cmake --version | head -1

step "Get Unify Slicer source"
if [ ! -d "$SRC/.git" ]; then
  git clone --recursive https://github.com/MagpulX720/unify-slicer.git "$SRC"
else
  git -C "$SRC" checkout -- . 2>/dev/null || true
  git -C "$SRC" pull --ff-only
  git -C "$SRC" submodule update --init --recursive
fi
cd "$SRC"
git submodule update --init --remote submodules/Profiles
git -C submodules/Profiles log -1 --format='Snapmaker profiles: %h %cd'
python3 unify/apply_unify.py

step "Build dependencies (first time only, ~45-90 min)"
if [ -f "$WORK/.deps_done" ] && [ -d "deps/build/$ARCH/OrcaSlicer_dep" ]; then
  echo "Already built, skipping."
else
  ZSTD_WAS=0; brew list zstd >/dev/null 2>&1 && ZSTD_WAS=1 && brew unlink zstd || true
  ./build_release_macos.sh -dx -a "$ARCH" -t 11.3
  [ "$ZSTD_WAS" = 1 ] && brew link zstd || true
  touch "$WORK/.deps_done"
fi

step "Build Unify Slicer (~15-30 min)"
./build_release_macos.sh -s -n -x -a "$ARCH" -t 11.3

step "Install to /Applications"
APP_SRC="build/$ARCH/Snapmaker_Orca/Snapmaker Orca.app"
test -d "$APP_SRC"
rm -rf "/Applications/Unify Slicer.app"
cp -R "$APP_SRC" "/Applications/Unify Slicer.app"
PL="/Applications/Unify Slicer.app/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleName Unify Slicer" "$PL" || true
/usr/libexec/PlistBuddy -c "Set :CFBundleDisplayName Unify Slicer" "$PL" 2>/dev/null || /usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string Unify Slicer" "$PL"
/usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier local.unify.slicer" "$PL"
codesign --force --deep --sign - "/Applications/Unify Slicer.app"
xattr -dr com.apple.quarantine "/Applications/Unify Slicer.app" 2>/dev/null || true

step "DONE - Unify Slicer is in your Applications folder"
echo "UNIFY_BUILD_SUCCESS"
