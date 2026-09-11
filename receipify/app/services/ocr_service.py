"""Local OCR and conservative suggestions; never writes receipt records."""

import csv
import io
import os
import re
import shutil
import subprocess
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from PIL import Image, ImageOps, UnidentifiedImageError

try:
    # iPhones save HEIC. Pillow cannot read it alone, so register the opener when
    # the optional decoder is present; without it HEIC still fails with advice.
    from pillow_heif import register_heif_opener
except ImportError:
    HEIC_SUPPORTED = False
else:
    register_heif_opener()
    HEIC_SUPPORTED = True

MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 30_000_000
MIN_WORD_CONFIDENCE = 60
MIN_WORDS = 5
# OCR often inserts a space after the decimal mark, reading "159,99" as "159, 99".
MONEY = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:[ ,.\u00a0]\d{3})+|\d+)[.,][ \u00a0]?\d{2}(?!\d)")
PAGE_MODES = ("4", "6")
# "Pardavimas 159,99 EUR" labels the sale amount, so it is a total, not a product.
TOTAL = re.compile(r"\b(?:grand total|total due|amount due|total|is viso|viso|moketi|suma|pardavimas|pirkimas)\b")
QUANTITY = re.compile(r"\s*\b\d+(?:[.,]\d+)?\s*(?:vnt|kg|g|l|ml|pcs?)?\s*[x×*]\s*$", re.IGNORECASE)
# Lower-case "x1" after a name is a quantity; "ThinkPad X1" is a model and is kept.
QUANTITY_SUFFIX = re.compile(r"\s+[x×]\s?\d{1,3}$")
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
MONTH_NAME = r"(?P<month>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?"
NAMED_DATES = (
    re.compile(rf"\b{MONTH_NAME}\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?,?\s+(?P<year>\d{{4}})\b", re.IGNORECASE),
    re.compile(rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+{MONTH_NAME},?\s+(?P<year>\d{{4}})\b", re.IGNORECASE),
)
# "2 x 1,29   2,58" continues the product named on the line above; a lone amount does not.
CONTINUATION = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:vnt|kg|g|l|ml|pcs?)?\s*[x×*]", re.IGNORECASE)
# Serial numbers and reference codes are not shop names.
IDENTIFIER = re.compile(r"\b(?:ser|nr|s/n|id|kodas|kvit\w*|atsk|ref|term|aut)\b")
NON_ITEM = re.compile(
    r"\b(?:total|subtotal|tax|vat|pvm|cash|card|change|discount|savings|balance|paid|payment|visa|mastercard"
    r"|usd|gbp|viso|suma|moketi|graza|grynais|kortele|nuolaida|aciu|thank|kvitas|receipt|tel|phone"
    # Card-terminal and bookkeeping lines print amounts but never name a product.
    r"|pardavimas|pirkimas|multipoint|contactless|patvirtint\w*|apskaitos|atsk|teisingai|ivestas|saugokite"
    r"|kasinink\w*|kasa|parasas|infolinija|registracija|serviso|servisui|informacija|modulio|numeris)\b")


class ScanError(ValueError):
    pass


@dataclass
class ScanResult:
    text: str
    merchant: str = ""
    purchase_date: str = ""
    total_cents: int | None = None
    items: list[tuple[str, int]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)


def plain(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def amount_cents(text):
    compact = re.sub(r"[\s\u00a0]", "", text)
    whole, fraction = compact[:-3], compact[-2:]
    return int(Decimal(re.sub(r"[.,]", "", whole) + "." + fraction) * 100)


def read_image(source):
    """Decode with a size cap, honor camera orientation, discard metadata."""
    try:
        with Image.open(source) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ScanError("Photo is too large. Use an image under 30 megapixels.")
            image.load()
            oriented = ImageOps.exif_transpose(image)
            background = Image.new("RGB", oriented.size, "white")
            if oriented.mode in ("RGBA", "LA") or "transparency" in oriented.info:
                rgba = oriented.convert("RGBA")
                background.paste(rgba, mask=rgba.getchannel("A"))
            else:
                background.paste(oriented.convert("RGB"))
            background.thumbnail((3000, 5000))
            return background
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        advice = ("Cannot read this photo. Choose a JPEG, PNG, WebP, or HEIC image."
                  if HEIC_SUPPORTED else
                  "Cannot read this photo. Choose a JPEG, PNG, or WebP image; convert HEIC to JPEG first.")
        raise ScanError(advice) from error


def normalize_upload(data):
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ScanError("Choose a photo smaller than 15 MB.")
    image = read_image(io.BytesIO(data))
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=92)
    return output.getvalue()


