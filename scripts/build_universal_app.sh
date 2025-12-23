#!/usr/bin/env bash
set -euo pipefail

APP_NAME="GenClashFromURL"
ENTRYPOINT="gen_clash_from_url.py"
PYTHON3="${PYTHON3:-}"
PYTHON3_ARM="${PYTHON3_ARM:-}"
PYTHON3_X86="${PYTHON3_X86:-}"
MIN_TK_VERSION="${MIN_TK_VERSION:-8.6}"
BUILD_DMG="${BUILD_DMG:-1}"
DMG_NAME="${DMG_NAME:-${APP_NAME}}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

DMG_BACKGROUND="${DMG_BACKGROUND:-$ROOT_DIR/assets/dmg-background.png}"

DEFAULT_ICON="/System/Library/CoreServices/CoreTypes.bundle/Contents/Resources/GenericApplicationIcon.icns"
PROJECT_ICON="$ROOT_DIR/assets/icon.icns"
if [[ -f "$PROJECT_ICON" ]]; then
  DEFAULT_ICON="$PROJECT_ICON"
fi
ICON_PATH="${ICON_PATH:-$DEFAULT_ICON}"

is_conda_python() {
  case "$1" in
    *miniconda*|*anaconda*) return 0 ;;
    *) return 1 ;;
  esac
}

pick_python() {
  local override="$1"
  local arch="$2"
  if [[ -n "$override" ]]; then
    echo "$override"
    return 0
  fi
  if [[ -n "$PYTHON3" && -x "$PYTHON3" ]]; then
    echo "$PYTHON3"
    return 0
  fi
  local candidates=()
  if [[ "$arch" == "arm64" ]]; then
    candidates=(
      /opt/homebrew/opt/python@3.13/bin/python3.13
      /opt/homebrew/bin/python3.13
      /Library/Frameworks/Python.framework/Versions/3.13/bin/python3
    )
  else
    candidates=(
      /usr/local/opt/python@3.13/bin/python3.13
      /usr/local/bin/python3.13
      /Library/Frameworks/Python.framework/Versions/3.13/bin/python3
    )
  fi
  for candidate in "${candidates[@]}"; do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
  done
  if command -v python3.13 >/dev/null 2>&1; then
    local found
    found="$(command -v python3.13)"
    if ! is_conda_python "$found"; then
      echo "$found"
      return 0
    fi
  fi
  return 1
}

PYTHON3_ARM="$(pick_python "$PYTHON3_ARM" "arm64" || true)"
PYTHON3_X86="$(pick_python "$PYTHON3_X86" "x86_64" || true)"

if [[ -z "$PYTHON3_ARM" || ! -x "$PYTHON3_ARM" ]]; then
  echo "arm64 python3 not found (set PYTHON3_ARM or PYTHON3 to override)"
  exit 1
fi

if [[ -z "$PYTHON3_X86" || ! -x "$PYTHON3_X86" ]]; then
  echo "x86_64 python3 not found (set PYTHON3_X86 or PYTHON3 to override)"
  exit 1
fi

if ! "$PYTHON3_ARM" -m PyInstaller --version >/dev/null 2>&1; then
  echo "PyInstaller not installed for arm64. Run: python3 -m pip install pyinstaller"
  exit 1
fi

if ! "$PYTHON3_X86" -m PyInstaller --version >/dev/null 2>&1; then
  echo "PyInstaller not installed for x86_64. Run: python3 -m pip install pyinstaller"
  exit 1
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This build script is for macOS only."
  exit 1
fi

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "Universal build requires Apple Silicon to build both arm64 and x86_64."
  exit 1
fi

if ! arch -arm64 "$PYTHON3_ARM" -c 'import platform; assert platform.machine() == "arm64"' >/dev/null 2>&1; then
  echo "arm64 python3 not available. Install an arm64 Python, or set PYTHON3_ARM to one that works under: arch -arm64"
  exit 1
fi

