"""Absolute application paths, resolved once so they never depend on the working directory.

Persistent data lives in the per-user location Qt reports for the platform,
which is ``~/Library/Application Support/Receipify`` on macOS. Writing there
rather than inside the application folder keeps the data out of a read-only
app bundle, and out of PyInstaller's ``sys._MEIPASS`` extraction directory,
which is deleted when a frozen build exits.
"""

import sys
from pathlib import Path

from PyQt6.QtCore import QCoreApplication, QStandardPaths


APPLICATION_NAME = "Receipify"


def application_root() -> Path:
    """Where the application's own files live, used to resolve legacy relative paths."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parents[1]


def application_data_root() -> Path:
    """The per-user writable data directory Qt reports for this platform."""
    # Qt builds the location from the application name, and defaults that name
    # to the running executable, which is "Python" while the app is started
    # through the interpreter. It is therefore always set here, before the
    # location is read, so the data directory is named for the application in
    # both a development run and a frozen build.
    QCoreApplication.setApplicationName(APPLICATION_NAME)

    location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )
    data_root = Path(location) if location else Path.home() / ".receipify"

    # Qt omits the application name when it has not been set, so the directory
    # is named here instead of sharing the platform's data folder.
    if data_root.name != APPLICATION_NAME:
        data_root = data_root / APPLICATION_NAME

    return data_root


def ensure_directories() -> None:
    """Create the data directories, which do not exist before the first run."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)


APP_ROOT = application_root()
DATA_DIR = application_data_root()
IMAGE_DIR = DATA_DIR / "receipt_images"
DATABASE_PATH = DATA_DIR / "receipify.db"

ensure_directories()
