#!/usr/bin/env bash
set -euo pipefail

REPO="${TARMAN_REPO:-Tihulu/tarman-studio}"
MODE="${TARMAN_INSTALL_MODE:-auto}" # auto, appimage, pyenv
BIN_DIR="${HOME}/.local/bin"
APP_DIR="${HOME}/.local/share/tarman-studio"
APPIMAGE_PATH="$APP_DIR/Tarman_Studio.AppImage"
DESKTOP_DIR="${HOME}/.local/share/applications"
ICON_DIR="${HOME}/.local/share/icons/hicolor/scalable/apps"

say() { printf '==> %s\n' "$*"; }
warn() { printf 'warning: %s\n' "$*" >&2; }
need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing required command: $1" >&2; exit 1; }; }

latest_appimage_url() {
  curl -fsSL "https://api.github.com/repos/${REPO}/releases/latest" \
    | grep -E '"browser_download_url": ".*\.AppImage"' \
    | sed -E 's/.*"browser_download_url": "([^"]+)".*/\1/' \
    | head -n 1
}

install_desktop_entry_for_appimage() {
  mkdir -p "$BIN_DIR" "$APP_DIR" "$DESKTOP_DIR" "$ICON_DIR"
  ln -sf "$APPIMAGE_PATH" "$BIN_DIR/tarman-gui"
  curl -fsSL "https://raw.githubusercontent.com/${REPO}/main/assets/tarman-studio.svg" -o "$ICON_DIR/tarman-studio.svg" || true
  cat > "$DESKTOP_DIR/tarman-studio.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Tarman Studio
Comment=Install portable Linux apps from tar archives
Exec=${APPIMAGE_PATH}
Icon=tarman-studio
Terminal=false
Categories=Utility;System;
StartupWMClass=tarman-studio
EOF
  chmod +x "$DESKTOP_DIR/tarman-studio.desktop" 2>/dev/null || true
  update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true
  gtk-update-icon-cache "${HOME}/.local/share/icons/hicolor" >/dev/null 2>&1 || true
}

install_appimage() {
  need curl
  local url=""
  url="$(latest_appimage_url || true)"
  if [[ -z "$url" ]]; then
    return 42
  fi
  say "Installing latest AppImage from ${REPO}"
  mkdir -p "$APP_DIR" "$BIN_DIR"
  curl -L --fail -o "$APPIMAGE_PATH" "$url"
  chmod +x "$APPIMAGE_PATH"
  install_desktop_entry_for_appimage
  say "Installed: $APPIMAGE_PATH"
  say "Run: tarman-gui"
}

install_pyenv_source() {
  need curl
  need tar
  local tmp
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT
  say "Installing from source with pyenv isolation"
  curl -L --fail "https://github.com/${REPO}/archive/refs/heads/main.tar.gz" | tar -xz -C "$tmp"
  cd "$tmp"/*
  ./install-pyenv.sh
}

case "$MODE" in
  appimage)
    install_appimage
    ;;
  pyenv)
    install_pyenv_source
    ;;
  auto)
    if install_appimage; then
      exit 0
    fi
    warn "No AppImage release found yet; falling back to pyenv source install."
    install_pyenv_source
    ;;
  *)
    echo "Unknown TARMAN_INSTALL_MODE=$MODE. Use auto, appimage, or pyenv." >&2
    exit 2
    ;;
esac
