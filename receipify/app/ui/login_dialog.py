from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.auth_service import validate_credentials
from app.ui.styles import app_stylesheet


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
        self.setMinimumWidth(420)
        self.build_ui()
        self.apply_mode()
        self.setStyleSheet(app_stylesheet())

    def build_ui(self):
        root = QWidget()
        root.setObjectName("dialogRoot")

        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(26, 24, 26, 24)
        root_layout.setSpacing(18)

        self.title_label = QLabel()
        self.title_label.setObjectName("dialogTitle")
        root_layout.addWidget(self.title_label)

        self.subtitle_label = QLabel()
        self.subtitle_label.setObjectName("dialogSubtitle")
        self.subtitle_label.setWordWrap(True)
        root_layout.addWidget(self.subtitle_label)

        form_container = QFrame()
        form_container.setObjectName("formContainer")
        form_layout = QVBoxLayout(form_container)
        form_layout.setContentsMargins(22, 22, 22, 22)
        form_layout.setSpacing(14)
        root_layout.addWidget(form_container)

        self.username_input = self.create_input("e.g. alex")
        self.password_input = self.create_input("Your password", is_password=True)
        self.confirm_password_input = self.create_input(
            "Repeat your password", is_password=True
        )

        form_layout.addWidget(self.create_field("Username", self.username_input))
        form_layout.addWidget(self.create_field("Password", self.password_input))
        self.confirm_field = self.create_field(
            "Confirm password", self.confirm_password_input
        )
        form_layout.addWidget(self.confirm_field)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root_layout.addWidget(self.error_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        root_layout.addLayout(button_row)

        self.switch_button = QPushButton()
        self.switch_button.setObjectName("secondaryButton")
        self.switch_button.clicked.connect(self.toggle_mode)
        button_row.addWidget(self.switch_button)
        button_row.addStretch(1)

        self.submit_button = QPushButton()
        self.submit_button.setObjectName("primaryButton")
        self.submit_button.setDefault(True)
        self.submit_button.clicked.connect(self.submit)
        button_row.addWidget(self.submit_button)

        for field in (self.username_input, self.password_input, self.confirm_password_input):
            field.returnPressed.connect(self.submit)

        dialog_layout = QVBoxLayout(self)
        dialog_layout.setContentsMargins(0, 0, 0, 0)
        dialog_layout.addWidget(root)

    def create_field(self, label_text, input_widget):
        field = QWidget()
        layout = QVBoxLayout(field)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        layout.addWidget(input_widget)

        return field

    def create_input(self, placeholder, is_password=False):
        input_widget = QLineEdit()
        input_widget.setObjectName("formInput")
        input_widget.setPlaceholderText(placeholder)
        input_widget.setMinimumHeight(42)
        if is_password:
            input_widget.setEchoMode(QLineEdit.EchoMode.Password)
        return input_widget

    def apply_mode(self):
        if self.is_registering:
            self.title_label.setText(
                "Welcome to Receipify" if self.is_first_run else "Create Account"
            )
            self.subtitle_label.setText(
                "Create your account to start tracking receipts. Your existing "
                "receipts will be kept."
                if self.is_first_run
                else "Choose a username and password for the new account."
            )
            self.submit_button.setText("Create Account")
        else:
            self.title_label.setText("Log In")
            self.subtitle_label.setText("Enter your credentials to open your receipts.")
            self.submit_button.setText("Log In")

        self.confirm_field.setVisible(self.is_registering)
        # On first run there is no other account to switch to.
        self.switch_button.setVisible(not self.is_first_run)
        self.switch_button.setText("Log in instead" if self.is_registering else "Create account")
        self.clear_error()

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

    def clear_error(self):
        self.error_label.clear()
        self.error_label.hide()
