from PyQt6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.services.settings_service import validate_settings


class SettingsPage(QWidget):
    def __init__(self, data_manager, user_id, on_settings_saved=None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.user_id = user_id
        self.on_settings_saved = on_settings_saved
        layout = QVBoxLayout(self)
        form = QFormLayout()
        for attribute, label in (
            ("default_warranty_input", "Default warranty days"),
            ("default_return_input", "Default return days"),
            ("warranty_threshold_input", "Warranty warning threshold (days)"),
            ("return_threshold_input", "Return warning threshold (days)"),
        ):
            field = QLineEdit()
            setattr(self, attribute, field)
            form.addRow(label, field)
        layout.addLayout(form)
        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        layout.addWidget(self.message_label)
        buttons = QHBoxLayout()
        buttons.addStretch()
        save = QPushButton("Save")
        save.clicked.connect(self.save_settings)
        buttons.addWidget(save)
        layout.addLayout(buttons)
        layout.addStretch()
        self.load_settings()

    def load_settings(self):
        settings = self.data_manager.get_settings(self.user_id)
        self.default_warranty_input.setText(str(settings["default_warranty_days"]))
        self.default_return_input.setText(str(settings["default_return_days"]))
        self.warranty_threshold_input.setText(
            str(settings["warranty_warning_threshold"])
        )
        self.return_threshold_input.setText(str(settings["return_warning_threshold"]))

    def save_settings(self):
        is_valid, errors, values = validate_settings(
            self.default_warranty_input.text(),
            self.default_return_input.text(),
            self.warranty_threshold_input.text(),
            self.return_threshold_input.text(),
        )
        if not is_valid:
            self.show_message("\n".join(errors), is_error=True)
            return

        self.data_manager.save_settings(user_id=self.user_id, **values)
        self.show_message("Settings saved.")
        if self.on_settings_saved is not None:
            self.on_settings_saved()

    def show_message(self, message, is_error=False):
        self.message_label.setText(("Error: " if is_error else "") + message)
        self.message_label.show()
