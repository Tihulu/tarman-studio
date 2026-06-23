# Tarman Studio

Tarman Studio is a Linux GUI + CLI helper for installing **prebuilt portable applications** distributed as `.tar`, `.tar.gz`, `.tgz`, `.tar.xz`, `.txz`, `.tar.bz2`, or `.tbz2` archives.

It is designed for people who download portable app tarballs and want a cleaner install flow than manually extracting files and creating `.desktop` launchers.

![Tarman Studio icon](assets/tarman-studio.svg)

## Highlights

- Modern English Qt/PySide6 interface.
- CLI command: `tarman`.
- GUI command: `tarman-gui`.
- pyenv-isolated install path; no conda, system Python, or `pip --user` conflicts.
- Optional AppImage build and GitHub Release workflow.
- User install target: `~/.local/share/tarman/apps/<app>`.
- Optional system install target: `/opt/<app>` using `pkexec`.
- Creates Linux app menu launchers.
- Installs a proper `tarman-studio` icon so docks can pin the app cleanly.
- Avoids running arbitrary `install.sh`, `configure`, or build scripts automatically.

## One-line install

Install with:

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/tarman-studio/main/install-online.sh | bash
```

The installer tries the latest GitHub Release AppImage first. If no AppImage release exists yet, it falls back to the pyenv/source installer.

Force AppImage mode:

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/tarman-studio/main/install-online.sh | TARMAN_INSTALL_MODE=appimage bash
```

Force pyenv/source mode, which also installs the CLI:

```bash
curl -fsSL https://raw.githubusercontent.com/Tihulu/tarman-studio/main/install-online.sh | TARMAN_INSTALL_MODE=pyenv bash
```

## Install from source

Download or clone the repository, then run:

```bash
./install-pyenv.sh
```

The installer will:

1. Install Debian/Ubuntu native build/runtime packages with `apt`.
2. Install pyenv into `~/.pyenv` if it is missing.
3. Build Python `3.12.8` with pyenv.
4. Create an isolated venv at `~/.local/share/tarman-studio/venv-pyenv`.
5. Install Tarman Studio and PySide6 into that venv.
6. Link commands into `~/.local/bin`.
7. Install `tarman-studio.desktop` and the app icon into the user data directory.

Use a different Python version:

```bash
TARMAN_PYTHON_VERSION=3.12.8 ./install-pyenv.sh
```

## Run

```bash
tarman-gui
```

or directly:

```bash
~/.local/bin/tarman-gui
```

CLI examples:

```bash
tarman --version
tarman analyze ~/Downloads/App.tar.xz
tarman install ~/Downloads/App.tar.xz
tarman install ~/Downloads/App.tar.gz --name "My App" --executable bin/myapp
tarman install ~/Downloads/App.tar.xz --scope system
tarman list
tarman uninstall "My App"
```

## Supported distros

The source/pyenv installer targets Debian-family systems with `apt-get`, including:

- Debian 12+
- Ubuntu 22.04+
- Ubuntu 24.04+
- Pop!_OS 22.04+

Other Linux distros can still run the Python package, but you must install pyenv build dependencies and Qt runtime libraries manually. The AppImage should be easier to run across distributions, but it still depends on normal Linux desktop basics such as FUSE/AppImage support.

## Dock icon and pinning

Tarman Studio installs:

- `~/.local/share/applications/tarman-studio.desktop`
- `~/.local/share/icons/hicolor/scalable/apps/tarman-studio.svg`

For COSMIC, GNOME, KDE, and similar desktops, launch **Tarman Studio** from the application menu once, then pin that running app. The Qt app sets its desktop file name to `tarman-studio`, matching the desktop entry.

## Privileged installs

When you select **System install (/opt, uses pkexec)** in the GUI, Tarman Studio first shows an **Authorization required** confirmation dialog. If you continue, the actual password prompt is handled by your desktop's Polkit/pkexec agent. Tarman Studio never reads or stores your password.

## Uninstall

Remove Tarman Studio but keep apps installed by Tarman:

```bash
./uninstall-pyenv.sh
```

Also remove apps/manifests installed by Tarman:

```bash
./uninstall-pyenv.sh --remove-installed-apps
```

Also remove the pyenv Python version used by Tarman:

```bash
./uninstall-pyenv.sh --remove-pyenv-python
```

You can combine both flags.

## Safety model

Tar archives are not a universal Linux package format. Tarman Studio only extracts archives after validating paths and link targets. It does not automatically run installer scripts or build systems.

This is intentional: a `.tar.gz` can contain anything from a prebuilt app to source code to arbitrary shell scripts.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

The Tarman Studio logo in `assets/` and `tarman/assets/` is original project artwork and is distributed under the same GPL-3.0-or-later license as the application.

## Upstream technologies and references

- pyenv: Python version isolation and installation.
- Qt for Python / PySide6: Qt 6 GUI bindings for Python.
- PyInstaller: used by the AppImage build script to bundle the GUI launcher.
- AppImageKit/appimagetool: used to generate AppImage release assets.
- Qt `desktopFileName`: used so desktop environments can associate the running window with `tarman-studio.desktop`.
- GNU GPL v3: project license.
