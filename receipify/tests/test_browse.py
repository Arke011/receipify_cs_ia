from browse import DEFAULT_FILTERS, FilterDialog, count_active, filter_receipts, sort_receipts
from database import DEFAULT_SETTINGS


def browse(db, query="", **filters):
    return [r.product for r in filter_receipts(db.receipts(1), query, {**DEFAULT_FILTERS, **filters}, DEFAULT_SETTINGS)]


def test_search_filters_and_sort_combine(db, add_receipt):
    untracked = {"warranty_days": 0, "return_days": 0}
    add_receipt(product="Laptop", price_cents=10000, purchase_date="2026-08-02", **untracked)
    add_receipt(product="Laptop Stand", price_cents=6000, purchase_date="2026-08-03", **untracked)
    add_receipt(product="Laptop Sleeve", merchant="Office Shop", purchase_date="2026-08-03", **untracked)
    add_receipt(product="Old Laptop", purchase_date="2025-01-01", **untracked)
    add_receipt(product="Tracked Laptop", purchase_date="2026-08-03")
    add_receipt(product="Mouse", purchase_date="2026-08-03", **untracked)
    assert browse(db, "laptop", merchant="Tech Store", warranty_status="Not tracked",
                  date_from="2026-08-01", date_to="2026-08-04", sort_by="Price (lowest)") == ["Laptop Stand", "Laptop"]


def test_search_matches_names_and_typed_prices(db, add_receipt):
    add_receipt(product="Mouse", price_cents=2499)
    add_receipt(product="Cable", category="Accessories", price_cents=500)
    assert browse(db, "24,99") == ["Mouse"]
    assert browse(db, "ACCESS") == ["Cable"]
    assert browse(db, "tech store") == ["Cable", "Mouse"]


def test_every_sort_option(db, add_receipt):
    old = add_receipt(product="Zulu", price_cents=300, purchase_date="2026-01-01")
    new = add_receipt(product="Alpha", price_cents=100, purchase_date="2026-02-01")
    middle = add_receipt(product="Mouse", price_cents=200, purchase_date="2026-01-15")
    expected = {
        "Purchase date (newest)": [new, middle, old],
        "Purchase date (oldest)": [old, middle, new],
        "Price (highest)": [old, middle, new],
        "Price (lowest)": [new, middle, old],
        "Product name (A-Z)": [new, middle, old],
        "Product name (Z-A)": [old, middle, new],
        "Recently added": [middle, new, old],
    }
    for sort_by, ids in expected.items():
        assert [r.id for r in sort_receipts(db.receipts(1), sort_by)] == ids, sort_by


def test_filter_dialog_offers_used_merchants_and_returns_the_choices(db, add_receipt):
    add_receipt(merchant="Tech Store")
    add_receipt(merchant="HomeGoods")
    dialog = FilterDialog({**DEFAULT_FILTERS, "sort_by": "Price (lowest)"}, db.receipts(1))
    merchants = dialog.combos["merchant"]
    assert [merchants.itemText(i) for i in range(merchants.count())] == ["All", "HomeGoods", "Tech Store"]
    assert dialog.combos["sort_by"].currentText() == "Price (lowest)"

    merchants.setCurrentText("HomeGoods")
    dialog.date_from.setText(" 2026-01-01 ")
    dialog.accept()
    assert dialog.values == {**DEFAULT_FILTERS, "merchant": "HomeGoods", "sort_by": "Price (lowest)",
                             "date_from": "2026-01-01"}
    assert count_active(dialog.values) == 3
