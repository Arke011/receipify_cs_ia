from datetime import date

import pytest

from app.services import expiry_service


def test_add_days_to_iso_date_returns_expiry_or_none():
    assert expiry_service.add_days_to_iso_date("2026-01-31", 2) == "2026-02-02"
    assert expiry_service.add_days_to_iso_date("2026-01-31", 0) is None
    assert expiry_service.add_days_to_iso_date("2026-01-31", -1) is None


def test_add_days_to_iso_date_rejects_invalid_dates():
    with pytest.raises(ValueError):
        expiry_service.add_days_to_iso_date("not-a-date", 1)


def test_days_until_iso_date_uses_today(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 8, 15)

    monkeypatch.setattr(expiry_service, "date", FixedDate)

    assert expiry_service.days_until_iso_date("2026-08-15") == 0
    assert expiry_service.days_until_iso_date("2026-08-20") == 5
    assert expiry_service.days_until_iso_date("2026-08-14") == -1
    assert expiry_service.days_until_iso_date(None) is None


@pytest.mark.parametrize(
    ("days_remaining", "expected"),
    [
        (None, {"label": "not tracked", "color": "grey"}),
        (-1, {"label": "expired", "color": "red"}),
        (7, {"label": "expiring soon", "color": "orange"}),
        (8, {"label": "active", "color": "green"}),
    ],
)
def test_expiry_status_covers_each_state(days_remaining, expected):
    assert expiry_service.expiry_status(days_remaining, 7, "not tracked") == expected
