from __future__ import annotations

import dataclasses
import fnmatch
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Iterable, Optional

SUPPORTED_SUFFIXES = (
    ".tar",
    ".tar.gz",
    ".tgz",
    ".tar.xz",
    ".txz",
    ".tar.bz2",
    ".tbz2",
)

SOURCE_MARKERS = {
    "configure",
    "CMakeLists.txt",
    "Makefile",
    "makefile",
    "meson.build",
    "setup.py",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "configure.ac",
    "autogen.sh",
}
INSTALL_SCRIPT_PATTERNS = (
    "install.sh",
    "setup.sh",
    "*.install",
    "install",
    "Installer.sh",
)
ICON_PATTERNS = (
    "*.png",
    "*.svg",
    "*.xpm",
    "*.ico",
)
EXECUTABLE_EXTENSIONS = {".sh", ".run", ".AppRun", ""}
LIBRARY_EXECUTABLE_SUFFIXES = {".so", ".a", ".o", ".dll", ".dylib"}

DEFAULT_USER_APPS_DIR = Path.home() / ".local" / "share" / "tarman" / "apps"
DEFAULT_USER_DESKTOP_DIR = Path.home() / ".local" / "share" / "applications"
DEFAULT_USER_MANIFEST_DIR = Path.home() / ".local" / "share" / "tarman" / "manifests"
DEFAULT_SYSTEM_APPS_DIR = Path("/opt")
DEFAULT_SYSTEM_DESKTOP_DIR = Path("/usr/share/applications")


class TarmanError(RuntimeError):
    """Base exception for user-facing Tarman errors."""


class UnsafeArchiveError(TarmanError):
    """Raised when an archive contains unsafe paths or links."""


@dataclasses.dataclass(frozen=True)
class ArchiveEntry:
    path: str
    size: int
    mode: int
    type: str


@dataclasses.dataclass
class ArchiveAnalysis:
    archive: Path
    app_name: str
    format: str
    entries: int
    top_level: str | None
    top_levels: list[str]
    executables: list[str]
    desktop_files: list[str]
    icons: list[str]
    install_scripts: list[str]
    source_markers: list[str]
    warnings: list[str]
    recommended_executable: str | None

    @property
    def is_source_like(self) -> bool:
        return bool(self.source_markers) and not self.executables

    def as_dict(self) -> dict:
        data = dataclasses.asdict(self)
        data["archive"] = str(self.archive)
        data["is_source_like"] = self.is_source_like
        return data


@dataclasses.dataclass
class InstallResult:
    app_name: str
    install_dir: Path
    executable: Path
    desktop_file: Path | None
    manifest: Path | None
    scope: str
    used_privilege_escalation: bool = False

    def as_dict(self) -> dict:
        return {
            "app_name": self.app_name,
            "install_dir": str(self.install_dir),
            "executable": str(self.executable),
            "desktop_file": str(self.desktop_file) if self.desktop_file else None,
            "manifest": str(self.manifest) if self.manifest else None,
            "scope": self.scope,
            "used_privilege_escalation": self.used_privilege_escalation,
        }


def strip_archive_suffix(path: Path) -> str:
    name = path.name
    for suffix in sorted(SUPPORTED_SUFFIXES, key=len, reverse=True):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def archive_format(path: Path) -> str:
    for suffix in sorted(SUPPORTED_SUFFIXES, key=len, reverse=True):
        if path.name.endswith(suffix):
            return suffix
    return path.suffix


def slugify(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9._+-]+", "-", value.strip()).strip("-._")
    return slug or "portable-app"


def titleize(value: str) -> str:
    return re.sub(r"[-_]+", " ", value).strip().title() or "Portable App"


def ensure_supported_archive(archive: Path) -> None:
    if not archive.exists():
        raise TarmanError(f"Archive not found: {archive}")
    if not archive.is_file():
        raise TarmanError(f"Not a file: {archive}")
    if not any(archive.name.endswith(suffix) for suffix in SUPPORTED_SUFFIXES):
        raise TarmanError(
            "Unsupported archive type. Supported: " + ", ".join(SUPPORTED_SUFFIXES)
        )


