import pytest
from PyQt6.QtWidgets import QDialog

from login import LoginDialog, validate_credentials
from main import Session


@pytest.mark.parametrize(("username", "password", "confirm", "message"), [
    ("", "password123", "password123", "Username cannot be empty."),
    ("ab", "password123", "password123", "Username must be between 3 and 32 characters."),
    ("has space", "password123", "password123",
     "Username can only contain letters, numbers, dots, hyphens, and underscores."),
    ("alice", "short", "short", "Password must be at least 8 characters."),
    ("alice", "password123", "password124", "Passwords do not match."),
])
def test_credential_rules(username, password, confirm, message):
    assert validate_credentials(username, password, confirm) == [message]


def test_first_run_creates_an_account(empty_db):
    dialog = LoginDialog(empty_db)
    assert dialog.registering
    assert dialog.submit_button.text() == "Create Account"
    dialog.username_input.setText("  alice ")
    dialog.password_input.setText("password123")
    dialog.confirm_input.setText("password123")
    dialog.submit()
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert (dialog.user_id, dialog.username) == (1, "alice")


def test_failed_login_does_not_reveal_which_usernames_exist(db):
    messages = []
    for username, password in (("alice", "wrong-password"), ("nobody", "password123")):
        dialog = LoginDialog(db)
        assert not dialog.registering
        dialog.username_input.setText(username)
        dialog.password_input.setText(password)
        dialog.submit()
        assert dialog.result() != QDialog.DialogCode.Accepted
        messages.append(dialog.error_label.text())
    assert messages == ["Incorrect username or password."] * 2


def log_in(session, username="alice", password="password123"):
    session.login.username_input.setText(username)
    session.login.password_input.setText(password)
    session.login.submit()


def test_log_in_log_out_and_quit(db):
    quits = []
    session = Session(db, quits.append)
    session.show_login()
    log_in(session)
    assert session.window.user_id == 1
    assert session.login is None

    session.window.logout_button.click()
    assert session.window is None
    assert session.login.password_input.text() == ""  # the password is needed again
    assert quits == []  # logging out does not quit

    log_in(session)
    session.window.close()
    assert quits == [0]


def test_cancelling_the_login_quits(db):
    quits = []
    session = Session(db, quits.append)
    session.show_login()
    session.login.reject()
    assert quits == [0]
