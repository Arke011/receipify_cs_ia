# Receipify

Receipify is a PyQt6 desktop application for recording purchases and tracking
warranty and return periods.

## Setup

Requires Python 3.10 or newer.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On Windows, activate the environment with `.venv\\Scripts\\activate`.

## Run the application

```bash
python main.py
```

The app stores its SQLite database and receipt images in the platform’s per-user
Receipify application-data directory.

## Run tests

```bash
python -m pytest
```

Tests use temporary SQLite databases and do not modify the application's local
database.

## Project structure

```text
app/
  data/          SQLite persistence layer
  models/        Receipt model
  services/      Validation and expiry calculations
  ui/            PyQt6 windows, dialogs, and receipt entries
data/            Local runtime database (not committed)
tests/           Automated tests
main.py          Application entry point
```

## Current scope

The interface uses standard Qt controls and system fonts, with four tabs:
Receipts, Dashboard, Export, and Settings. Receipt entries retain images,
warranty/return status icons and text, expiry dates, and Edit/Delete actions.
Log out is available beside the tabs. Receipts can be
added, edited, deleted, searched, filtered, and exported as CSV or JSON, and the
dashboard charts spending and upcoming warranty and return deadlines.

Receipt photos can be scanned locally with Tesseract, or uploaded from a phone
over the local network using a temporary QR connection. Detected details are
reviewed before being used in the receipt form.

## Receipt scanning

Install the Python dependencies from `requirements.txt`, and install the
**Tesseract 5 engine** separately. No OCR account, API key, or cloud service is
required. Ordinary receipt entry and image attachment also work without the engine.

On **Windows 11**, use the Windows installer linked from the
[Tesseract installation documentation](https://tesseract-ocr.github.io/tessdoc/Installation.html).
Include English language data; optionally include Lithuanian. Receipify checks
PATH and `C:\Program Files\Tesseract-OCR\tesseract.exe`. For a custom location,
set `RECEIPIFY_TESSERACT_CMD` to the full executable path before starting the app:

```powershell
$env:RECEIPIFY_TESSERACT_CMD = 'C:\Tools\Tesseract-OCR\tesseract.exe'
.\.venv\Scripts\python.exe main.py
```

On macOS, `brew install tesseract` supplies the engine and English data. Optional
additional languages are available through `brew install tesseract-lang`.
Scanning automatically uses English and Lithuanian when those language packs
are installed; `brew install tesseract-lang` supplies Lithuanian. No model is
downloaded while a scan runs. Each photo is read twice, as a single column and
as a uniform block, keeping whichever result parsed further: neither page layout
wins on every photo.

1. Open **Add receipt → Scan**. With no attachment, a QR code appears automatically.
   With an attachment, OCR starts on that image; **Use phone** switches to capture.
2. Connect the computer and phone to the same trusted local network. Scan the QR
   using the phone's camera, take or choose a photo, then press **Send to computer**.
   Alternatively, use **Choose image** on the computer.
3. Review the recognized merchant, date, and text. Pick the purchase date from
   the detected candidates, or leave it manual: a misread year prints one date
   twice, so candidates are offered rather than guessed between. Choose the
   product/price from the list, or explicitly select the receipt total and enter
   the product name yourself. Product and price remain manual until you make this
   selection. When one product is found whose printed price disagrees with the
   receipt total, the name is also offered against the total, which several lines
   of the receipt agree on; OCR splitting an amount across two lines is common.
4. Press **Use photo and details**. Only blank fields are prefilled. Existing typed
   values, category, and warranty/return defaults are preserved. Review the form
   and press **Save** to persist the receipt and its image.

Capture uses a random, single-upload token valid for five minutes. The listener
binds only to the selected local IPv4 address and closes when the photo arrives,
the connection expires, or the scan is cancelled. Closing the receipt/window
cleans temporary photos. No database or receipt gallery is accessible to the phone.
The phone connection uses **unencrypted local HTTP**, so use trusted Wi-Fi and
do not expose or forward the port to the internet.

If the phone cannot connect, select the correct Wi-Fi/Ethernet address in the
scan dialog. Windows may require allowing Receipify/Python through the firewall
on a **Private** network. Guest/school Wi-Fi may isolate devices; use another
trusted network or transfer the photo manually. The phone cannot use mobile
data alone to reach the computer. Camera/file-picker behavior depends on the
phone browser; an existing-photo picker is always offered as a fallback.

Use a sharp, upright photo showing the entire receipt, with even lighting and
little background. Low-confidence words are discarded, so a blurred frame or a
photo with no receipt in it reports no text rather than inventing one; if a real
receipt comes back empty, retake it closer, sharper, and better lit. Fill as much
of the frame with the receipt as you can: a receipt occupying a small part of a
cluttered photo reads far worse than a close one. Uploads are limited to 15 MB
and 30 megapixels. JPEG, PNG, WebP, BMP, GIF and iPhone HEIC are accepted (HEIC
needs `pillow-heif`, in `requirements.txt`); a chosen HEIC is converted to JPEG
when stored, so it still displays. PDF must be converted first. Camera EXIF
orientation is honored and metadata is removed from uploaded copies.

OCR supplies suggestions, not verified purchase data. Ambiguous dates and
conflicting totals are left unset. Quantity columns (`2 x 1,29  2,58`) and
descriptions wrapped onto a second line are read; discounts, unusual layouts,
and faded print may still need manual entry. Dollar and pound amounts are filled in as printed, with a warning to convert
them before saving, because Receipify stores euros only.
Warranty/return terms and categories are not inferred. All receipt validation
still runs on Save. If the OCR engine is missing or reading fails, **Use photo
only** still lets you attach the image and enter details manually.

The test suite includes local HTTP upload tests and a real OCR smoke test using
a generated receipt (skipped when Tesseract or a suitable font is unavailable).
Tests use temporary data. Real phone/browser capture and Windows firewall behavior
should also be checked on the target Windows 11 computer.

## Dashboard

The dashboard retains all-time spending, warranty counts, category spending
with percentages, and deadline review (expired and within the next 30 days).
The chart's selector offers **All years** for yearly totals, or a specific year
for its twelve monthly totals. Hover for an exact amount. Changing the chart
period does not filter the other dashboard sections. There are no zoom controls,
receipt drill-downs, or separate chart/statistics windows.
