#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="Tarman Studio"
APP_ID="tarman-studio"
ARCH="${ARCH:-x86_64}"
VERSION="${TARMAN_VERSION:-$(python3 - <<PY
import re
from pathlib import Path
text = Path("$ROOT/tarman/__init__.py").read_text()
print(re.search(r'__version__ = "([^"]+)"', text).group(1))
PY
)}"

BUILD_DIR="$ROOT/build/appimage"
APPDIR="$BUILD_DIR/TarmanStudio.AppDir"
DIST_DIR="$ROOT/dist"
PYINSTALLER_WORK="$BUILD_DIR/pyinstaller"
PYINSTALLER_SPEC="$BUILD_DIR/spec"

echo "==> Building ${APP_NAME} ${VERSION} AppImage for ${ARCH}"
rm -rf "$BUILD_DIR"
mkdir -p "$APPDIR/usr/bin" \
         "$APPDIR/usr/share/applications" \
         "$APPDIR/usr/share/icons/hicolor/scalable/apps" \
         "$DIST_DIR"

python3 -m pip install --upgrade pip wheel setuptools
python3 -m pip install --upgrade pyinstaller
python3 -m pip install "$ROOT[gui]"

python3 -m PyInstaller \
  --name "$APP_ID" \
  --onedir \
  --windowed \
  --noconfirm \
  --workpath "$PYINSTALLER_WORK" \
  --specpath "$PYINSTALLER_SPEC" \
  --distpath "$BUILD_DIR/pyinstaller-dist" \
  --collect-all PySide6 \
  --collect-data tarman \
  "$ROOT/packaging/tarman_gui_entry.py"

cp -a "$BUILD_DIR/pyinstaller-dist/$APP_ID" "$APPDIR/usr/bin/$APP_ID"

cat > "$APPDIR/AppRun" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
HERE="$(dirname "$(readlink -f "$0")")"
export APPDIR="$HERE"
exec "$HERE/usr/bin/tarman-studio/tarman-studio" "$@"
EOF
chmod +x "$APPDIR/AppRun"

cp "$ROOT/assets/tarman-studio.svg" "$APPDIR/tarman-studio.svg"
cp "$ROOT/assets/tarman-studio.svg" "$APPDIR/usr/share/icons/hicolor/scalable/apps/tarman-studio.svg"
cat > "$APPDIR/tarman-studio.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Tarman Studio
Comment=Install portable Linux apps from tar archives
Exec=tarman-studio
Icon=tarman-studio
Terminal=false
Categories=Utility;System;
StartupWMClass=tarman-studio
EOF
cp "$APPDIR/tarman-studio.desktop" "$APPDIR/usr/share/applications/tarman-studio.desktop"

APPIMAGETOOL="$BUILD_DIR/appimagetool-${ARCH}.AppImage"
if [[ ! -x "$APPIMAGETOOL" ]]; then
  echo "==> Downloading appimagetool"
  curl -L --fail -o "$APPIMAGETOOL" "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-${ARCH}.AppImage"
  chmod +x "$APPIMAGETOOL"
fi

OUTPUT="$DIST_DIR/Tarman_Studio-${VERSION}-${ARCH}.AppImage"
rm -f "$OUTPUT"
echo "==> Creating AppImage: $OUTPUT"
ARCH="$ARCH" "$APPIMAGETOOL" "$APPDIR" "$OUTPUT"
chmod +x "$OUTPUT"
echo "==> Done: $OUTPUT"
