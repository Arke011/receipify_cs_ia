"""Settings tab: default warranty/return periods and how early to warn before they end."""

from PyQt6.QtWidgets import QFormLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from receipt import whole_number

# Setting key -> name used in error messages.
SETTING_NAMES = {
    "default_warranty_days": "Default warranty days",
    "default_return_days": "Default return days",
    "warranty_warning_threshold": "Warranty warning threshold",
    "return_warning_threshold": "Return warning threshold",
}
FIELD_LABELS = {
    "default_warranty_days": "Default warranty days",
    "default_return_days": "Default return days",
    "warranty_warning_threshold": "Warranty warning threshold (days)",
    "return_warning_threshold": "Return warning threshold (days)",
}


def validate_settings(texts):
    """Check the settings form's text. Returns (errors, values); values are usable only when errors is empty."""
    errors = []
    values = {key: whole_number(texts[key], name, errors) for key, name in SETTING_NAMES.items()}
    return errors, values


class SettingsPage(QWidget):
    def __init__(self, db, user_id, on_saved):
        super().__init__()
        self.db = db
        self.user_id = user_id
        self.on_saved = on_saved  # called after saving, so views that use the settings can update

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.fields = {}
        for key, label in FIELD_LABELS.items():
            self.fields[key] = QLineEdit()
            form.addRow(label, self.fields[key])
        layout.addLayout(form)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.hide()
        layout.addWidget(self.message)
        buttons = QHBoxLayout()
        buttons.addStretch()
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save)
        buttons.addWidget(save_button)
        layout.addLayout(buttons)
        layout.addStretch()
        self.refresh()

    def refresh(self):
        settings = self.db.get_settings(self.user_id)
        for key, field in self.fields.items():
            field.setText(str(settings[key]))

    def save(self):
        errors, values = validate_settings({key: field.text() for key, field in self.fields.items()})
        if errors:
            self.message.setText("Error: " + "\n".join(errors))
        else:
            self.db.save_settings(self.user_id, values)
            self.message.setText("Settings saved.")
            self.on_saved()
        self.message.show()
