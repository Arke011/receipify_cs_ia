"""Reads receipt photos with the local Tesseract engine and suggests details from the text.

Suggestions are never saved directly: the user reviews them, and ambiguous
dates or totals are left blank rather than guessed.
"""

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
    # iPhones save HEIC, which Pillow can only read with this optional plug-in.
    from pillow_heif import register_heif_opener
except ImportError:
    HEIC_SUPPORTED = False
else:
    register_heif_opener()
    HEIC_SUPPORTED = True

MAX_IMAGE_BYTES = 15 * 1024 * 1024
MAX_IMAGE_PIXELS = 30_000_000
MIN_CONFIDENCE = 60  # real receipt words score about 90; noise from a blurred photo scores under 30
MIN_WORDS = 5

# An amount such as 24.99, 1 249,99 or "159, 99" (OCR often adds a space after the decimal mark).
MONEY = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:[ ,.\u00a0]\d{3})+|\d+)[.,][ \u00a0]?\d{2}(?!\d)")
# Lines that state the amount paid. "Pardavimas" (sale) labels the total, not a product.
TOTAL = re.compile(r"\b(?:grand total|total due|amount due|total|is viso|viso|moketi|suma|pardavimas|pirkimas)\b")
NOT_FINAL_TOTAL = re.compile(r"subtotal|sub total|tarpine|tax|vat|pvm|discount|nuolaida")
# Lines that print an amount but never name a product: payment, tax, card-terminal and bookkeeping lines.
NON_ITEM = re.compile(
    r"\b(?:total|subtotal|tax|vat|pvm|cash|card|change|discount|savings|balance|paid|payment|visa|mastercard"
    r"|usd|gbp|viso|suma|moketi|graza|grynais|kortele|nuolaida|aciu|thank|kvitas|receipt|tel|phone"
    r"|pardavimas|pirkimas|multipoint|contactless|patvirtint\w*|apskaitos|atsk|teisingai|ivestas|saugokite"
    r"|kasinink\w*|kasa|parasas|infolinija|registracija|serviso|servisui|informacija|modulio|numeris)\b")
# Serial numbers and reference codes, which are not shop names.
IDENTIFIER = re.compile(r"\b(?:ser|nr|s/n|id|kodas|kvit\w*|atsk|ref|term|aut)\b")
WEB_ADDRESS = re.compile(r"www\.|https?://|@")
# "2 x 1,29" at the end of a product name is a quantity, not part of the name.
QUANTITY = re.compile(r"\s*\b\d+(?:[.,]\d+)?\s*(?:vnt|kg|g|l|ml|pcs?)?\s*[x×*]\s*$", re.IGNORECASE)
# Lower-case "x1" after a name is a quantity; "ThinkPad X1" is a model name and is kept.
QUANTITY_SUFFIX = re.compile(r"\s+[x×]\s?\d{1,3}$")
# A "2 x 1,29   2,58" line continues the product named on the line above it.
CONTINUATION = re.compile(r"\b\d+(?:[.,]\d+)?\s*(?:vnt|kg|g|l|ml|pcs?)?\s*[x×*]", re.IGNORECASE)

ISO_DATE = re.compile(r"\b(\d{4})[-/.](\d{2})[-/.](\d{2})\b")
DAY_FIRST_DATE = re.compile(r"\b(\d{2})[./-](\d{2})[./-](\d{4})\b")
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
MONTH_NAME = (r"(?P<month>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?"
              r"|sept?(?:ember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\.?")
NAMED_DATES = (  # "April 8, 2025" and "8 April 2025"
    re.compile(rf"\b{MONTH_NAME}\s+(?P<day>\d{{1,2}})(?:st|nd|rd|th)?,?\s+(?P<year>\d{{4}})\b", re.IGNORECASE),
    re.compile(rf"\b(?P<day>\d{{1,2}})(?:st|nd|rd|th)?\s+{MONTH_NAME},?\s+(?P<year>\d{{4}})\b", re.IGNORECASE),
)


class ScanError(ValueError):
    pass


@dataclass
class ScanResult:
    text: str
    merchant: str = ""
    purchase_date: str = ""  # set only when exactly one date was found
    total_cents: int | None = None  # set only when exactly one total was found
    items: list[tuple[str, int]] = field(default_factory=list)  # (product name, price in cents)
    notes: list[str] = field(default_factory=list)
    dates: list[str] = field(default_factory=list)  # every date candidate found


# ---- photos

