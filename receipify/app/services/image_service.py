from pathlib import Path
from shutil import copy2
from uuid import uuid4

from app.paths import APP_ROOT, IMAGE_DIR


MANAGED_IMAGE_DIRECTORY = IMAGE_DIR
SUPPORTED_IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}


def copy_receipt_image(source_path, destination_directory=MANAGED_IMAGE_DIRECTORY):
    """Copy a user-selected image into the application's managed image folder.

    Returns a path relative to the application root when the copy lands inside
    it, so stored paths survive the whole application folder being moved.
    """
    source = Path(source_path)

    if not source.is_file():
        raise FileNotFoundError(f"Image file does not exist: {source}")

    extension = source.suffix.lower()
    if extension not in SUPPORTED_IMAGE_EXTENSIONS:
        raise ValueError("Choose a supported image file.")

    destination_directory = Path(destination_directory)
    destination_directory.mkdir(parents=True, exist_ok=True)
    destination = destination_directory / f"{uuid4().hex}{extension}"
    copy2(source, destination)

    try:
        return str(destination.resolve().relative_to(APP_ROOT))
    except ValueError:
        return str(destination.resolve())


def resolve_image_path(stored_path):
    """Turn a stored image path into an absolute one, accepting legacy relative values."""
    image_path = Path(stored_path)

    if image_path.is_absolute():
        return image_path

    return APP_ROOT / image_path