def open_tar(archive: Path) -> tarfile.TarFile:
    ensure_supported_archive(archive)
    try:
        return tarfile.open(archive, mode="r:*")
    except tarfile.TarError as exc:
        raise TarmanError(f"Could not open archive: {exc}") from exc


def _member_type(member: tarfile.TarInfo) -> str:
    if member.isdir():
        return "directory"
    if member.isfile():
        return "file"
    if member.issym():
        return "symlink"
    if member.islnk():
        return "hardlink"
    return "special"


def _split_components(path: str) -> list[str]:
    return [part for part in PurePosixPath(path).parts if part not in ("", ".")]


def _is_bad_path(path: str) -> bool:
    parts = _split_components(path)
    return path.startswith("/") or ".." in parts


def validate_member_safety(member: tarfile.TarInfo) -> None:
    name = member.name
    if _is_bad_path(name):
        raise UnsafeArchiveError(f"Archive contains unsafe path: {name}")
    if member.isdev():
        raise UnsafeArchiveError(f"Archive contains device file: {name}")
    if member.issym() or member.islnk():
        if not member.linkname:
            raise UnsafeArchiveError(f"Archive contains empty link target: {name}")
        if _is_bad_path(member.linkname):
            raise UnsafeArchiveError(
                f"Archive contains unsafe link target: {name} -> {member.linkname}"
            )
        # Resolve relative symlink/hardlink target within the archive tree.
        base = PurePosixPath(name).parent
        candidate = base / member.linkname
        if _is_bad_path(str(candidate)):
            raise UnsafeArchiveError(
                f"Archive link escapes extraction root: {name} -> {member.linkname}"
            )


def list_members(archive: Path) -> list[tarfile.TarInfo]:
    with open_tar(archive) as tar:
        members = tar.getmembers()
    for member in members:
        validate_member_safety(member)
    return members


def summarize_entries(members: Iterable[tarfile.TarInfo], limit: int = 5000) -> list[ArchiveEntry]:
    entries: list[ArchiveEntry] = []
    for i, member in enumerate(members):
        if i >= limit:
            break
        entries.append(
            ArchiveEntry(
                path=member.name,
                size=member.size,
                mode=member.mode,
                type=_member_type(member),
            )
        )
    return entries


def detect_top_levels(members: Iterable[tarfile.TarInfo]) -> list[str]:
    top_levels: list[str] = []
    seen: set[str] = set()
    for member in members:
        parts = _split_components(member.name)
        if not parts:
            continue
        top = parts[0]
        if top not in seen:
            top_levels.append(top)
            seen.add(top)
    return top_levels


def relative_inside_top(member_name: str, top_level: str | None) -> str:
    if top_level:
        prefix = top_level.rstrip("/") + "/"
        if member_name == top_level:
            return ""
        if member_name.startswith(prefix):
            return member_name[len(prefix) :]
    return member_name


def _basename(path: str) -> str:
    return PurePosixPath(path).name


def _has_exec_bit(mode: int) -> bool:
    return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


def detect_executables(members: Iterable[tarfile.TarInfo], top_level: str | None = None) -> list[str]:
    out: list[str] = []
    for member in members:
        if not member.isfile():
            continue
        rel = relative_inside_top(member.name, top_level)
        if not rel or rel.startswith("."):
            continue
        base = _basename(rel)
        lower = base.lower()
        suffix = Path(base).suffix.lower()
        if suffix in LIBRARY_EXECUTABLE_SUFFIXES or lower.endswith((".so", ".so.0", ".so.1")):
            continue
        if _has_exec_bit(member.mode):
            # Avoid treating plugin/shared-library files as launchers.
            out.append(rel)
        elif base == "AppRun" or suffix in {".sh", ".run"}:
            out.append(rel)
        elif lower in {"bin", "launch", "launcher"}:
            out.append(rel)
    return sorted(dict.fromkeys(out), key=_executable_rank_key)


