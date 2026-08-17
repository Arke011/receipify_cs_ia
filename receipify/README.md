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

The app creates its local SQLite database at `data/receipify.db` when needed.

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
  ui/            PyQt6 windows, dialogs, cards, and styles
data/            Local runtime database (not committed)
tests/           Automated tests
main.py          Application entry point
```

## Current scope

Receipts, Dashboard, Export, and Settings are all functional. Receipts can be
added, edited, deleted, searched, filtered, and exported as CSV or JSON, and the
dashboard charts spending and upcoming warranty and return deadlines.

Reading receipt details from a photo is not implemented. The entry point for it
sits in the Add Receipt dialog as "Scan with OCR", which currently explains that
the feature is not available yet.
