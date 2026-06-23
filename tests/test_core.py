from __future__ import annotations

import os
import stat
import tarfile
from pathlib import Path

import pytest

from tarman.core import UnsafeArchiveError, analyze_archive, install_archive, list_members, safe_extract


def make_tar(path: Path, root: Path) -> None:
    with tarfile.open(path, "w:gz") as tar:
        tar.add(root, arcname=root.name)


def test_analyze_detects_launcher(tmp_path: Path):
    app = tmp_path / "CoolApp"
    bin_dir = app / "bin"
    bin_dir.mkdir(parents=True)
    launcher = bin_dir / "coolapp"
    launcher.write_text("#!/bin/sh\necho cool\n")
    launcher.chmod(0o755)
    archive = tmp_path / "CoolApp.tar.gz"
    make_tar(archive, app)

    analysis = analyze_archive(archive)

    assert analysis.top_level == "CoolApp"
    assert analysis.recommended_executable == "bin/coolapp"


def test_rejects_path_traversal(tmp_path: Path):
    archive = tmp_path / "bad.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        info = tarfile.TarInfo("../evil")
        data = b"nope"
        info.size = len(data)
        tar.addfile(info, fileobj=__import__("io").BytesIO(data))

    with pytest.raises(UnsafeArchiveError):
        list_members(archive)


def test_install_user_creates_desktop(tmp_path: Path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    # Constants are evaluated at import time, so patch them directly.
    import tarman.core as core

    monkeypatch.setattr(core, "DEFAULT_USER_APPS_DIR", home / ".local/share/tarman/apps")
    monkeypatch.setattr(core, "DEFAULT_USER_DESKTOP_DIR", home / ".local/share/applications")
    monkeypatch.setattr(core, "DEFAULT_USER_MANIFEST_DIR", home / ".local/share/tarman/manifests")

    app = tmp_path / "CoolApp"
    bin_dir = app / "bin"
    bin_dir.mkdir(parents=True)
    launcher = bin_dir / "coolapp"
    launcher.write_text("#!/bin/sh\necho cool\n")
    launcher.chmod(0o755)
    archive = tmp_path / "CoolApp.tar.gz"
    make_tar(archive, app)

    result = install_archive(archive, app_name="Cool App")

    assert result.install_dir.exists()
    assert result.executable.exists()
    assert result.desktop_file and result.desktop_file.exists()
    assert "Exec=" in result.desktop_file.read_text()
