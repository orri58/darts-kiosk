"""Helpers for reading the application version from the local install."""
from __future__ import annotations

import os
from pathlib import Path

VERSION_FILE = Path(__file__).resolve().parent.parent.parent / "VERSION"


def read_app_version(default: str = "0.0.0") -> str:
    """Read the current app version from the local VERSION file.

    This stays dynamic on purpose so long-running processes still report the
    real installed version after an external updater replaces files.
    """
    try:
        value = VERSION_FILE.read_text(encoding="utf-8").strip()
        return value or os.environ.get("APP_VERSION", default)
    except FileNotFoundError:
        return os.environ.get("APP_VERSION", default)
