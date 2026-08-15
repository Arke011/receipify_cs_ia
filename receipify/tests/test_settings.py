import pytest

from app.data.data_manager import DataManager
from app.services.settings_service import DEFAULT_SETTINGS, validate_settings


def test_data_manager_returns_defaults_when_no_settings_exist(tmp_path):
    data_manager = DataManager(tmp_path / "receipify-test.db")

    assert data_manager.get_settings() == DEFAULT_SETTINGS


def test_data_manager_persists_settings_between_instances(tmp_path):
    database_path = tmp_path / "receipify-test.db"
    data_manager = DataManager(database_path)
    saved_settings = {
        "default_warranty_days": 730,
        "default_return_days": 14,
        "warranty_warning_threshold": 45,
        "return_warning_threshold": 10,
    }

    data_manager.save_settings(**saved_settings)

    reloaded_manager = DataManager(database_path)
    assert reloaded_manager.get_settings() == saved_settings


def test_validate_settings_rejects_invalid_values():
    is_valid, errors, values = validate_settings("365", "-1", "soon", "7")

    assert is_valid is False
    assert errors == [
        "Default return days must be greater than or equal to 0.",
        "Warranty warning threshold must be an integer.",
    ]
    assert values == {}


def test_data_manager_rejects_invalid_settings(tmp_path):
    data_manager = DataManager(tmp_path / "receipify-test.db")

    with pytest.raises(ValueError, match="Default warranty days"):
        data_manager.save_settings(-1, 30, 30, 7)
