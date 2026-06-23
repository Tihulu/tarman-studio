from __future__ import annotations

from importlib import resources
from pathlib import Path

APP_ID = "tarman-studio"
ICON_NAME = "tarman-studio"
DESKTOP_FILE = "tarman-studio"


def resource_path(relative: str) -> Path:
    """Return a filesystem path for bundled package resources."""
    return Path(str(resources.files("tarman") / relative))


def icon_path() -> Path:
    return resource_path("assets/tarman-studio.svg")


def combo_arrow_path() -> Path:
    return resource_path("assets/combobox-arrow.svg")


def checkbox_check_path() -> Path:
    return resource_path("assets/checkbox-check.svg")


def radio_dot_path() -> Path:
    return resource_path("assets/radio-dot.svg")
