from pathlib import Path
from shutil import copy2
from uuid import uuid4


MANAGED_IMAGE_DIRECTORY = Path("data/receipt_images")
SUPPORTED_IMAGE_EXTENSIONS = {".bmp", ".gif", ".jpeg", ".jpg", ".png", ".webp"}


def copy_receipt_image(source_path, destination_directory=MANAGED_IMAGE_DIRECTORY):
    """Copy a user-selected image into the application's managed image folder."""
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
    return str(destination)