if ! arch -x86_64 "$PYTHON3_X86" -c 'import platform; assert platform.machine() == "x86_64"' >/dev/null 2>&1; then
  echo "x86_64 python3 not available. Install a universal or x86_64 Python, or set PYTHON3_X86 to one that works under: arch -x86_64"
  exit 1
fi

check_tk_version() {
  local arch_cmd="$1"
  local arch_arg="$2"
  local py="$3"
  local label="$4"
  local tk_version
  tk_version="$("$arch_cmd" "$arch_arg" "$py" -c 'import tkinter as tk; print(tk.TkVersion)' 2>/dev/null || true)"
  if [[ -z "$tk_version" ]]; then
    echo "Unable to determine Tk version for $label ($py). Ensure tkinter is available."
    exit 1
  fi
  if [[ "$(printf '%s\n' "$MIN_TK_VERSION" "$tk_version" | sort -V | head -n 1)" != "$MIN_TK_VERSION" ]]; then
    echo "Tk $MIN_TK_VERSION+ required on macOS 26 (found $tk_version in $label)."
    echo "Install python.org or Homebrew Python (Tk 8.6) and set PYTHON3_ARM/PYTHON3_X86."
    exit 1
  fi
}

echo "Checking Tk version for arm64 Python..."
check_tk_version arch -arm64 "$PYTHON3_ARM" "arm64"

echo "Checking Tk version for x86_64 Python..."
check_tk_version arch -x86_64 "$PYTHON3_X86" "x86_64"

verify_venv_yaml_arch() {
  local arch_cmd="$1"
  local arch_arg="$2"
  local py="$3"
  local expected_arch="$4"
  local so_path
  so_path="$("$arch_cmd" "$arch_arg" "$py" -c 'import yaml; import importlib.util as u; spec = u.find_spec("yaml._yaml"); print(spec.origin if spec and spec.origin else "")' 2>/dev/null || true)"
  if [[ -z "$so_path" || ! -f "$so_path" ]]; then
    echo "PyYAML C extension not present for $expected_arch (using pure Python)."
    return 0
  fi
  if ! lipo -archs "$so_path" 2>/dev/null | grep -qx "$expected_arch"; then
    echo "PyYAML binary has wrong architecture in $so_path (expected only $expected_arch)"
    exit 1
  fi
}

echo "Verifying PyYAML architecture in arm64 Python..."
verify_venv_yaml_arch arch -arm64 "$PYTHON3_ARM" "arm64"

echo "Verifying PyYAML architecture in x86_64 Python..."
verify_venv_yaml_arch arch -x86_64 "$PYTHON3_X86" "x86_64"

ARM_DIST="dist_arm64"
X86_DIST="dist_x86_64"
UNI_DIST="dist_universal"
ARM_BUILD="build_arm64"
X86_BUILD="build_x86_64"

mkdir -p "$ARM_DIST" "$X86_DIST" "$UNI_DIST"

echo "Building arm64 app..."
arch -arm64 "$PYTHON3_ARM" -m PyInstaller \
  --noconfirm \
  --windowed \
  --name "$APP_NAME" \
  --icon "$ICON_PATH" \
  --distpath "$ARM_DIST" \
  --workpath "$ARM_BUILD" \
  "$ENTRYPOINT"

echo "Building x86_64 app..."
arch -x86_64 "$PYTHON3_X86" -m PyInstaller \
  --noconfirm \
  --windowed \
  --name "$APP_NAME" \
  --icon "$ICON_PATH" \
  --distpath "$X86_DIST" \
  --workpath "$X86_BUILD" \
  "$ENTRYPOINT"

ARM_APP="$ARM_DIST/$APP_NAME.app"
X86_APP="$X86_DIST/$APP_NAME.app"
UNI_APP="$UNI_DIST/$APP_NAME.app"
DMG_PATH="$UNI_DIST/${DMG_NAME}.dmg"

