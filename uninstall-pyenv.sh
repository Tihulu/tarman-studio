#!/usr/bin/env bash
set -euo pipefail

APP_ID="tarman-studio"
PYTHON_VERSION="${TARMAN_PYTHON_VERSION:-3.12.8}"
PYENV_ROOT="${PYENV_ROOT:-$HOME/.pyenv}"
VENV_DIR="${TARMAN_VENV_DIR:-$HOME/.local/share/tarman-studio/venv-pyenv}"
BIN_DIR="${TARMAN_BIN_DIR:-$HOME/.local/bin}"
DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
DESKTOP_DIR="$DATA_HOME/applications"
ICON_BASE="$DATA_HOME/icons/hicolor"
MANIFEST_DIR="$DATA_HOME/tarman/manifests"
APPS_DIR="$DATA_HOME/tarman/apps"

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }

REMOVE_PYENV_PYTHON=0
REMOVE_INSTALLED_APPS=0
for arg in "$@"; do
  case "$arg" in
    --remove-pyenv-python) REMOVE_PYENV_PYTHON=1 ;;
    --remove-installed-apps) REMOVE_INSTALLED_APPS=1 ;;
    *) printf 'Unknown option: %s\n' "$arg" >&2; exit 2 ;;
  esac
done

say "Removing Tarman Studio launchers and desktop assets."
rm -f "$BIN_DIR/tarman" "$BIN_DIR/tarman-gui"
rm -f "$DESKTOP_DIR/$APP_ID.desktop"
rm -f "$ICON_BASE/scalable/apps/$APP_ID.svg"

say "Removing isolated virtual environment."
rm -rf "$VENV_DIR"

if [[ "$REMOVE_INSTALLED_APPS" == "1" ]]; then
  say "Removing apps and manifests installed by Tarman Studio."
  rm -rf "$MANIFEST_DIR" "$APPS_DIR"
else
  say "Keeping apps installed by Tarman Studio. Pass --remove-installed-apps to remove them too."
fi

if command -v update-desktop-database >/dev/null 2>&1; then
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
  gtk-update-icon-cache -q "$ICON_BASE" >/dev/null 2>&1 || true
fi

if [[ "$REMOVE_PYENV_PYTHON" == "1" ]]; then
  export PYENV_ROOT
  export PATH="$PYENV_ROOT/bin:$PYENV_ROOT/shims:$PATH"
  if command -v pyenv >/dev/null 2>&1; then
    say "Removing pyenv Python $PYTHON_VERSION."
    pyenv uninstall -f "$PYTHON_VERSION" || true
  else
    say "pyenv command not found; skipping pyenv Python removal."
  fi
else
  say "Keeping pyenv and Python $PYTHON_VERSION. Pass --remove-pyenv-python to remove that Python build."
fi

say "Done."
