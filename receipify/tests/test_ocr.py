import io
import random
import shutil
import sys
from datetime import date
from pathlib import Path
from threading import Event

import pytest
from PIL import Image, ImageDraw, ImageFont
from PyQt6.QtCore import QThreadPool
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog

import ocr
import scan_dialog
from ocr import ScanError, clean_photo, parse_receipt

needs_tesseract = pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract is not installed")

RECEIPT = """TECH STORE
Receipt 1234
2026-01-15 14:30
Wireless Mouse 24.99 EUR
USB Cable 5.00 EUR
Subtotal 29.99
VAT 5.21
TOTAL EUR 29.99
CASH 50.00
CHANGE 20.01
Thank you
"""


def photo_bytes(size=(100, 150)):
    data = io.BytesIO()
    Image.new("RGB", size, "white").save(data, format="PNG")
    return data.getvalue()


# ---- reading receipt text

def test_reads_merchant_date_items_and_total():
    result = parse_receipt(RECEIPT)
    assert result.merchant == "TECH STORE"
    assert result.purchase_date == "2026-01-15"
    assert result.total_cents == 2999  # not the subtotal, tax, cash or change
    assert result.items == [("Wireless Mouse", 2499), ("USB Cable", 500)]


@pytest.mark.parametrize(("text", "items", "total"), [
    pytest.param("PARDUOTUVĖ\n2026.01.15\nNešiojamas kompiuteris 1 249,99\nNuolaida -50,00\nIŠ VISO 1 199,99\nGRĄŽA 0,01",
                 [("Nešiojamas kompiuteris", 124999)], 119999, id="lithuanian-labels-and-discount"),
    pytest.param("SHOP\nPienas Šviežias 1L\n1 x 1,29 1,29\nVISO 1,29",
                 [("Pienas Šviežias 1L", 129)], 129, id="price-on-the-line-below"),
    pytest.param("SHOP\nDuona juoda 2 x 1,29 2,58\nVISO 2,58",
                 [("Duona juoda", 258)], 258, id="quantity-times-unit-price"),
    pytest.param("SHOP\nServeris 24 159, 99\nSUMA 24 159, 99",
                 [("Serveris", 2415999)], 2415999, id="space-after-decimal-mark"),
    pytest.param("SHOP\nPienas 1L 1,29\nTarpinė suma 1,29\nVISO 1,29",
                 [("Pienas 1L", 129)], 129, id="subtotal-is-not-a-second-total"),
    pytest.param("SHOP\nSaugokite kvitą išrašui\n159, 99\nMokėti 159, 99",
                 [], 15999, id="lone-amount-under-a-notice"),
    pytest.param("UAB \"Avitelos prekyba\"\nPardavimas 159, 99 EUR\nMultiPOINT 07.20. 076 0076\nMokėti 159, 99",
                 [], 15999, id="card-terminal-lines"),
    pytest.param("SHOP\nMinimalist T-Shirt x1 €25.00\nThinkPad X1 1299,00\nTotal €1 324,00",
                 [("Minimalist T-Shirt", 2500), ("ThinkPad X1", 129900)], 132400, id="quantity-suffix-and-model-name"),
])
def test_items_and_totals(text, items, total):
    result = parse_receipt(text)
    assert result.items == items
    assert result.total_cents == total


@pytest.mark.parametrize(("text", "expected"), [
    ("15.01.2026", "2026-01-15"),
    ("Date April 8, 2025, 3:30 PM", "2025-04-08"),
    ("8 apr. 2025", "2025-04-08"),
    ("04/05/2026", ""),  # 4 May or April 5: never guessed
    ("2026-02-30", ""),  # not a real date
    ("December 1, 2026", ""),  # in the future
])
def test_purchase_dates(text, expected):
    assert parse_receipt(text, today=date(2026, 9, 11)).purchase_date == expected