if [[ ! -d "$ARM_APP" || ! -d "$X86_APP" ]]; then
  echo "Build failed: app bundle not found."
  exit 1
fi

rm -rf "$UNI_APP"
cp -R "$ARM_APP" "$UNI_APP"

is_macho() {
  file -b "$1" | grep -q "Mach-O"
}

verify_app_arch() {
  local app_path="$1"
  local expected_arch="$2"
  while IFS= read -r -d '' f; do
    if is_macho "$f"; then
      archs="$(lipo -archs "$f" 2>/dev/null || true)"
      if [[ -z "$archs" || "$archs" != "$expected_arch" ]]; then
        echo "Unexpected architecture in $f (expected only $expected_arch, got: ${archs:-unknown})"
        exit 1
      fi
    fi
  done < <(find "$app_path" -type f -print0)
}

echo "Verifying arm64 app architecture..."
verify_app_arch "$ARM_APP" "arm64"

echo "Verifying x86_64 app architecture..."
verify_app_arch "$X86_APP" "x86_64"

echo "Merging binaries into universal app..."
while IFS= read -r -d '' f; do
  rel="${f#$UNI_APP/}"
  f2="$X86_APP/$rel"
  if [[ -f "$f2" ]]; then
    if is_macho "$f" && is_macho "$f2"; then
      tmp="$(mktemp)"
      lipo -create "$f" "$f2" -output "$tmp"
      mv "$tmp" "$f"
    fi
  fi
done < <(find "$UNI_APP" -type f -print0)

if [[ "$BUILD_DMG" == "1" ]]; then
  echo "Packaging DMG..."
  rm -f "$DMG_PATH"
  STAGING_DIR="$(mktemp -d)"
  mkdir -p "$STAGING_DIR/.background"
  cp -R "$UNI_APP" "$STAGING_DIR/"
  ln -s /Applications "$STAGING_DIR/Applications"
  if [[ -f "$DMG_BACKGROUND" ]]; then
    cp "$DMG_BACKGROUND" "$STAGING_DIR/.background/background.png"
  fi

  DMG_RW="$UNI_DIST/${DMG_NAME}-rw.dmg"
  rm -f "$DMG_RW"
  hdiutil create -volname "$APP_NAME" -srcfolder "$STAGING_DIR" -ov -format UDRW "$DMG_RW" >/dev/null

  MOUNT_DIR="$(hdiutil attach -readwrite -noverify -noautoopen "$DMG_RW" | tail -n 1 | awk '{print $3}')"
  if [[ -n "$MOUNT_DIR" && -d "$MOUNT_DIR" ]]; then
    if [[ -f "$DMG_BACKGROUND" ]]; then
      if ! /usr/bin/osascript <<EOF
tell application "Finder"
  tell disk "$APP_NAME"
    open
    set theContainer to container window
    set current view of theContainer to icon view
    set toolbar visible of theContainer to false
    set statusbar visible of theContainer to false
    set the bounds of theContainer to {100, 100, 900, 600}
    set theViewOptions to icon view options of theContainer
    set arrangement of theViewOptions to not arranged
    set icon size of theViewOptions to 96
    set background picture of theViewOptions to file ".background:background.png"
    set position of item "$APP_NAME.app" of theContainer to {200, 260}
    set position of item "Applications" of theContainer to {700, 260}
    close
    open
    update without registering applications
  end tell
end tell
EOF
      then
        echo "Warning: DMG styling failed; continuing with default layout."
      fi
    fi
    hdiutil detach "$MOUNT_DIR" >/dev/null
  fi

  if ! hdiutil convert "$DMG_RW" -format UDZO -o "$DMG_PATH" >/dev/null; then
    echo "Warning: DMG convert failed; keeping read-write image at $DMG_RW"
  else
    rm -f "$DMG_RW"
  fi
  rm -rf "$STAGING_DIR"
  echo "DMG created: $DMG_PATH"
fi

echo "Done: $UNI_APP"
