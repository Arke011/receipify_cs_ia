from pathlib import Path

import pytest

from app.services.image_service import copy_receipt_image


def test_copy_receipt_image_uses_managed_directory(tmp_path):
    source = tmp_path / "receipt.png"
    source.write_bytes(b"image bytes")
    image_directory = tmp_path / "managed-images"

    copied_path = Path(copy_receipt_image(source, image_directory))

    assert copied_path.parent == image_directory
    assert copied_path.suffix == ".png"
    assert copied_path.name != source.name
    assert copied_path.read_bytes() == b"image bytes"


def test_copy_receipt_image_rejects_missing_or_unsupported_files(tmp_path):
    missing_image = tmp_path / "missing.png"
    unsupported_file = tmp_path / "receipt.txt"
    unsupported_file.write_text("not an image")

    with pytest.raises(FileNotFoundError):
        copy_receipt_image(missing_image, tmp_path / "managed-images")

    with pytest.raises(ValueError, match="supported image"):
        copy_receipt_image(unsupported_file, tmp_path / "managed-images")
