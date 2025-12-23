#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON3="${PYTHON3:-}"
PYTHON3_ARM="${PYTHON3_ARM:-}"
PYTHON3_X86="${PYTHON3_X86:-}"
AUTO_INSTALL_BREW="${AUTO_INSTALL_BREW:-1}"
PYINSTALLER_VERSION="${PYINSTALLER_VERSION:-6.11.0}"
VENV_ARM=".venv_arm64"
VENV_X86=".venv_x86"
MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-14.0}"
PYYAML_PURE="${PYYAML_PURE:-1}"
MIN_TK_VERSION="${MIN_TK_VERSION:-8.6}"

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
  if [[ -n "$PYTHON3" ]]; then
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

ensure_brew_python() {
  local arch="$1"
  local brew_path="$2"
  if [[ ! -x "$brew_path" ]]; then
    return 1
  fi
  if [[ "$AUTO_INSTALL_BREW" != "1" ]]; then
    return 1
  fi
  if [[ "$arch" == "arm64" ]]; then
    "$brew_path" install python@3.13 python-tk@3.13
  else
    arch -x86_64 "$brew_path" install python@3.13 python-tk@3.13
  fi
  return 0
}

PYTHON3_ARM="$(pick_python "$PYTHON3_ARM" "arm64" || true)"
PYTHON3_X86="$(pick_python "$PYTHON3_X86" "x86_64" || true)"

if [[ -z "$PYTHON3_ARM" && -x /opt/homebrew/bin/brew ]]; then
  ensure_brew_python "arm64" "/opt/homebrew/bin/brew" || true
  PYTHON3_ARM="$(pick_python "$PYTHON3_ARM" "arm64" || true)"
fi

if [[ -z "$PYTHON3_X86" && -x /usr/local/bin/brew ]]; then
  ensure_brew_python "x86_64" "/usr/local/bin/brew" || true
  PYTHON3_X86="$(pick_python "$PYTHON3_X86" "x86_64" || true)"
fi

if [[ -z "$PYTHON3_ARM" || ! -x "$PYTHON3_ARM" || -z "$PYTHON3_X86" || ! -x "$PYTHON3_X86" ]]; then
  echo "python3.13 not found. Install Homebrew python@3.13 for arm64 and x86_64, or set PYTHON3_ARM/PYTHON3_X86."
  echo "arm64: /opt/homebrew/bin/brew install python@3.13 python-tk@3.13"
  echo "x86_64: arch -x86_64 /usr/local/bin/brew install python@3.13 python-tk@3.13"
  exit 1
fi

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This script is for macOS only."
  exit 1
fi

if [[ "$(uname -m)" != "arm64" ]]; then
  echo "This setup requires Apple Silicon."
  exit 1
fi

check_tk_version() {
  local arch_cmd="$1"
  local arch_arg="$2"
  local py="$3"
  local brew_path="$4"
  local tk_pkg="python-tk@3.13"
  local tk_version
  tk_version="$("$arch_cmd" "$arch_arg" "$py" -c 'import tkinter as tk; print(tk.TkVersion)' 2>/dev/null || true)"
  if [[ -z "$tk_version" ]]; then
    if [[ "$AUTO_INSTALL_BREW" == "1" && -x "$brew_path" ]]; then
      if [[ "$arch_arg" == "-arm64" ]]; then
        "$brew_path" install "$tk_pkg"
      else
        arch -x86_64 "$brew_path" install "$tk_pkg"
      fi
      tk_version="$("$arch_cmd" "$arch_arg" "$py" -c 'import tkinter as tk; print(tk.TkVersion)' 2>/dev/null || true)"
    fi
  fi
  if [[ -z "$tk_version" ]]; then
    echo "Unable to determine Tk version for $arch_arg ($py). Ensure python-tk@3.13 is installed."
    exit 1
  fi
  if [[ "$(printf '%s\n' "$MIN_TK_VERSION" "$tk_version" | sort -V | head -n 1)" != "$MIN_TK_VERSION" ]]; then
    echo "Tk $MIN_TK_VERSION+ required on macOS 26 (found $tk_version in $py)."
    echo "Install python.org or Homebrew Python (Tk 8.6) and set PYTHON3."
    exit 1
  fi
}

echo "Checking Tk version for arm64 Python..."
check_tk_version arch -arm64 "$PYTHON3_ARM" "/opt/homebrew/bin/brew"

echo "Checking Tk version for x86_64 Python..."
check_tk_version arch -x86_64 "$PYTHON3_X86" "/usr/local/bin/brew"

