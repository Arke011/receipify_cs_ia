import pytest
from PyQt6.QtWidgets import QDialog

from app.data.data_manager import DataManager
from app.ui.login_dialog import LoginDialog
from app.ui.main_window import MainWindow
from app.ui.session_controller import SessionController


@pytest.fixture
def data_manager(tmp_path):
    return DataManager(tmp_path / "receipify-test.db")


def test_first_run_opens_in_register_mode(qapp, data_manager):
    dialog = LoginDialog(data_manager)

    assert dialog.is_registering is True
    assert "Create" in dialog.submit_button.text()


def test_dialog_opens_in_login_mode_once_an_account_exists(qapp, data_manager):
    data_manager.register_user("alice", "password123")

    dialog = LoginDialog(data_manager)

    assert dialog.is_registering is False
    assert "Log In" in dialog.submit_button.text()


def test_registering_claims_the_legacy_account_and_accepts(qapp, data_manager):
    data_manager.add_receipt(
        product_name="Legacy Item",
        merchant_name="Shop",
        category_name="Home",
        price_cents=100,
        purchase_date="2026-01-01",
    )
    dialog = LoginDialog(data_manager)
    dialog.username_input.setText("alice")
    dialog.password_input.setText("password123")
    dialog.confirm_password_input.setText("password123")

    dialog.submit()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.user_id == 1
    assert dialog.username == "alice"
    assert [r.product_name for r in data_manager.get_all_receipts(dialog.user_id)] == [
        "Legacy Item"
    ]


def test_successful_login_exposes_the_authenticated_user(qapp, data_manager):
    expected_id = data_manager.register_user("alice", "password123")
    dialog = LoginDialog(data_manager)
    dialog.username_input.setText("alice")
    dialog.password_input.setText("password123")

    dialog.submit()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.user_id == expected_id


def test_failed_login_shows_a_non_specific_error_and_does_not_accept(qapp, data_manager):
    data_manager.register_user("alice", "password123")
    dialog = LoginDialog(data_manager)
    dialog.username_input.setText("alice")
    dialog.password_input.setText("wrong-password")

    dialog.submit()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.user_id is None
    assert dialog.error_label.text() == "Incorrect username or password."
    assert dialog.error_label.isVisible() or not dialog.isVisible()


def test_login_error_does_not_reveal_whether_the_username_exists(qapp, data_manager):
    data_manager.register_user("alice", "password123")

    unknown_user = LoginDialog(data_manager)
    unknown_user.username_input.setText("nobody")
    unknown_user.password_input.setText("password123")
    unknown_user.submit()

    wrong_password = LoginDialog(data_manager)
    wrong_password.username_input.setText("alice")
    wrong_password.password_input.setText("wrong-password")
    wrong_password.submit()

    assert unknown_user.error_label.text() == wrong_password.error_label.text()


def test_registration_validation_errors_do_not_create_a_user(qapp, data_manager):
    dialog = LoginDialog(data_manager)
    dialog.username_input.setText("alice")
    dialog.password_input.setText("short")
    dialog.confirm_password_input.setText("short")

    dialog.submit()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "at least 8 characters" in dialog.error_label.text()
    assert data_manager.count_claimed_accounts() == 0


def test_registration_rejects_mismatched_confirmation(qapp, data_manager):
    dialog = LoginDialog(data_manager)
    dialog.username_input.setText("alice")
    dialog.password_input.setText("password123")
    dialog.confirm_password_input.setText("password124")

    dialog.submit()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "Passwords do not match." in dialog.error_label.text()
    assert data_manager.count_claimed_accounts() == 0


def test_duplicate_username_is_reported_on_the_form(qapp, data_manager):
    data_manager.register_user("alice", "password123")
    dialog = LoginDialog(data_manager)
    dialog.switch_to_register()
    dialog.username_input.setText("alice")
    dialog.password_input.setText("password123")
    dialog.confirm_password_input.setText("password123")

    dialog.submit()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "already taken" in dialog.error_label.text()


def test_password_fields_are_masked(qapp, data_manager):
    from PyQt6.QtWidgets import QLineEdit

    dialog = LoginDialog(data_manager)

    assert dialog.password_input.echoMode() == QLineEdit.EchoMode.Password
    assert dialog.confirm_password_input.echoMode() == QLineEdit.EchoMode.Password