def detect_files_by_patterns(
    members: Iterable[tarfile.TarInfo],
    patterns: Iterable[str],
    top_level: str | None = None,
    *,
    only_files: bool = True,
) -> list[str]:
    found: list[str] = []
    for member in members:
        if only_files and not member.isfile():
            continue
        rel = relative_inside_top(member.name, top_level)
        base = _basename(rel)
        for pattern in patterns:
            if fnmatch.fnmatch(base, pattern) or fnmatch.fnmatch(rel, pattern):
                found.append(rel)
                break
    return sorted(dict.fromkeys([item for item in found if item]))


def detect_source_markers(members: Iterable[tarfile.TarInfo], top_level: str | None = None) -> list[str]:
    found: list[str] = []
    for member in members:
        rel = relative_inside_top(member.name, top_level)
        base = _basename(rel)
        if base in SOURCE_MARKERS:
            found.append(rel)
    return sorted(dict.fromkeys(found))


NOISY_EXECUTABLE_PATH_PARTS = {
    "plugin", "plugins", "effect", "effects", "docs", "doc", "html", "www", "www_root",
    "resources", "samples", "examples", "example", "installdata", "data", "lib", "libs",
    "locale", "man", "share", "themes", "icons",
}


def _noisy_path_penalty(path: str) -> int:
    p = PurePosixPath(path)
    parts = [part.lower() for part in p.parts]
    name = p.name.lower()
    penalty = 0
    for part in parts[:-1]:
        if part in NOISY_EXECUTABLE_PATH_PARTS:
            penalty += 18
    if name.endswith((".html", ".txt", ".desktop", ".md")):
        penalty += 60
    if "install" in name and name not in {"install", "install.sh"}:
        penalty += 20
    return penalty


def _executable_rank_key(path: str) -> tuple[int, int, str]:
    p = PurePosixPath(path)
    name = p.name
    lower = name.lower()
    parts = [part.lower() for part in p.parts]
    rank = 50
    if name == "AppRun":
        rank = 0
    elif "bin" in parts:
        rank = 5
    elif lower.endswith(".sh"):
        rank = 25
    elif lower in {"install", "setup", "configure", "autogen.sh"}:
        rank = 90
    elif lower.endswith((".so", ".a", ".o")):
        rank = 95
    elif "." not in name:
        rank = 10
    return (rank + _noisy_path_penalty(path), len(path), path)


def choose_recommended_executable(executables: list[str], app_name: str) -> str | None:
    if not executables:
        return None
    slug = slugify(app_name).lower()
    app_words = {word for word in re.split(r"[-_ .]+", slug) if word}

    def key(path: str) -> tuple[int, int, str]:
        p = PurePosixPath(path)
        name = p.name.lower()
        parts = [part.lower() for part in p.parts]
        score = 50
        if name == "apprun":
            score = 0
        elif name == slug:
            score = 1
        elif app_words and app_words.intersection(re.split(r"[-_ .]+", name)):
            score = 2
        elif "bin" in parts and "." not in name:
            score = 5
        elif "." not in name:
            score = 10
        elif name.endswith((".sh", ".run")):
            score = 25
        if name in {"install", "setup", "configure", "autogen.sh"}:
            score = 99
        return (score + _noisy_path_penalty(path), len(path), path)

    return sorted(executables, key=key)[0]