if [[ "$PYYAML_PURE" != "1" ]]; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "Homebrew not found. Install libyaml manually or via Homebrew, or set PYYAML_PURE=1."
    exit 1
  fi

  if ! brew list --formula libyaml >/dev/null 2>&1; then
    echo "libyaml not found for arm64. Install with: brew install libyaml"
    exit 1
  fi

  LIBYAML_ARM_PREFIX="$(brew --prefix libyaml)"
  LIBYAML_ARM_INCLUDE="$LIBYAML_ARM_PREFIX/include"
  LIBYAML_ARM_LIB="$LIBYAML_ARM_PREFIX/lib"

  LIBYAML_X86_PREFIX=""
  if [[ -x /usr/local/bin/brew ]]; then
    if arch -x86_64 /usr/local/bin/brew list --formula libyaml >/dev/null 2>&1; then
      LIBYAML_X86_PREFIX="$(arch -x86_64 /usr/local/bin/brew --prefix libyaml)"
    fi
  else
    echo "Intel Homebrew not found. Installing..."
    arch -x86_64 /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
  fi

  if [[ -z "$LIBYAML_X86_PREFIX" && -f /usr/local/include/yaml.h ]]; then
    LIBYAML_X86_PREFIX="/usr/local"
  fi

  if [[ -z "$LIBYAML_X86_PREFIX" ]]; then
    echo "libyaml not found for x86_64. Install Intel Homebrew libyaml under /usr/local:"
    echo "arch -x86_64 /usr/local/bin/brew install libyaml"
    exit 1
  fi

  LIBYAML_X86_INCLUDE="$LIBYAML_X86_PREFIX/include"
  LIBYAML_X86_LIB="$LIBYAML_X86_PREFIX/lib"
fi

echo "Creating venvs..."
arch -arm64 "$PYTHON3_ARM" -m venv "$VENV_ARM"
arch -x86_64 "$PYTHON3_X86" -m venv "$VENV_X86"

echo "Installing arm64 deps..."
arch -arm64 "$VENV_ARM/bin/python3" -m pip install --upgrade pip
arch -arm64 "$VENV_ARM/bin/python3" -m pip install "pyinstaller==${PYINSTALLER_VERSION}"
arch -arm64 "$VENV_ARM/bin/python3" -m pip install -r requirements.txt
arch -arm64 "$VENV_ARM/bin/python3" -m pip uninstall -y pyyaml >/dev/null 2>&1 || true
if [[ "$PYYAML_PURE" == "1" ]]; then
  PYTHONYAML_FORCE_PURE=1 \
  arch -arm64 "$VENV_ARM/bin/python3" -m pip install --no-cache-dir pyyaml
  arch -arm64 "$VENV_ARM/bin/python3" -c 'import yaml; print(yaml.__file__)' >/dev/null
else
  ARCHFLAGS="-arch arm64" \
  MACOSX_DEPLOYMENT_TARGET="$MACOSX_DEPLOYMENT_TARGET" \
  PYYAML_FORCE_LIBYAML=1 \
  CFLAGS="-I$LIBYAML_ARM_INCLUDE" \
  LDFLAGS="-L$LIBYAML_ARM_LIB" \
  arch -arm64 "$VENV_ARM/bin/python3" -m pip install --no-cache-dir --no-binary :all: pyyaml
  arch -arm64 "$VENV_ARM/bin/python3" -c 'import yaml, yaml._yaml as y; print(y.__file__)' >/dev/null
fi

echo "Installing x86_64 deps..."
arch -x86_64 "$VENV_X86/bin/python3" -m pip install --upgrade pip
arch -x86_64 "$VENV_X86/bin/python3" -m pip install "pyinstaller==${PYINSTALLER_VERSION}"
arch -x86_64 "$VENV_X86/bin/python3" -m pip install -r requirements.txt
arch -x86_64 "$VENV_X86/bin/python3" -m pip uninstall -y pyyaml >/dev/null 2>&1 || true
if [[ "$PYYAML_PURE" == "1" ]]; then
  PYTHONYAML_FORCE_PURE=1 \
  arch -x86_64 "$VENV_X86/bin/python3" -m pip install --no-cache-dir pyyaml
  arch -x86_64 "$VENV_X86/bin/python3" -c 'import yaml; print(yaml.__file__)' >/dev/null
else
  ARCHFLAGS="-arch x86_64" \
  MACOSX_DEPLOYMENT_TARGET="$MACOSX_DEPLOYMENT_TARGET" \
  PYYAML_FORCE_LIBYAML=1 \
  CFLAGS="-I$LIBYAML_X86_INCLUDE" \
  LDFLAGS="-L$LIBYAML_X86_LIB" \
  arch -x86_64 "$VENV_X86/bin/python3" -m pip install --no-cache-dir --no-binary :all: pyyaml
  arch -x86_64 "$VENV_X86/bin/python3" -c 'import yaml, yaml._yaml as y; print(y.__file__)' >/dev/null
fi

cat <<'EOF'
Done. Build with:
PYTHON3_ARM="./.venv_arm64/bin/python3" \
PYTHON3_X86="./.venv_x86/bin/python3" \
./scripts/build_universal_app.sh
EOF
