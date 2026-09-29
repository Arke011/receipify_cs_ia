"""The log-in / create-account dialog shown when Receipify starts and after logging out."""

import re

from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLabel, QLineEdit, QVBoxLayout

USERNAME_CHARACTERS = re.compile(r"[A-Za-z0-9._-]+")


def validate_credentials(username, password, confirm):
    """Messages for every rule a new username and password break; an empty list means valid."""
    errors = []
    if not username:
        errors.append("Username cannot be empty.")
    elif not 3 <= len(username) <= 32:
        errors.append("Username must be between 3 and 32 characters.")
    elif not USERNAME_CHARACTERS.fullmatch(username):
        errors.append("Username can only contain letters, numbers, dots, hyphens, and underscores.")
    if len(password) < 8:
        errors.append("Password must be at least 8 characters.")
    elif len(password) > 128:
        errors.append("Password must be 128 characters or fewer.")
    if password != confirm:
        errors.append("Passwords do not match.")
    return errors


class LoginDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.user_id = None  # set once the user has logged in or registered
        self.username = None
        self.first_run = not db.has_users()  # with no accounts yet there is nothing to log in to
        self.setMinimumWidth(360)
        self.resize(400, 200)

        layout = QVBoxLayout(self)
        self.form = QFormLayout()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.confirm_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.form.addRow("Username", self.username_input)
        self.form.addRow("Password", self.password_input)
        self.form.addRow("Confirm password", self.confirm_input)
        layout.addLayout(self.form)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        # Parented to the dialog before setDefault, or Qt makes Cancel the Enter key's button.
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, self)
        self.switch_button = buttons.addButton("Create account", QDialogButtonBox.ButtonRole.ActionRole)
        self.switch_button.setAutoDefault(False)
        self.switch_button.clicked.connect(lambda: self.set_mode(not self.registering))
        self.submit_button = buttons.addButton("Log In", QDialogButtonBox.ButtonRole.AcceptRole)
        self.submit_button.setDefault(True)
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.set_mode(registering=self.first_run)

    def set_mode(self, registering):
        self.registering = registering
        action = "Create Account" if registering else "Log In"
        self.setWindowTitle(f"Receipify — {action}")
        self.submit_button.setText(action)
        self.form.setRowVisible(self.confirm_input, registering)
        self.switch_button.setVisible(not self.first_run)
        self.switch_button.setText("Log in instead" if registering else "Create account")
        self.error_label.hide()
        self.fit_height()

    def fit_height(self):
        """Resize to the content, so showing or hiding a row does not stretch the others apart."""
        self.layout().invalidate()
        self.layout().activate()
        self.resize(self.width(), self.sizeHint().height())

    def submit(self):
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if self.registering:
            errors = validate_credentials(username, password, self.confirm_input.text())
            if errors:
                self.show_error("\n".join(errors))
                return
            try:
                user_id = self.db.register(username, password)
            except ValueError as error:
                self.show_error(str(error))
                return
        else:
            user = self.db.log_in(username, password)
            if user is None:
                # The same message for an unknown username and a wrong password,
                # so the form cannot be used to find out which usernames exist.
                self.show_error("Incorrect username or password.")
                return
            user_id, username = user["user_id"], user["username"]
        self.user_id, self.username = user_id, username
        self.password_input.clear()
        self.confirm_input.clear()
        self.accept()

    def show_error(self, message):
        self.error_label.setText(message)
        self.error_label.show()
        self.fit_height()
