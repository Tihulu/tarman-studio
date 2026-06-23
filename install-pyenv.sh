#!/usr/bin/env bash
set -euo pipefail

APP_NAME="Tarman Studio"
APP_ID="tarman-studio"
PYTHON_VERSION="${TARMAN_PYTHON_VERSION:-3.12.8}"
PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"
VENV_DIR="${TARMAN_VENV_DIR:-$HOME/.local/share/tarman-studio/venv-pyenv}"
BIN_DIR="${TARMAN_BIN_DIR:-$HOME/.local/bin}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DESKTOP_DIR="$DATA_HOME/applications"
ICON_DIR="$DATA_HOME/icons/hicolor/scalable/apps"
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ICON_SOURCE="$SOURCE_DIR/tarman/assets/tarman-studio.svg"

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33mwarning:\033[0m %s\n' "$*"; }
fail() { printf '\033[1;31merror:\033[0m %s\n' "$*" >&2; exit 1; }

install_native_deps_apt() {
  if ! command -v apt-get >/dev/null 2>&1; then
    warn "apt-get not found; skipping native dependency install."
    warn "Install Python build dependencies and Qt runtime libraries manually for your distro."
    return
  fi

  local packages=(
    build-essential curl git ca-certificates make wget xz-utils
    libssl-dev zlib1g-dev libbz2-dev libreadline-dev libsqlite3-dev
    llvm libncursesw5-dev tk-dev libxml2-dev libxmlsec1-dev
    libffi-dev liblzma-dev
    libgl1 libegl1 libopengl0 libxkbcommon-x11-0
    libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1
    libxcb-render-util0 libxcb-xinerama0 libxcb-randr0 libxcb-shape0
    libxcb-xfixes0 libxcb-sync1 libxcb-xkb1
    desktop-file-utils hicolor-icon-theme
  )

  local missing=()
  local pkg
  for pkg in "${packages[@]}"; do
    if ! apt-cache show "$pkg" >/dev/null 2>&1; then
      warn "Package not available in this apt repo, skipping: $pkg"
      continue
    fi
    if ! dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed"; then
      missing+=("$pkg")
    fi
  done

  if ((${#missing[@]})); then
    say "Installing Debian/Ubuntu native build/runtime packages with apt. Sudo may ask for your password."
    sudo apt-get update
    sudo apt-get install -y "${missing[@]}"
  else
    say "Native build/runtime packages already look installed."
  fi
}

ensure_pyenv() {
  export PYENV_ROOT
  export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"

  if command -v pyenv >/dev/null 2>&1; then
    say "Using existing pyenv: $(command -v pyenv)"
    return
  fi

  if [[ -d "$PYENV_ROOT/.git" ]]; then
    say "Using pyenv checkout at $PYENV_ROOT"
    return
  fi

  say "Installing pyenv into $PYENV_ROOT without editing your shell rc files."
  git clone --depth=1 https://github.com/pyenv/pyenv.git "$PYENV_ROOT"
}

init_pyenv_for_script() {
  export PYENV_ROOT
  export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
  if ! command -v pyenv >/dev/null 2>&1; then
    fail "pyenv is still not available after setup."
  fi
  # shellcheck disable=SC1090
  eval "$(pyenv init - bash)"
}

install_python_and_app() {
  say "Installing Python $PYTHON_VERSION with pyenv if needed."
  pyenv install -s "$PYTHON_VERSION"

  local py="$PYENV_ROOT/versions/$PYTHON_VERSION/bin/python"
  [[ -x "$py" ]] || fail "Expected Python was not found at $py"

  say "Creating isolated virtual environment: $VENV_DIR"
  rm -rf "$VENV_DIR"
  "$py" -m venv "$VENV_DIR"

  say "Installing $APP_NAME and Qt/PySide6 into the isolated environment."
  "$VENV_DIR/bin/python" -m pip install --upgrade pip wheel setuptools
  "$VENV_DIR/bin/python" -m pip install --force-reinstall "$SOURCE_DIR[gui]"

  mkdir -p "$BIN_DIR"
  ln -sf "$VENV_DIR/bin/tarman" "$BIN_DIR/tarman"
  ln -sf "$VENV_DIR/bin/tarman-gui" "$BIN_DIR/tarman-gui"
}

install_desktop_assets() {
  say "Installing desktop launcher and icon."
  mkdir -p "$DESKTOP_DIR" "$ICON_DIR"
  if [[ -f "$ICON_SOURCE" ]]; then
    cp "$ICON_SOURCE" "$ICON_DIR/$APP_ID.svg"
  else
    warn "Icon source not found: $ICON_SOURCE"
  fi

  cat > "$DESKTOP_DIR/$APP_ID.desktop" <<EOF_DESKTOP
[Desktop Entry]
Type=Application
Name=Tarman Studio
Comment=Install portable Linux tarballs
Exec=$BIN_DIR/tarman-gui
TryExec=$BIN_DIR/tarman-gui
Icon=$APP_ID
Terminal=false
Categories=Utility;Qt;
StartupNotify=true
StartupWMClass=$APP_ID
EOF_DESKTOP

  chmod 0644 "$DESKTOP_DIR/$APP_ID.desktop"

  if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
  fi
  if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q "$DATA_HOME/icons/hicolor" >/dev/null 2>&1 || true
  fi
}

post_install_check() {
  say "Running import check."
  "$VENV_DIR/bin/python" - <<'PY'
from PySide6.QtWidgets import QApplication
import tarman
print(f"Tarman Studio {tarman.__version__}: PySide6 import OK")
PY

  say "Installed."
  printf '\nCommands:\n'
  printf '  %s/tarman --version\n' "$BIN_DIR"
  printf '  %s/tarman-gui\n' "$BIN_DIR"
  printf '\nDesktop entry:\n'
  printf '  %s/%s.desktop\n' "$DESKTOP_DIR" "$APP_ID"
  printf '\nIf %s is not in PATH, add this to your shell rc file:\n' "$BIN_DIR"
  printf '  export PATH="$HOME/.local/bin:$PATH"\n'
  printf '\nFor COSMIC/GNOME/KDE dock pinning, launch Tarman Studio from the application menu once, then pin that running app.\n'
}

main() {
  say "Installing $APP_NAME with pyenv isolation."
  install_native_deps_apt
  ensure_pyenv
  init_pyenv_for_script
  install_python_and_app
  install_desktop_assets
  post_install_check
}

main "$@"
