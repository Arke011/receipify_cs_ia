import io
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

from app.services import image_service, ocr_service
from app.services.ocr_service import ScanError, parse_receipt_text, normalize_upload
from app.ui import receipt_dialog, scan_dialog


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


def test_parser_separates_items_total_tax_and_change():
    result = parse_receipt_text(RECEIPT)
    assert result.merchant == "TECH STORE"
    assert result.purchase_date == "2026-01-15"
    assert result.total_cents == 2999
    assert result.items == [("Wireless Mouse", 2499), ("USB Cable", 500)]


def test_lithuanian_labels_decimal_commas_and_thousands():
    result = parse_receipt_text("PARDUOTUVĖ\n2026.01.15\nNešiojamas kompiuteris 1 249,99\nNuolaida -50,00\nIŠ VISO 1 199,99\nGRĄŽA 0,01")
    assert result.merchant == "PARDUOTUVĖ"
    assert result.items == [("Nešiojamas kompiuteris", 124999)]
    assert result.total_cents == 119999


@pytest.mark.parametrize("text", ["04/05/2026", "2026-01-01\n2026-01-02", "2026-02-30", "2027-01-01"])
def test_ambiguous_invalid_and_future_dates_are_not_guessed(text):
    assert not parse_receipt_text(text, today=date(2026, 9, 10)).purchase_date


def test_unambiguous_day_first_date_and_conflicting_totals():
    result = parse_receipt_text("15.01.2026\nTOTAL 10.00\nTOTAL 12.00")
    assert result.purchase_date == "2026-01-15"
    assert result.total_cents is None


def test_foreign_currency_prices_are_filled_with_a_warning_and_refunds_are_not():
    result = parse_receipt_text("SHOP\nMouse $24.99\nTOTAL USD 24.99")
    assert result.total_cents == 2499
    assert result.items == [("Mouse", 2499)]
    assert any("not in euros" in note for note in result.notes)
    assert not any("not in euros" in note for note in parse_receipt_text("SHOP\nMouse €24.99").notes)
    assert parse_receipt_text("Returned Mouse -24.99").items == []


def test_normalize_photo_applies_orientation_and_removes_metadata():
    image = Image.new("RGB", (120, 80), "white")
    exif = image.getexif()
    exif[274] = 6
    exif[270] = "Private image description"
    data = io.BytesIO()
    image.save(data, format="JPEG", exif=exif)
    with Image.open(io.BytesIO(normalize_upload(data.getvalue()))) as received:
        assert received.size == (80, 120)
        assert received.format == "JPEG"
        assert not received.getexif()


def test_invalid_and_oversized_uploads_are_rejected(monkeypatch):
    with pytest.raises(ScanError, match="Cannot read"):
        normalize_upload(b"not an image")
    monkeypatch.setattr(ocr_service, "MAX_IMAGE_BYTES", 5)
    with pytest.raises(ScanError, match="15 MB"):
        normalize_upload(b"123456")
    monkeypatch.setattr(ocr_service, "MAX_IMAGE_PIXELS", 1)
    with pytest.raises(ScanError, match="30 megapixels"):
        ocr_service.read_image(io.BytesIO(make_photo_bytes()))


def make_photo_bytes():
    data = io.BytesIO()
    Image.new("RGB", (100, 150), "white").save(data, format="PNG")
    return data.getvalue()


def test_missing_engine_has_actionable_error(monkeypatch):
    monkeypatch.setenv("RECEIPIFY_TESSERACT_CMD", "/not/installed/tesseract")
    with pytest.raises(ScanError, match="Install Tesseract 5"):
        ocr_service.find_tesseract()


def test_engine_process_can_time_out_and_cancel():
    with pytest.raises(ScanError, match="timed out"):
        ocr_service.run_tesseract([sys.executable, "-c", "import time; time.sleep(10)"], Event(), timeout=0.1)
    cancelled = Event()
    cancelled.set()
    with pytest.raises(ScanError, match="cancelled"):
        ocr_service.run_tesseract([sys.executable, "-c", "raise RuntimeError()"], cancelled)


