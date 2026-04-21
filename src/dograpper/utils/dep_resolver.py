"""
Runtime dependency resolver for dograpper.

DOGRAPPER_HOME env var is read at module import time. Tests that need to
override it must set the env var BEFORE importing (or use importlib.reload).
"""

import os
import shutil
from pathlib import Path

DEFAULT_HOME = Path.home() / ".dograpper"
DOGRAPPER_HOME = Path(os.environ.get("DOGRAPPER_HOME", DEFAULT_HOME))
USER_BIN_DIR = DOGRAPPER_HOME / "bin"
USER_BROWSER_DIR = DOGRAPPER_HOME / "playwright-browsers"


def ensure_dirs() -> None:
    USER_BIN_DIR.mkdir(parents=True, exist_ok=True)
    USER_BROWSER_DIR.mkdir(parents=True, exist_ok=True)


def resolve_wget() -> str:
    candidate = USER_BIN_DIR / "wget"
    if candidate.exists() and os.access(candidate, os.X_OK):
        return str(candidate)
    return shutil.which("wget") or "wget"


def resolve_browser_dir() -> str:
    return str(USER_BROWSER_DIR)


def ensure_playwright_browsers_path() -> None:
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", resolve_browser_dir())


_initialized = False
if not _initialized:
    ensure_dirs()
    ensure_playwright_browsers_path()
    _initialized = True