def analyze_archive(archive: str | Path, app_name: str | None = None) -> ArchiveAnalysis:
    archive = Path(archive).expanduser().resolve()
    members = list_members(archive)
    top_levels = detect_top_levels(members)
    top_level = top_levels[0] if len(top_levels) == 1 else None
    detected_app_name = app_name or (titleize(top_level) if top_level else titleize(strip_archive_suffix(archive)))
    executables = detect_executables(members, top_level)
    desktop_files = detect_files_by_patterns(members, ["*.desktop"], top_level)
    icons = detect_files_by_patterns(members, ICON_PATTERNS, top_level)
    install_scripts = detect_files_by_patterns(members, INSTALL_SCRIPT_PATTERNS, top_level)
    source_markers = detect_source_markers(members, top_level)
    warnings: list[str] = []
    if len(top_levels) > 1:
        warnings.append(
            "Archive has multiple top-level paths; it will be extracted into a dedicated app folder."
        )
    if source_markers and not executables:
        warnings.append(
            "This looks like source code, not a prebuilt portable app. Tarman will not run build scripts automatically."
        )
    if install_scripts:
        warnings.append(
            "Install scripts were found. They are not executed automatically for safety."
        )
    if not executables:
        warnings.append(
            "No obvious executable was found. You may need to choose one manually after extraction."
        )
    return ArchiveAnalysis(
        archive=archive,
        app_name=detected_app_name,
        format=archive_format(archive),
        entries=len(members),
        top_level=top_level,
        top_levels=top_levels,
        executables=executables,
        desktop_files=desktop_files,
        icons=icons,
        install_scripts=install_scripts,
        source_markers=source_markers,
        warnings=warnings,
        recommended_executable=choose_recommended_executable(executables, detected_app_name),
    )


def _copy_fileobj(src, dst) -> None:
    shutil.copyfileobj(src, dst)


def safe_extract(archive: Path, destination: Path, strip_top_level: bool = True) -> None:
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with open_tar(archive) as tar:
        members = tar.getmembers()
        for member in members:
            validate_member_safety(member)
        top_levels = detect_top_levels(members)
        top_level = top_levels[0] if strip_top_level and len(top_levels) == 1 else None

        for member in members:
            rel = relative_inside_top(member.name, top_level)
            if not rel:
                continue
            out_path = (destination / Path(*PurePosixPath(rel).parts)).resolve()
            if not str(out_path).startswith(str(destination) + os.sep) and out_path != destination:
                raise UnsafeArchiveError(f"Extraction target escapes destination: {member.name}")
            if member.isdir():
                out_path.mkdir(parents=True, exist_ok=True)
                continue
            if member.isfile():
                out_path.parent.mkdir(parents=True, exist_ok=True)
                extracted = tar.extractfile(member)
                if extracted is None:
                    raise TarmanError(f"Could not extract file: {member.name}")
                with open(out_path, "wb") as fh:
                    _copy_fileobj(extracted, fh)
                os.chmod(out_path, member.mode & 0o777)
                continue
            if member.issym():
                out_path.parent.mkdir(parents=True, exist_ok=True)
                target = member.linkname
                try:
                    out_path.symlink_to(target)
                except FileExistsError:
                    out_path.unlink()
                    out_path.symlink_to(target)
                continue
            if member.islnk():
                target_rel = relative_inside_top(member.linkname, top_level)
                target_path = (destination / Path(*PurePosixPath(target_rel).parts)).resolve()
                if not target_path.exists():
                    # Hardlink target may appear later. Skip instead of creating unsafe links.
                    continue
                out_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(target_path, out_path)
                except FileExistsError:
                    out_path.unlink()
                    os.link(target_path, out_path)
                continue
            raise UnsafeArchiveError(f"Unsupported archive member type: {member.name}")


def find_icon(extracted_dir: Path) -> Path | None:
    candidates: list[Path] = []
    for pattern in ("*.svg", "*.png", "*.xpm", "*.ico"):
        candidates.extend(extracted_dir.rglob(pattern))
    if not candidates:
        return None

    def key(path: Path) -> tuple[int, int, str]:
        text = str(path).lower()
        rank = 50
        if "hicolor" in text or "icons" in text:
            rank = 0
        elif "logo" in text or "icon" in text:
            rank = 5
        # Prefer larger likely icons by filename/path mention.
        size_score = 0
        match = re.search(r"(\d{2,4})x\1", text)
        if match:
            size_score = -int(match.group(1))
        return (rank, size_score, str(path))

    return sorted(candidates, key=key)[0]


