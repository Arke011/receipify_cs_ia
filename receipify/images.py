"""Receipt photos are copied into Receipify's own folder, so the user can move or delete the original."""

from pathlib import Path
from shutil import copy2
from uuid import uuid4

from database import DATA_DIR

IMAGE_DIR = DATA_DIR / "receipt_images"
IMAGE_TYPES = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}


def copy_image(source):
    """Copy a chosen image into IMAGE_DIR under a random name and return the copy's path."""
    source = Path(source)
    if not source.is_file():
        raise FileNotFoundError(f"Image file does not exist: {source}")
    extension = source.suffix.lower()
    if extension not in IMAGE_TYPES:
        raise ValueError("Choose a supported image file.")
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    destination = IMAGE_DIR / f"{uuid4().hex}{extension}"
    copy2(source, destination)
    return str(destination.resolve())


def delete_image(path):
    """Delete Receipify's copy of an image. Files outside IMAGE_DIR, like the user's originals, are left alone."""
    if path and Path(path).resolve().is_relative_to(IMAGE_DIR.resolve()):
        Path(path).unlink(missing_ok=True)
