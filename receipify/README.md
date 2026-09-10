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

## Dashboard

The dashboard retains all-time spending, warranty counts, category spending
with percentages, and deadline review (expired and within the next 30 days).
The chart's selector offers **All years** for yearly totals, or a specific year
for its twelve monthly totals. Hover for an exact amount. Changing the chart
period does not filter the other dashboard sections. There are no zoom controls,
receipt drill-downs, or separate chart/statistics windows.
