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

All source files sit in one folder. Each file is one feature or one shared rule set.

```text
main.py            Entry point; switches between the login dialog and the main window
database.py        SQLite storage (accounts, receipts, settings) and password hashing
receipt.py         Receipt record; date/price parsing, expiry status, form validation
images.py          Copies receipt photos into Receipify's own folder
login.py           Login / create-account dialog and username/password rules
main_window.py     Main window: the Receipts tab, receipt cards, image viewer
receipt_dialog.py  Add/edit receipt form
browse.py          Search, filter and sort rules, and the Filters dialog
dashboard.py       Dashboard figures, spending chart and Dashboard tab
export.py          CSV/JSON export and the Export tab
settings.py        Settings validation and the Settings tab
tests/             Automated tests
```

## Current scope

The interface uses standard Qt controls and system fonts, with four tabs:
Receipts, Dashboard, Export, and Settings. Receipt entries retain images,
warranty/return status icons and text, expiry dates, and Edit/Delete actions.
Log out is available beside the tabs. Receipts can be
added, edited, deleted, searched, filtered, and exported as CSV or JSON, and the
dashboard charts spending and upcoming warranty and return deadlines.

## Dashboard

The dashboard retains all-time spending, warranty counts, category spending
with percentages, and deadline review (expired and within the next 30 days).
The chart's selector offers **All years** for yearly totals, or a specific year
for its twelve monthly totals. Hover for an exact amount. Changing the chart
period does not filter the other dashboard sections. There are no zoom controls,
receipt drill-downs, or separate chart/statistics windows.