def create_desktop_entry(
    *,
    app_name: str,
    executable: Path,
    desktop_path: Path,
    icon: Path | None = None,
    terminal: bool = False,
) -> None:
    desktop_path.parent.mkdir(parents=True, exist_ok=True)
    exec_value = str(executable)
    icon_value = str(icon) if icon else "application-x-executable"
    entry = "\n".join(
        [
            "[Desktop Entry]",
            "Type=Application",
            f"Name={app_name}",
            f"Comment=Installed with Tarman Studio",
            f"Exec={exec_value}",
            f"Icon={icon_value}",
            f"Terminal={'true' if terminal else 'false'}",
            "Categories=Utility;",
            "StartupNotify=true",
            "",
        ]
    )
    desktop_path.write_text(entry, encoding="utf-8")
    desktop_path.chmod(0o644)


def manifest_id(app_name: str, install_dir: Path) -> str:
    raw = f"{app_name}:{install_dir}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:12]


def write_manifest(
    *,
    app_name: str,
    archive: Path,
    install_dir: Path,
    executable: Path,
    desktop_file: Path | None,
    scope: str,
) -> Path:
    DEFAULT_USER_MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
    ident = manifest_id(app_name, install_dir)
    manifest = DEFAULT_USER_MANIFEST_DIR / f"{slugify(app_name)}-{ident}.json"
    data = {
        "schema": 1,
        "app_name": app_name,
        "archive": str(archive),
        "install_dir": str(install_dir),
        "executable": str(executable),
        "desktop_file": str(desktop_file) if desktop_file else None,
        "scope": scope,
    }
    manifest.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return manifest