def test_conflicting_dates_are_offered_and_conflicting_totals_left_blank():
    result = parse_receipt("SHOP\n2025-02-20 Laikas 18:56\nCR-01 2026-02-20 18:56\nTOTAL 10.00\nTOTAL 12.00")
    assert result.purchase_date == ""
    assert result.dates == ["2025-02-20", "2026-02-20"]
    assert result.total_cents is None


def test_merchant_name_rules():
    assert parse_receipt("\"Avitelos prekyba\nVilnius\nMokėti 10,00").merchant == "Avitelos prekyba"
    assert parse_receipt("Ser. Nr. : SURPOSOLL\nAut. kodas ABCDEF\nMokėti 10,00").merchant == ""


def test_foreign_currency_is_filled_in_with_a_warning():
    result = parse_receipt("SHOP\nMouse $24.99\nTOTAL USD 24.99")
    assert result.items == [("Mouse", 2499)]
    assert any("not in euros" in note for note in result.notes)
    assert not any("not in euros" in note for note in parse_receipt("SHOP\nMouse €24.99").notes)


# ---- photos and the Tesseract engine

def test_uploaded_photos_are_turned_upright_and_lose_their_metadata():
    image = Image.new("RGB", (120, 80), "white")
    exif = image.getexif()
    exif[274] = 6  # "rotate 90°", as a phone held upright saves it
    exif[270] = "Private image description"
    data = io.BytesIO()
    image.save(data, format="JPEG", exif=exif)
    with Image.open(io.BytesIO(clean_photo(data.getvalue()))) as cleaned:
        assert cleaned.size == (80, 120)
        assert cleaned.format == "JPEG"
        assert not cleaned.getexif()


def test_unreadable_and_oversized_photos_are_rejected(monkeypatch):
    with pytest.raises(ScanError, match="Cannot read"):
        clean_photo(b"not an image")
    monkeypatch.setattr(ocr, "MAX_IMAGE_PIXELS", 1)
    with pytest.raises(ScanError, match="30 megapixels"):
        clean_photo(photo_bytes())


def test_missing_engine_gives_advice(monkeypatch):
    monkeypatch.setenv("RECEIPIFY_TESSERACT_CMD", "/not/installed/tesseract")
    with pytest.raises(ScanError, match="Install Tesseract 5"):
        ocr.find_tesseract()


def test_engine_can_time_out_and_be_cancelled():
    with pytest.raises(ScanError, match="timed out"):
        ocr.run_tesseract([sys.executable, "-c", "import time; time.sleep(10)"], Event(), timeout=0.1)
    cancelled = Event()
    cancelled.set()
    with pytest.raises(ScanError, match="cancelled"):
        ocr.run_tesseract([sys.executable, "-c", "import time; time.sleep(10)"], cancelled)


