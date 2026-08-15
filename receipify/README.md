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

The Receipts section is functional: receipts can be added and searched.
Dashboard, Export, Settings, and OCR Import are navigation placeholders for
future work. OCR is intentionally not implemented yet.
