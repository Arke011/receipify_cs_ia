from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from app.services.auth_service import validate_credentials


class LoginDialog(QDialog):
    def __init__(self, data_manager, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.user_id = None
        self.username = None
        # With no claimed account yet this is first run, so there is nothing to log in to.
        self.is_first_run = data_manager.count_claimed_accounts() == 0
        self.is_registering = self.is_first_run
        self.setWindowTitle("Receipify")
        self.setMinimumWidth(360)
        self.resize(400, 200)
        self.build_ui()
        self.apply_mode()

    def build_ui(self):
        layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.confirm_password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.form_layout.addRow("Username", self.username_input)
        self.form_layout.addRow("Password", self.password_input)
        self.form_layout.addRow("Confirm password", self.confirm_password_input)
        layout.addLayout(self.form_layout)
        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)
        # Parented to the dialog before setDefault, or Qt makes Cancel the Enter key's button.
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel, self)
        self.switch_button = buttons.addButton("Create account", QDialogButtonBox.ButtonRole.ActionRole)
        self.switch_button.setAutoDefault(False)
        self.switch_button.clicked.connect(self.toggle_mode)
        self.submit_button = buttons.addButton("Log In", QDialogButtonBox.ButtonRole.AcceptRole)
        self.submit_button.setDefault(True)
        buttons.accepted.connect(self.submit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply_mode(self):
        action = "Create Account" if self.is_registering else "Log In"
        self.setWindowTitle(f"Receipify — {action}")
        self.submit_button.setText(action)
        self.form_layout.setRowVisible(self.confirm_password_input, self.is_registering)
        self.switch_button.setVisible(not self.is_first_run)
        self.switch_button.setText("Log in instead" if self.is_registering else "Create account")
        self.clear_error()
        self.refit()

    def refit(self):
        self.layout().invalidate()
        self.layout().activate()
        self.resize(self.width(), self.sizeHint().height())

    def switch_to_register(self):
        self.is_registering = True
        self.apply_mode()

    def switch_to_login(self):
        self.is_registering = False
        self.apply_mode()

    def toggle_mode(self):
        if self.is_registering:
            self.switch_to_login()
        else:
            self.switch_to_register()

    def submit(self):
        if self.is_registering:
            self.submit_registration()
        else:
            self.submit_login()

    def submit_registration(self):
        is_valid, errors, values = validate_credentials(
            self.username_input.text(),
            self.password_input.text(),
            confirm_password=self.confirm_password_input.text(),
        )
        if not is_valid:
            self.show_error("\n".join(errors))
            return

        try:
            user_id = self.data_manager.register_user(
                values["username"], values["password"]
            )
        except ValueError as error:
            self.show_error(str(error))
            return

        self.finish(user_id, values["username"])

    def submit_login(self):
        username = self.username_input.text()
        user_id = self.data_manager.authenticate_user(username, self.password_input.text())

        if user_id is None:
            # Deliberately identical for unknown users and wrong passwords so the
            # form cannot be used to discover which usernames exist.
            self.show_error("Incorrect username or password.")
            return

        self.finish(user_id, self.data_manager.get_user_by_username(username)["username"])

    def finish(self, user_id, username):
        self.user_id = user_id
        self.username = username
        self.password_input.clear()
        self.confirm_password_input.clear()
        self.accept()

    def show_error(self, message):
        self.error_label.setText(message)
        self.error_label.show()
        self.refit()

    def clear_error(self):
        self.error_label.clear()
        self.error_label.hide()