@needs_tesseract
def test_real_tesseract_reads_a_generated_receipt():
    fonts = ["/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    font_path = next((font for font in fonts if Path(font).exists()), None)
    if font_path is None:
        pytest.skip("No font available to draw the receipt")
    image = Image.new("RGB", (1000, 700), "white")
    ImageDraw.Draw(image).multiline_text((50, 45), RECEIPT, font=ImageFont.truetype(font_path, 38),
                                         fill="black", spacing=14)
    data = io.BytesIO()
    image.save(data, format="PNG")
    result = ocr.scan_image(data.getvalue())
    assert result.merchant == "TECH STORE"
    assert result.purchase_date == "2026-01-15"
    assert result.total_cents == 2999
    assert ("Wireless Mouse", 2499) in result.items


@needs_tesseract
def test_a_photo_without_a_receipt_gives_no_text():
    # Pointed at a desk, Tesseract returns confident-looking nonsense, which
    # must never become a merchant name.
    random.seed(7)
    image = Image.new("RGB", (1200, 1600), (140, 138, 135))
    pixels = image.load()
    for _ in range(180000):
        x, y = random.randrange(image.width), random.randrange(image.height)
        shift = random.randint(-28, 28)
        pixels[x, y] = tuple(max(0, min(255, channel + shift)) for channel in pixels[x, y])
    data = io.BytesIO()
    image.save(data, format="JPEG", quality=70)
    result = ocr.scan_image(data.getvalue())
    assert (result.text, result.merchant, result.items, result.total_cents) == ("", "", [], None)


@pytest.mark.skipif(not ocr.HEIC_SUPPORTED, reason="pillow-heif is not installed")
def test_iphone_heic_photos_are_stored_as_jpeg(tmp_path):
    heic = tmp_path / "IMG_0001.HEIC"
    Image.new("RGB", (60, 40), "white").save(heic, format="HEIF")
    stored = Path(scan_dialog.ScanDialog(str(tmp_path)).heic_to_jpeg(str(heic)))
    with Image.open(stored) as image:
        assert image.format == "JPEG"  # a format the receipt image viewer can show


# ---- reviewing the result in the scan dialog

def review(tmp_path, result):
    """A scan dialog showing an OCR result, as if its background job had just finished."""
    dialog = scan_dialog.ScanDialog(str(tmp_path))
    dialog.image_path = str(tmp_path / "photo.jpg")
    dialog.show_result(dialog.job, result, "")
    return dialog


def test_review_needs_an_explicit_product_choice(tmp_path):
    dialog = review(tmp_path, parse_receipt(RECEIPT))
    assert dialog.purchase_date.currentData() == "2026-01-15"
    assert dialog.purchase.currentData() is None  # "Enter product and price manually"
    dialog.purchase.setCurrentIndex(1)
    dialog.use_result()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.values == {"merchant": "TECH STORE", "purchase_date": "2026-01-15",
                             "product": "Wireless Mouse", "price": "24.99"}


def test_a_split_price_offers_the_receipt_total_first(tmp_path):
    # OCR split "159,99" across two lines, leaving "9.99" beside the product.
    dialog = review(tmp_path, parse_receipt("SHOP\nMonitor 24 Lenovo 9.99 A\nSUMA 159, 99 EUR"))
    offered = [dialog.purchase.itemData(i) for i in range(dialog.purchase.count())]
    assert offered == [None, ("Monitor 24 Lenovo", 15999), ("Monitor 24 Lenovo", 999), ("", 15999)]


def test_failed_ocr_still_allows_using_the_photo(tmp_path):
    dialog = scan_dialog.ScanDialog(str(tmp_path))
    dialog.image_path = str(tmp_path / "photo.jpg")
    dialog.show_result(None, None, "Tesseract is not installed")
    assert dialog.status.text() == "Tesseract is not installed"
    assert dialog.use_button.text() == "Use photo only"
    dialog.use_result()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.values == {}


@pytest.mark.parametrize("cancel", [False, True])
def test_ocr_runs_in_the_background_and_can_be_cancelled(monkeypatch, tmp_path, cancel):
    release = Event()

    def slow_scan(data, cancelled):
        release.wait(timeout=3)
        return parse_receipt(RECEIPT)

    monkeypatch.setattr(scan_dialog, "scan_image", slow_scan)
    (tmp_path / "photo.png").write_bytes(photo_bytes())
    dialog = scan_dialog.ScanDialog(str(tmp_path))
    dialog.show()
    dialog.start_ocr(tmp_path / "photo.png")
    assert dialog.progress.isVisible()  # the dialog is still responsive while OCR runs
    if cancel:
        dialog.reject()
    release.set()
    for _ in range(100):
        QTest.qWait(20)
        if dialog.use_button.isEnabled():
            break
    if cancel:
        assert dialog.job is None and dialog.scan_result is None
    else:
        assert dialog.scan_result.merchant == "TECH STORE"
    dialog.close()
    QThreadPool.globalInstance().waitForDone(3000)
