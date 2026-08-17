import importlib
import sys
from pathlib import Path

from PyQt6.QtCore import QStandardPaths

from app.data.data_manager import DataManager
from app.services import image_service


def reload_paths():
    import app.paths

    return importlib.reload(app.paths)


def test_application_paths_are_absolute_and_independent_of_cwd(tmp_path, monkeypatch):
    paths = reload_paths()
    original = (paths.APP_ROOT, paths.DATA_DIR, paths.IMAGE_DIR, paths.DATABASE_PATH)

    assert all(path.is_absolute() for path in original)

    monkeypatch.chdir(tmp_path)
    reloaded = reload_paths()

    assert (
        reloaded.APP_ROOT,
        reloaded.DATA_DIR,
        reloaded.IMAGE_DIR,
        reloaded.DATABASE_PATH,
    ) == original


def test_data_and_image_directories_sit_in_the_platform_data_location():
    paths = reload_paths()
    standard_location = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppDataLocation
    )

    assert paths.DATA_DIR == Path(standard_location)
    assert paths.DATA_DIR.name == paths.APPLICATION_NAME
    assert paths.DATABASE_PATH.parent == paths.DATA_DIR
    assert paths.IMAGE_DIR.parent == paths.DATA_DIR


def test_data_directories_are_created_when_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.paths.application_data_root", lambda: tmp_path / "Receipify"
    )
    paths = reload_paths()

    try:
        assert paths.DATA_DIR.is_dir()
        assert paths.IMAGE_DIR.is_dir()
    finally:
        monkeypatch.undo()
        reload_paths()


def test_data_is_stored_outside_the_application_folder():
    """The app folder can be read-only, so it must never hold the user's data."""
    paths = reload_paths()

    assert paths.APP_ROOT not in paths.DATA_DIR.parents
    assert paths.DATA_DIR != paths.APP_ROOT


def test_frozen_builds_store_data_outside_the_extraction_directory(tmp_path, monkeypatch):
    """A frozen executable must not persist data in PyInstaller's temp extraction dir."""
    executable_directory = tmp_path / "portable-app"
    executable_directory.mkdir()
    extraction_directory = tmp_path / "_MEI123456"
    extraction_directory.mkdir()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(extraction_directory), raising=False)
    monkeypatch.setattr(sys, "executable", str(executable_directory / "Receipify.exe"))

    paths = reload_paths()

    assert paths.APP_ROOT == executable_directory
    assert paths.DATABASE_PATH == paths.DATA_DIR / "receipify.db"
    assert extraction_directory not in paths.DATABASE_PATH.parents

    monkeypatch.undo()
    reload_paths()


def test_default_database_and_image_locations_do_not_depend_on_cwd(tmp_path, monkeypatch):
    paths = reload_paths()

    monkeypatch.chdir(tmp_path)

    assert DataManager.default_database_path() == paths.DATABASE_PATH
    assert image_service.MANAGED_IMAGE_DIRECTORY == paths.IMAGE_DIR
    assert image_service.MANAGED_IMAGE_DIRECTORY.is_absolute()


def test_images_stored_under_the_app_root_are_recorded_as_portable_relative_paths(tmp_path):
    paths = reload_paths()
    source = tmp_path / "receipt.png"
    source.write_bytes(b"image bytes")
    destination = paths.APP_ROOT / "portability-check"

    stored_path = image_service.copy_receipt_image(source, destination)

    try:
        assert not Path(stored_path).is_absolute()
        assert image_service.resolve_image_path(stored_path).read_bytes() == b"image bytes"
    finally:
        (paths.APP_ROOT / stored_path).unlink(missing_ok=True)
        destination.rmdir()


def test_managed_images_now_live_outside_the_app_root_and_keep_absolute_paths(tmp_path):
    """Images moved with the data directory, so their stored paths are absolute."""
    paths = reload_paths()
    source = tmp_path / "receipt.png"
    source.write_bytes(b"image bytes")

    stored_path = image_service.copy_receipt_image(source)

    try:
        assert Path(stored_path).is_absolute()
        assert Path(stored_path).parent == paths.IMAGE_DIR
        assert image_service.is_managed_receipt_image(stored_path) is True
    finally:
        Path(stored_path).unlink(missing_ok=True)


def test_images_stored_outside_the_app_root_keep_an_absolute_path(tmp_path):
    source = tmp_path / "receipt.png"
    source.write_bytes(b"image bytes")

    stored_path = image_service.copy_receipt_image(source, tmp_path / "elsewhere")

    assert Path(stored_path).is_absolute()
    assert image_service.resolve_image_path(stored_path) == Path(stored_path)


def test_legacy_relative_image_paths_resolve_against_the_app_root():
    paths = reload_paths()

    resolved = image_service.resolve_image_path("data/receipt_images/legacy.png")

    assert resolved == paths.APP_ROOT / "data" / "receipt_images" / "legacy.png"