def load_photo(source):
    """Open a photo safely: reject huge images, apply the camera's rotation, flatten transparency onto white."""
    try:
        with Image.open(source) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ScanError("Photo is too large. Use an image under 30 megapixels.")
            image.load()
            upright = ImageOps.exif_transpose(image)
            photo = Image.new("RGB", upright.size, "white")
            if upright.mode in ("RGBA", "LA") or "transparency" in upright.info:
                rgba = upright.convert("RGBA")
                photo.paste(rgba, mask=rgba.getchannel("A"))
            else:
                photo.paste(upright.convert("RGB"))
            photo.thumbnail((3000, 5000))
            return photo
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as error:
        if HEIC_SUPPORTED:
            advice = "Cannot read this photo. Choose a JPEG, PNG, WebP, or HEIC image."
        else:
            advice = "Cannot read this photo. Choose a JPEG, PNG, or WebP image; convert HEIC to JPEG first."
        raise ScanError(advice) from error


def clean_photo(data):
    """Re-encode photo bytes as a plain JPEG: size-checked, upright, and with metadata (e.g. location) removed."""
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ScanError("Choose a photo smaller than 15 MB.")
    output = io.BytesIO()
    load_photo(io.BytesIO(data)).save(output, format="JPEG", quality=92)
    return output.getvalue()


# ---- running Tesseract