def test_scan_review_requires_explicit_product_or_total_choice(qapp, tmp_path):
    dialog = scan_dialog.ScanDialog(tmp_path)
    dialog.image_path = str(tmp_path / "receipt.jpg")
    job = object()
    dialog.job = job
    dialog.show_result(job, parse_receipt_text(RECEIPT), "")
    assert dialog.purchase.currentData() is None
    dialog.purchase.setCurrentIndex(1)
    dialog.use_result()
    assert dialog.values == {"merchant_name": "TECH STORE", "purchase_date": "2026-01-15", "product_name": "Wireless Mouse", "price": "24.99"}
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_old_worker_result_is_ignored_after_replacement(qapp, tmp_path):
    dialog = scan_dialog.ScanDialog(tmp_path)
    dialog.job = object()
    dialog.show_result(object(), parse_receipt_text(RECEIPT), "")
    assert dialog.result_data is None
    assert not dialog.use_button.isEnabled()
    dialog.job = None
    dialog.close()


def test_failed_ocr_still_allows_attaching_photo(qapp, tmp_path):
    dialog = scan_dialog.ScanDialog(tmp_path)
    dialog.image_path = str(tmp_path / "receipt.jpg")
    job = object()
    dialog.job = job
    dialog.show_result(job, None, "Tesseract is not installed")
    assert "not installed" in dialog.status.text()
    assert dialog.use_button.isEnabled()
    dialog.use_result()
    assert dialog.values == {}
    assert dialog.result() == QDialog.DialogCode.Accepted


@pytest.mark.parametrize("save_receipt", [False, True])
def test_scanning_prefills_blanks_preserves_typed_values_and_cleans_temp(monkeypatch, qapp, tmp_path, save_receipt):
    class AcceptedScan(QDialog):
        def __init__(self, directory, image_path, parent):
            super().__init__(parent)
            self.image_path = str(Path(directory) / "phone.jpg")
            Path(self.image_path).write_bytes(make_photo_bytes())
            self.values = {"merchant_name": "TECH STORE", "product_name": "Mouse", "price": "24.99", "purchase_date": "2026-01-15"}

        def start(self):
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(receipt_dialog, "ScanDialog", AcceptedScan)
    dialog = receipt_dialog.AddReceiptDialog(default_warranty_days=730, default_return_days=14)
    dialog.product_name_input.setText("My chosen product")
    dialog.category_name_input.setText("Office")
    dialog.scan_with_ocr()
    assert dialog.merchant_name_input.text() == "TECH STORE"
    assert dialog.product_name_input.text() == "My chosen product"
    assert dialog.price_input.text() == "24.99"
    assert dialog.category_name_input.text() == "Office"
    assert dialog.warranty_days_input.text() == "730"
    assert dialog.return_days_input.text() == "14"
    temporary_image = Path(dialog.selected_image_path)
    assert temporary_image.exists()
    if save_receipt:
        from app.services.image_service import copy_receipt_image
        managed = tmp_path / "managed"
        monkeypatch.setattr(receipt_dialog, "copy_receipt_image", lambda source: copy_receipt_image(source, managed))
        dialog.validate_and_accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
        assert Path(dialog.cleaned_values["image_path"]).exists()
        assert Path(dialog.cleaned_values["image_path"]).parent == managed
    else:
        dialog.reject()
        assert dialog.cleaned_values == {}
    assert not temporary_image.exists()


