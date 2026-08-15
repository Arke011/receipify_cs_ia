"""Absolute application paths, resolved once so they never depend on the working directory.

When frozen by PyInstaller, ``sys._MEIPASS`` points at a temporary extraction
directory that is deleted on exit, so persistent data is stored beside the
executable instead.
"""

import sys
from pathlib import Path


def application_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[1]


APP_ROOT = application_root()
DATA_DIR = APP_ROOT / "data"
IMAGE_DIR = DATA_DIR / "receipt_images"
DATABASE_PATH = DATA_DIR / "receipify.db"
