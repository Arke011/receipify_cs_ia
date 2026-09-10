import pytest

from app.data.data_manager import DataManager
from app.services.settings_service import DEFAULT_SETTINGS, validate_settings
from app.ui.main_window import MainWindow


def test_settings_messages_switch_between_error_and_success(qapp, tmp_path):
    window = MainWindow(data_manager=DataManager(tmp_path / "receipify-test.db"))
    window.show()
    window.show_page("Settings")
    page = window.settings_page
    callbacks = []
    page.on_settings_saved = lambda: callbacks.append(True)
    before = window.data_manager.get_settings()

    page.default_warranty_input.setText("not-a-number")
    page.save_settings()
    assert page.message_label.isVisible()
    assert page.message_label.text().startswith("Error: ")
    assert "integer" in page.message_label.text()
    assert window.data_manager.get_settings() == before
    assert callbacks == []

    page.default_warranty_input.setText("730")
    page.save_settings()
    assert page.message_label.text() == "Settings saved."
    assert window.data_manager.get_settings()["default_warranty_days"] == 730
    assert callbacks == [True]

    page.default_warranty_input.setText("not-a-number")
    page.save_settings()
    assert page.message_label.text().startswith("Error: ")
    assert window.data_manager.get_settings()["default_warranty_days"] == 730
    assert callbacks == [True]
    window.close()


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