def list_installed() -> list[dict]:
    if not DEFAULT_USER_MANIFEST_DIR.exists():
        return []
    installed: list[dict] = []
    for path in sorted(DEFAULT_USER_MANIFEST_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            data["manifest"] = str(path)
            installed.append(data)
        except Exception:
            continue
    return installed


def _run_privileged_copy(src: Path, dst: Path) -> None:
    if not shutil.which("pkexec"):
        raise TarmanError("System install requires pkexec, but pkexec was not found.")
    # Use install -d and cp -a in a small shell script. src/dst are quoted with shlex-like repr.
    import shlex

    script = (
        f"set -e; "
        f"install -d {shlex.quote(str(dst.parent))}; "
        f"rm -rf {shlex.quote(str(dst))}; "
        f"cp -a {shlex.quote(str(src))} {shlex.quote(str(dst))}"
    )
    subprocess.run(["pkexec", "/bin/sh", "-c", script], check=True)


def _run_privileged_remove(path: Path) -> None:
    if not shutil.which("pkexec"):
        raise TarmanError("Removing a system install requires pkexec, but pkexec was not found.")
    import shlex

    script = f"rm -rf {shlex.quote(str(path))}"
    subprocess.run(["pkexec", "/bin/sh", "-c", script], check=True)


def install_archive(
    archive: str | Path,
    *,
    app_name: str | None = None,
    executable: str | None = None,
    scope: str = "user",
    destination: str | Path | None = None,
    create_desktop: bool = True,
    overwrite: bool = False,
    terminal: bool = False,
) -> InstallResult:
    archive = Path(archive).expanduser().resolve()
    analysis = analyze_archive(archive, app_name=app_name)
    name = app_name or analysis.app_name
    app_slug = slugify(name)

    if analysis.is_source_like:
        raise TarmanError(
            "This archive looks like source code. Tarman installs prebuilt portable apps only; "
            "build scripts are not executed automatically."
        )

    chosen_executable_rel = executable or analysis.recommended_executable
    if not chosen_executable_rel:
        raise TarmanError("No executable found. Pass --executable with the launcher path inside the archive.")

    if scope not in {"user", "system"}:
        raise TarmanError("scope must be 'user' or 'system'")

    used_pkexec = False
    if destination is not None:
        final_install_dir = Path(destination).expanduser().resolve()
    elif scope == "system":
        final_install_dir = DEFAULT_SYSTEM_APPS_DIR / app_slug
    else:
        final_install_dir = DEFAULT_USER_APPS_DIR / app_slug

    if final_install_dir.exists() and not overwrite:
        raise TarmanError(
            f"Install directory already exists: {final_install_dir}. Use --overwrite to replace it."
        )

    with tempfile.TemporaryDirectory(prefix="tarman-install-") as tmp:
        tmp_install_dir = Path(tmp) / app_slug
        safe_extract(archive, tmp_install_dir, strip_top_level=True)
        executable_path = (tmp_install_dir / Path(*PurePosixPath(chosen_executable_rel).parts)).resolve()
        if not str(executable_path).startswith(str(tmp_install_dir.resolve()) + os.sep):
            raise UnsafeArchiveError("Executable path escapes install directory.")
        if not executable_path.exists():
            raise TarmanError(f"Chosen executable was not found after extraction: {chosen_executable_rel}")
        current_mode = executable_path.stat().st_mode
        executable_path.chmod(current_mode | stat.S_IXUSR)

        if scope == "system":
            _run_privileged_copy(tmp_install_dir, final_install_dir)
            used_pkexec = True
        else:
            final_install_dir.parent.mkdir(parents=True, exist_ok=True)
            if final_install_dir.exists():
                shutil.rmtree(final_install_dir)
            shutil.copytree(tmp_install_dir, final_install_dir, symlinks=True)

    final_executable = final_install_dir / Path(*PurePosixPath(chosen_executable_rel).parts)
    desktop_file: Path | None = None
    if create_desktop:
        if scope == "system":
            # Keep desktop entry user-local to avoid another root action and to make uninstall predictable.
            desktop_dir = DEFAULT_USER_DESKTOP_DIR
        else:
            desktop_dir = DEFAULT_USER_DESKTOP_DIR
        desktop_file = desktop_dir / f"tarman-{app_slug}.desktop"
        icon = find_icon(final_install_dir)
        create_desktop_entry(
            app_name=name,
            executable=final_executable,
            desktop_path=desktop_file,
            icon=icon,
            terminal=terminal,
        )

    manifest = write_manifest(
        app_name=name,
        archive=archive,
        install_dir=final_install_dir,
        executable=final_executable,
        desktop_file=desktop_file,
        scope=scope,
    )
    return InstallResult(
        app_name=name,
        install_dir=final_install_dir,
        executable=final_executable,
        desktop_file=desktop_file,
        manifest=manifest,
        scope=scope,
        used_privilege_escalation=used_pkexec,
    )


def uninstall(app_name_or_manifest: str, *, keep_files: bool = False) -> dict:
    installed = list_installed()
    matches = []
    key = app_name_or_manifest.lower()
    for item in installed:
        if key in {
            Path(item.get("manifest", "")).name.lower(),
            item.get("app_name", "").lower(),
            slugify(item.get("app_name", "")).lower(),
        }:
            matches.append(item)
    if not matches:
        # Also allow substring match as a convenience.
        for item in installed:
            if key in item.get("app_name", "").lower() or key in Path(item.get("manifest", "")).name.lower():
                matches.append(item)
    if not matches:
        raise TarmanError(f"No installed app matched: {app_name_or_manifest}")
    if len(matches) > 1:
        names = ", ".join(item.get("app_name", "unknown") for item in matches)
        raise TarmanError(f"Multiple installed apps matched; be more specific: {names}")
    item = matches[0]
    removed: list[str] = []
    if item.get("desktop_file"):
        desktop = Path(item["desktop_file"]).expanduser()
        if desktop.exists():
            desktop.unlink()
            removed.append(str(desktop))
    if not keep_files and item.get("install_dir"):
        install_dir = Path(item["install_dir"]).expanduser()
        if install_dir.exists():
            if item.get("scope") == "system" and not os.access(install_dir.parent, os.W_OK):
                _run_privileged_remove(install_dir)
            else:
                shutil.rmtree(install_dir)
            removed.append(str(install_dir))
    manifest = Path(item.get("manifest", ""))
    if manifest.exists():
        manifest.unlink()
        removed.append(str(manifest))
    return {"app_name": item.get("app_name"), "removed": removed}