def find_tesseract():
    configured = os.environ.get("RECEIPIFY_TESSERACT_CMD")
    candidates = [configured] if configured else [shutil.which("tesseract")]
    if not configured and os.name == "nt":
        candidates += [str(Path(os.environ.get(key, fallback)) / "Tesseract-OCR" / "tesseract.exe")
                       for key, fallback in (("ProgramFiles", "C:/Program Files"),
                                             ("LOCALAPPDATA", "C:/Users/Default/AppData/Local"))]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise ScanError("Tesseract is not installed or cannot be found. Install Tesseract 5 with English language data, then restart Receipify. See README → Receipt scanning. You can still attach photos and enter details manually.")


def run_tesseract(arguments, cancelled, timeout=40):
    if cancelled.is_set():
        raise ScanError("Scan cancelled.")
    options = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    try:
        with subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options) as process:
            deadline = time.monotonic() + timeout
            while True:
                if cancelled.is_set() or time.monotonic() >= deadline:
                    process.kill()
                    process.communicate()
                    raise ScanError("Scan cancelled." if cancelled.is_set() else "Scanning timed out. Try a clearer, cropped photo.")
                try:
                    output, error = process.communicate(timeout=0.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode:
                raise ScanError("Tesseract could not read the photo. Check its language data installation and try another image.")
            return output.decode("utf-8", errors="replace")
    except OSError as error:
        raise ScanError("Could not start Tesseract. Check the engine installation and RECEIPIFY_TESSERACT_CMD setting.") from error


def scan_image(path, cancelled=None):
    cancelled = cancelled or Event()
    engine = find_tesseract()
    if isinstance(path, bytes):
        source, size = io.BytesIO(path), len(path)
    else:
        source, size = Path(path), Path(path).stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise ScanError("Choose a photo smaller than 15 MB.")
    languages = run_tesseract([engine, "--list-langs"], cancelled, timeout=10).splitlines()
    language = "+".join(lang for lang in ("eng", "lit") if lang in languages)
    if not language:
        raise ScanError("Install English (eng) or Lithuanian (lit) Tesseract language data before scanning.")
    with TemporaryDirectory(prefix="receipify-ocr-") as folder:
        # cutoff=1 discards the brightest and darkest 1% before stretching. Without
        # it a single blown-out pixel and a few black ones span the histogram, so
        # autocontrast does nothing at all on a dim phone photo of a pale receipt.
        image = ImageOps.autocontrast(ImageOps.grayscale(read_image(source)), cutoff=1)
        prepared = Path(folder) / "scan.png"
        image.save(prepared)
        best = None
        for mode in PAGE_MODES:
            tsv = run_tesseract([engine, str(prepared), "stdout", "-l", language, "--psm", mode, "tsv"], cancelled)
            result, words = read_words(tsv)
            # Neither segmentation mode wins on every photo: a single column suits
            # a receipt surrounded by background, a uniform block suits a tilted or
            # tightly cropped one. Read both and keep whichever parsed further.
            rank = (result.total_cents is not None, len(result.items), words)
            if best is None or rank > best[0]:
                best = (rank, result)
    return best[1]


def read_words(tsv):
    lines = {}
    kept = 0
    for word in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if word.get("level") != "5" or not word.get("text", "").strip():
            continue
        # Tesseract cannot report "no text here": pointed at a desk or a blurred
        # frame it returns page after page of confident-looking nonsense. Real
        # receipt words score around 90; noise scores under 30.
        try:
            confidence = float(word.get("conf", "-1"))
        except ValueError:
            continue
        if confidence < MIN_WORD_CONFIDENCE:
            continue
        key = tuple(word.get(name) for name in ("page_num", "block_num", "par_num", "line_num"))
        lines.setdefault(key, []).append(word["text"])
        kept += 1
    if kept < MIN_WORDS:
        # A stray surviving mark is not a receipt; do not invent a merchant from it.
        return parse_receipt_text(""), 0
    return parse_receipt_text("\n".join(" ".join(words) for words in lines.values())), kept


def parse_receipt_text(text, today=None):
    """Suggestions only: ambiguous dates/totals stay unset; items need review."""
    today = today or date.today()
    result = ScanResult(text=text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    dates = set()
    for match in re.finditer(r"\b(\d{4})[-/.](\d{2})[-/.](\d{2})\b", text):
        try:
            value = date(*map(int, match.groups()))
            if value <= today:
                dates.add(value.isoformat())
        except ValueError:
            pass
    for match in re.finditer(r"\b(\d{2})[./-](\d{2})[./-](\d{4})\b", text):
        day, month, year = map(int, match.groups())
        # 04/05 could be April 5 or May 4. Do not silently pick a locale.
        if day <= 12 and month <= 12 and day != month:
            result.notes.append("An ambiguous date was found; enter the purchase date manually.")
            continue
        try:
            value = date(year, month, day)
            if value <= today:
                dates.add(value.isoformat())
        except ValueError:
            pass
    # A spelled-out month is never ambiguous: "April 8, 2025" or "8 April 2025".
    for pattern in NAMED_DATES:
        for match in pattern.finditer(text):
            try:
                value = date(int(match["year"]), MONTHS.index(match["month"][:3].lower()) + 1, int(match["day"]))
            except ValueError:
                continue
            if value <= today:
                dates.add(value.isoformat())
    # Keep every candidate: a misread year turns one printed date into two, and
    # choosing between them is the reader's job, not a guess this parser may make.
    result.dates = sorted(dates)
    if len(dates) == 1:
        result.purchase_date = result.dates[0]
    elif len(dates) > 1:
        result.notes.append("Several dates were found; choose the purchase date below.")

    for line in lines[:6]:
        folded = plain(line)
        if (sum(c.isalpha() for c in line) >= 3 and not any(c.isdigit() for c in line)
                and not NON_ITEM.search(folded) and not IDENTIFIER.search(folded)
                and not re.search(r"www\.|https?://|@", folded)):
            # Receipts wrap the trading name in quotes: UAB "Avitelos prekyba".
            result.merchant = line.strip("\"'«»„“”‘’ .,:-")
            break

    totals = set()
    pending = ""
    for line in lines:
        folded = plain(line)
        amounts = list(MONEY.finditer(line))
        if not amounts:
            # Many receipts print the product name on its own line and the
            # quantity and price underneath. Hold the name for the next line.
            pending = (line.strip(" .:-")
                       if (sum(c.isalpha() for c in line) >= 3 and not NON_ITEM.search(folded)
                           and line != result.merchant and not re.search(r"www\.|https?://|@", folded))
                       else "")
            continue
        carried, pending = pending, ""
        if any(line[:amount.start()].rstrip().endswith("-") for amount in amounts):
            continue
        # The rightmost amount is the line total; anything before it is a unit price.
        cents = amount_cents(amounts[-1].group())
        if not 0 < cents <= 9_999_999_999:
            continue
        if TOTAL.search(folded) and not re.search(r"subtotal|sub total|tarpine|tax|vat|pvm|discount|nuolaida", folded):
            totals.add(cents)
            continue
        if NON_ITEM.search(folded) or re.search(r"\d{4}[-/.]\d{2}", line[:amounts[0].start()]):
            continue
        # "Minimalist T-Shirt x1 $25.00": drop the quantity and the currency sign.
        description = line[:amounts[0].start()].strip(" .:-$£€")
        description = QUANTITY_SUFFIX.sub("", QUANTITY.sub("", description)).strip(" .:-$£€")
        if sum(c.isalpha() for c in description) < 3:
            # Only a quantity line continues the name above it. A bare amount on
            # its own line is usually a total restated under a notice or heading.
            description = carried if CONTINUATION.search(line) else ""
        if sum(c.isalpha() for c in description) >= 3 and description != result.merchant:
            result.items.append((description, cents))
    if len(totals) == 1:
        result.total_cents = totals.pop()
    elif len(totals) > 1:
        result.notes.append("Several totals were found; verify the price manually.")
    result.notes.insert(0, "Check every suggestion. OCR can misread names, dates, and prices.")
    if re.search(r"[$£]|\b(?:USD|GBP)\b", text, re.IGNORECASE):
        # Receipify stores euros only. The printed figures are still offered, so the
        # reader converts one pre-filled price instead of retyping it.
        result.notes.append("This receipt is not in euros. The amounts below are the printed "
                            "$ or £ figures: convert the price before saving.")
    return result