@pytest.mark.parametrize("cancel", [False, True])
def test_worker_returns_without_blocking_ui(qapp, monkeypatch, tmp_path, cancel):
    gate = Event()
    def delayed_scan(path, cancelled):
        gate.wait(timeout=3)
        return parse_receipt_text(RECEIPT)
    monkeypatch.setattr(scan_dialog, "scan_image", delayed_scan)
    dialog = scan_dialog.ScanDialog(tmp_path)
    dialog.show()
    (tmp_path / "photo.jpg").write_bytes(make_photo_bytes())
    dialog.start_ocr(tmp_path / "photo.jpg")
    assert dialog.progress.isVisible()
    assert not dialog.use_button.isEnabled()
    if cancel:
        dialog.reject()
    gate.set()
    for _ in range(100):
        QTest.qWait(20)
        if dialog.use_button.isEnabled() or cancel:
            break
    if cancel:
        assert dialog.job is None
        assert dialog.result_data is None
        assert not dialog.isVisible()
    else:
        assert dialog.result_data.merchant == "TECH STORE"
    dialog.close()
    QThreadPool.globalInstance().waitForDone(3000)


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Install Tesseract to run real OCR integration")
def test_real_tesseract_reads_a_generated_receipt(tmp_path):
    fonts = ["/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    font_path = next((font for font in fonts if Path(font).exists()), None)
    if font_path is None:
        pytest.skip("No integration-test font available")
    image = Image.new("RGB", (1000, 700), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(font_path, 38)
    draw.multiline_text((50, 45), RECEIPT, font=font, fill="black", spacing=14)
    path = tmp_path / "receipt.png"
    image.save(path)
    result = ocr_service.scan_image(path)
    assert result.merchant == "TECH STORE"
    assert result.purchase_date == "2026-01-15"
    assert result.total_cents == 2999
    assert ("Wireless Mouse", 2499) in result.items


def test_items_wrapped_onto_a_following_line_are_recovered():
    # Many receipts print the name, then the quantity and price underneath.
    result = parse_receipt_text("SHOP\nPienas Šviežias 1L\n1 x 1,29 1,29\nVISO 1,29")
    assert result.items == [("Pienas Šviežias 1L", 129)]
    assert result.total_cents == 129


def test_quantity_times_unit_price_uses_the_line_total():
    result = parse_receipt_text("SHOP\nDuona juoda 2 x 1,29 2,58\nVISO 2,58")
    assert result.items == [("Duona juoda", 258)]
    assert result.total_cents == 258


def test_interim_subtotal_does_not_conflict_with_the_final_total():
    result = parse_receipt_text("SHOP\nPienas 1L 1,29\nTarpinė suma 1,29\nVISO 1,29")
    assert result.total_cents == 129
    assert not any("Several totals" in note for note in result.notes)


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Install Tesseract to run real OCR integration")
def test_photo_without_a_receipt_returns_no_text(tmp_path):
    # Tesseract cannot report "no text here": pointed at a desk it returns
    # confident-looking nonsense, which must never become a merchant name.
    import random

    random.seed(7)
    image = Image.new("RGB", (1200, 1600), (140, 138, 135))
    pixels = image.load()
    for _ in range(180000):
        x, y = random.randrange(image.width), random.randrange(image.height)
        shift = random.randint(-28, 28)
        pixels[x, y] = tuple(max(0, min(255, channel + shift)) for channel in pixels[x, y])
    path = tmp_path / "desk.jpg"
    image.save(path, quality=70)
    result = ocr_service.scan_image(path)
    assert result.text == ""
    assert result.merchant == ""
    assert result.items == []
    assert result.total_cents is None


def test_amounts_with_a_space_after_the_decimal_mark_are_read():
    # Tesseract routinely reads "159,99" as "159, 99".
    result = parse_receipt_text("SHOP\nMonitor Lenovo 159, 99\nSUMA 159, 99 EUR")
    assert result.total_cents == 15999
    assert result.items == [("Monitor Lenovo", 15999)]


def test_grouped_thousands_are_still_read_as_one_amount():
    result = parse_receipt_text("SHOP\nServeris 24 159, 99\nSUMA 24 159, 99")
    assert result.items == [("Serveris", 2415999)]
    assert result.total_cents == 2415999


def test_a_lone_amount_does_not_attach_to_the_notice_above_it():
    # "Saugokite kvitą" is a keep-your-receipt notice, not a product.
    result = parse_receipt_text("SHOP\nSaugokite kvitą išrašui\n159, 99\nMokėti 159, 99")
    assert result.items == []
    assert result.total_cents == 15999


def test_serial_and_reference_lines_are_not_used_as_the_merchant():
    result = parse_receipt_text("Ser. Nr. : SURPOSOLL\nAut. kodas ABCDEF\nMokėti 10,00")
    assert result.merchant == ""


@pytest.mark.skipif(not ocr_service.HEIC_SUPPORTED, reason="pillow-heif is not installed")
def test_iphone_heic_is_read_and_stored_as_jpeg(qapp, tmp_path):
    from PIL import Image as PILImage

    source = PILImage.new("RGB", (60, 40), "white")
    heic = tmp_path / "IMG_0001.HEIC"
    source.save(heic, format="HEIF")
    assert ocr_service.read_image(heic).size == (60, 40)
    # The stored copy must be a format the receipt image viewer can display.
    dialog = scan_dialog.ScanDialog(str(tmp_path), parent=None)
    stored = Path(dialog.as_stored_image(str(heic)))
    assert stored.suffix == ".jpg"
    assert PILImage.open(stored).format == "JPEG"
    assert stored.suffix in image_service.SUPPORTED_IMAGE_EXTENSIONS
    dialog.close()


def test_card_terminal_lines_are_not_offered_as_products():
    # "Pardavimas" (sale) labels the amount; MultiPOINT is the card terminal.
    result = parse_receipt_text(
        "UAB \"Avitelos prekyba\"\nPardavimas 159, 99 EUR\n"
        "MultiPOINT 07.20. 076 0076\nApskaitos Kvitas: 000000004200\nMokėti 159, 99")
    assert result.items == []
    assert result.total_cents == 15999


def test_quoted_trading_name_loses_its_quotes():
    result = parse_receipt_text("\"Avitelos prekyba\nVilnius\nMokėti 10,00")
    assert result.merchant == "Avitelos prekyba"


def test_conflicting_dates_are_kept_as_candidates():
    # A misread year turns one printed date into two; both are offered, none guessed.
    result = parse_receipt_text("SHOP\n2025-02-20 Laikas 18:56\nCR-01 2026-02-20 18:56\nMokėti 10,00")
    assert result.purchase_date == ""
    assert result.dates == ["2025-02-20", "2026-02-20"]


def test_split_price_offers_the_product_against_the_receipt_total(qapp, tmp_path):
    # OCR split "159,99" across two lines, leaving "9.99" beside the product.
    result = parse_receipt_text("SHOP\nMonitor 24 Lenovo 9.99 A\nSUMA 159, 99 EUR")
    assert result.items == [("Monitor 24 Lenovo", 999)]
    assert result.total_cents == 15999
    dialog = scan_dialog.ScanDialog(str(tmp_path))
    dialog.show_result(dialog.job, result, "")
    offered = [dialog.purchase.itemData(i) for i in range(dialog.purchase.count())]
    assert ("Monitor 24 Lenovo", 15999) in offered
    assert offered.index(("Monitor 24 Lenovo", 15999)) < offered.index(("Monitor 24 Lenovo", 999))
    dialog.close()


def test_chosen_date_candidate_is_returned(qapp, tmp_path):
    result = parse_receipt_text("SHOP\n2025-02-20 Laikas 18:56\nCR-01 2026-02-20 18:56\nMokėti 10,00")
    dialog = scan_dialog.ScanDialog(str(tmp_path))
    dialog.show_result(dialog.job, result, "")
    dialog.image_path = str(tmp_path / "photo.jpg")
    dialog.purchase_date.setCurrentIndex(2)
    dialog.use_result()
    assert dialog.values["purchase_date"] == "2026-02-20"
    dialog.close()


def test_spelled_out_month_dates_are_read():
    today = date(2026, 9, 11)
    for text in ("Date April 8, 2025, 3:30 PM", "8 April 2025", "Apr 8th 2025", "8 apr. 2025"):
        assert parse_receipt_text(text, today=today).purchase_date == "2025-04-08", text
    assert parse_receipt_text("December 1, 2026", today=today).purchase_date == ""


def test_quantity_suffix_and_currency_sign_are_trimmed_from_product_names():
    result = parse_receipt_text("SHOP\nMinimalist T-Shirt x1 €25.00\nThinkPad X1 1299,00\nTotal €1 324,00")
    assert result.items == [("Minimalist T-Shirt", 2500), ("ThinkPad X1", 129900)]