def find_tesseract():
    configured = os.environ.get("RECEIPIFY_TESSERACT_CMD")
    if configured:
        candidates = [configured]
    else:
        candidates = [shutil.which("tesseract")]
        if os.name == "nt":
            for folder in (os.environ.get("ProgramFiles", "C:/Program Files"),
                           os.environ.get("LOCALAPPDATA", "C:/Users/Default/AppData/Local")):
                candidates.append(str(Path(folder) / "Tesseract-OCR" / "tesseract.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise ScanError("Tesseract is not installed or cannot be found. Install Tesseract 5 with English language "
                    "data, then restart Receipify. See README → Receipt scanning. You can still attach photos "
                    "and enter details manually.")


def run_tesseract(arguments, cancelled, timeout=40):
    """Run Tesseract and return its output, stopping early if the scan is cancelled or takes too long."""
    no_window = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    try:
        process = subprocess.Popen(arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=no_window)
    except OSError as error:
        raise ScanError("Could not start Tesseract. Check the engine installation and "
                        "RECEIPIFY_TESSERACT_CMD setting.") from error
    deadline = time.monotonic() + timeout
    with process:
        # Wait in short steps, so a cancel from the dialog is noticed within 0.1 s.
        while True:
            if cancelled.is_set() or time.monotonic() >= deadline:
                process.kill()
                process.communicate()
                if cancelled.is_set():
                    raise ScanError("Scan cancelled.")
                raise ScanError("Scanning timed out. Try a clearer, cropped photo.")
            try:
                output, _ = process.communicate(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                pass
    if process.returncode:
        raise ScanError("Tesseract could not read the photo. Check its language data installation and try another image.")
    return output.decode("utf-8", errors="replace")


def scan_image(data, cancelled=None):
    """Read photo bytes with Tesseract and return the parsed ScanResult."""
    cancelled = cancelled or Event()
    engine = find_tesseract()
    installed = run_tesseract([engine, "--list-langs"], cancelled, timeout=10).splitlines()
    languages = "+".join(language for language in ("eng", "lit") if language in installed)
    if not languages:
        raise ScanError("Install English (eng) or Lithuanian (lit) Tesseract language data before scanning.")
    # cutoff=1 ignores the brightest and darkest 1% of pixels, so one glare spot
    # cannot stop the contrast stretch from working on a dim photo.
    image = ImageOps.autocontrast(ImageOps.grayscale(load_photo(io.BytesIO(data))), cutoff=1)
    best, best_rank = None, None
    with TemporaryDirectory(prefix="receipify-ocr-") as folder:
        prepared = Path(folder) / "scan.png"
        image.save(prepared)
        # Neither page layout wins on every photo: "4" (single column) suits a receipt
        # with background around it, "6" (uniform block) suits a tilted or tightly
        # cropped one. Read both and keep whichever found more.
        for layout in ("4", "6"):
            tsv = run_tesseract([engine, str(prepared), "stdout", "-l", languages, "--psm", layout, "tsv"], cancelled)
            result, word_count = read_tsv(tsv)
            rank = (result.total_cents is not None, len(result.items), word_count)
            if best is None or rank > best_rank:
                best, best_rank = result, rank
    return best


def read_tsv(tsv):
    """Rebuild the text from Tesseract's table of words, keeping only confident words.

    Tesseract cannot say "there is no text here": pointed at a desk it returns
    confident-looking nonsense, so low-confidence words are dropped.
    Returns (ScanResult, number of words kept).
    """
    lines = {}
    kept = 0
    for word in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        if word["level"] != "5" or not word["text"].strip() or float(word["conf"]) < MIN_CONFIDENCE:
            continue
        line = (word["page_num"], word["block_num"], word["par_num"], word["line_num"])
        lines.setdefault(line, []).append(word["text"])
        kept += 1
    if kept < MIN_WORDS:
        return parse_receipt(""), 0  # a few stray marks are not a receipt
    return parse_receipt("\n".join(" ".join(words) for words in lines.values())), kept


# ---- reading the text

def plain(text):
    """Lower-case text without accents, so 'IŠ VISO' matches 'is viso'."""
    return "".join(c for c in unicodedata.normalize("NFKD", text.casefold()) if not unicodedata.combining(c))


def letters(text):
    return sum(c.isalpha() for c in text)


def amount_cents(amount):
    """A printed amount such as '1 249,99' or '159, 99' in cents."""
    compact = re.sub(r"[\s\u00a0]", "", amount)
    whole, fraction = compact[:-3], compact[-2:]
    return int(Decimal(re.sub(r"[.,]", "", whole) + "." + fraction) * 100)


def parse_receipt(text, today=None):
    """Suggest the merchant, purchase date, total and items printed on a receipt."""
    result = ScanResult(text=text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    find_dates(result, text, today or date.today())
    find_merchant(result, lines)
    find_items_and_total(result, lines)
    result.notes.insert(0, "Check every suggestion. OCR can misread names, dates, and prices.")
    if re.search(r"[$£]|\b(?:USD|GBP)\b", text, re.IGNORECASE):
        # Receipify stores euros only; the printed figures are still offered so
        # the user converts one pre-filled price instead of retyping it.
        result.notes.append("This receipt is not in euros. The amounts below are the printed "
                            "$ or £ figures: convert the price before saving.")
    return result


def find_dates(result, text, today):
    dates = set()

    def add(year, month, day):
        try:
            found = date(year, month, day)
        except ValueError:
            return  # e.g. 2026-02-30
        if found <= today:
            dates.add(found.isoformat())

    for year, month, day in ISO_DATE.findall(text):
        add(int(year), int(month), int(day))
    for day, month, year in DAY_FIRST_DATE.findall(text):
        day, month, year = int(day), int(month), int(year)
        # 04/05 could be 4 May or April 5; a locale is never guessed.
        if day <= 12 and month <= 12 and day != month:
            result.notes.append("An ambiguous date was found; enter the purchase date manually.")
        else:
            add(year, month, day)
    for pattern in NAMED_DATES:
        for match in pattern.finditer(text):
            add(int(match["year"]), MONTHS.index(match["month"][:3].lower()) + 1, int(match["day"]))

    # Every candidate is kept: a misread year turns one printed date into two,
    # and choosing between them is the user's job.
    result.dates = sorted(dates)
    if len(dates) == 1:
        result.purchase_date = result.dates[0]
    elif len(dates) > 1:
        result.notes.append("Several dates were found; choose the purchase date below.")


def find_merchant(result, lines):
    """The shop name: the first of the top six lines that is words only."""
    for line in lines[:6]:
        folded = plain(line)
        if (letters(line) >= 3 and not any(c.isdigit() for c in line) and not NON_ITEM.search(folded)
                and not IDENTIFIER.search(folded) and not WEB_ADDRESS.search(folded)):
            # Receipts often quote the trading name: UAB "Avitelos prekyba".
            result.merchant = line.strip("\"'«»„“”‘’ .,:-")
            return


def find_items_and_total(result, lines):
    totals = set()
    waiting_name = ""  # a product name printed on its own line, waiting for its price line
    for line in lines:
        folded = plain(line)
        amounts = list(MONEY.finditer(line))
        if not amounts:
            is_name = (letters(line) >= 3 and not NON_ITEM.search(folded)
                       and line != result.merchant and not WEB_ADDRESS.search(folded))
            waiting_name = line.strip(" .:-") if is_name else ""
            continue
        name_above, waiting_name = waiting_name, ""
        if any(line[:amount.start()].rstrip().endswith("-") for amount in amounts):
            continue  # a refund or discount such as "-50,00"
        # The rightmost amount is the line total; any amount before it is a unit price.
        cents = amount_cents(amounts[-1].group())
        if not 0 < cents <= 9_999_999_999:
            continue
        if TOTAL.search(folded) and not NOT_FINAL_TOTAL.search(folded):
            totals.add(cents)
            continue
        text_before = line[:amounts[0].start()]
        if NON_ITEM.search(folded) or re.search(r"\d{4}[-/.]\d{2}", text_before):
            continue
        # "Minimalist T-Shirt x1 $25.00": drop the quantity and the currency sign.
        name = text_before.strip(" .:-$£€")
        name = QUANTITY_SUFFIX.sub("", QUANTITY.sub("", name)).strip(" .:-$£€")
        if letters(name) < 3:
            # Only a quantity line continues the name above it; a bare amount on
            # its own line is usually a total repeated under a notice.
            name = name_above if CONTINUATION.search(line) else ""
        if letters(name) >= 3 and name != result.merchant:
            result.items.append((name, cents))
    if len(totals) == 1:
        result.total_cents = totals.pop()
    elif len(totals) > 1:
        result.notes.append("Several totals were found; verify the price manually.")