def test_main_window_defaults_to_user_one_for_backwards_compatibility(qapp, data_manager):
    window = MainWindow(data_manager=data_manager)

    assert window.user_id == 1
    window.close()


def test_main_window_shows_only_the_authenticated_users_receipts(qapp, data_manager):
    alice_id = data_manager.register_user("alice", "password123")
    bob_id = data_manager.register_user("bob", "password123")
    data_manager.add_receipt(
        product_name="Alice Item",
        merchant_name="Shop",
        category_name="Home",
        price_cents=100,
        purchase_date="2026-01-01",
        user_id=alice_id,
    )

    alice_window = MainWindow(data_manager=data_manager, user_id=alice_id, username="alice")
    bob_window = MainWindow(data_manager=data_manager, user_id=bob_id, username="bob")

    assert [c.receipt.product_name for c in alice_window.receipt_cards] == ["Alice Item"]
    assert bob_window.receipt_cards == []
    assert bob_window.dashboard_page.total_receipts_value.text() == "0"
    assert alice_window.dashboard_page.total_receipts_value.text() == "1"
    alice_window.close()
    bob_window.close()


def test_main_window_titles_include_the_signed_in_user(qapp, data_manager):
    window = MainWindow(data_manager=data_manager, user_id=1, username="alice")

    assert "alice" in window.windowTitle()
    window.close()


def test_logout_button_emits_the_logout_signal(qapp, data_manager):
    window = MainWindow(data_manager=data_manager, user_id=1, username="alice")
    received = []
    window.logged_out.connect(lambda: received.append(True))

    window.logout_button.click()

    assert received == [True]
    window.close()


def test_session_controller_uses_one_event_loop_and_returns_to_login_after_logout(
    qapp, data_manager
):
    """Logout must not stop and restart the application's main event loop."""
    data_manager.register_user("alice", "password123")
    quit_calls = []

    controller = SessionController(data_manager, quit_callback=quit_calls.append)
    controller.start()

    assert controller.login_dialog is not None
    assert controller.window is None

    controller.login_dialog.username_input.setText("alice")
    controller.login_dialog.password_input.setText("password123")
    controller.login_dialog.submit()

    assert controller.window is not None
    assert controller.window.user_id == 1
    assert controller.login_dialog is None

    controller.window.logout_button.click()

    assert controller.window is None
    assert controller.login_dialog is not None
    assert quit_calls == []


def test_session_controller_quits_when_login_is_cancelled(qapp, data_manager):
    quit_calls = []
    controller = SessionController(data_manager, quit_callback=quit_calls.append)
    controller.start()

    controller.login_dialog.reject()

    assert len(quit_calls) == 1


def test_session_controller_quits_when_the_main_window_is_closed(qapp, data_manager):
    data_manager.register_user("alice", "password123")
    quit_calls = []
    controller = SessionController(data_manager, quit_callback=quit_calls.append)
    controller.start()
    controller.login_dialog.username_input.setText("alice")
    controller.login_dialog.password_input.setText("password123")
    controller.login_dialog.submit()

    controller.window.close()

    assert len(quit_calls) == 1


def test_logging_in_as_a_different_user_does_not_carry_over_state(qapp, data_manager):
    alice_id = data_manager.register_user("alice", "password123")
    data_manager.register_user("bob", "password123")
    data_manager.add_receipt(
        product_name="Alice Item",
        merchant_name="Shop",
        category_name="Home",
        price_cents=100,
        purchase_date="2026-01-01",
        user_id=alice_id,
    )
    controller = SessionController(data_manager, quit_callback=lambda code=0: None)
    controller.start()
    controller.login_dialog.username_input.setText("alice")
    controller.login_dialog.password_input.setText("password123")
    controller.login_dialog.submit()
    controller.window.search_bar.setText("Alice")

    controller.window.logout_button.click()
    controller.login_dialog.username_input.setText("bob")
    controller.login_dialog.password_input.setText("password123")
    controller.login_dialog.submit()

    assert controller.window.user_id != alice_id
    assert controller.window.search_bar.text() == ""
    assert controller.window.receipt_cards == []
