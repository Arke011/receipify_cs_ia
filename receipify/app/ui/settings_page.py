from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.settings_service import validate_settings


class SettingsPage(QWidget):
    def __init__(self, data_manager, user_id, on_settings_saved=None, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.user_id = user_id
        self.on_settings_saved = on_settings_saved
        self.build_ui()
        self.load_settings()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        title = QLabel("Settings")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel("Set the default periods and reminder thresholds for new receipts.")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        form_container = QFrame()
        form_container.setObjectName("formContainer")
        form_layout = QHBoxLayout(form_container)
        form_layout.setContentsMargins(22, 22, 22, 22)
        form_layout.setSpacing(18)
        layout.addWidget(form_container)

        left_column = QVBoxLayout()
        right_column = QVBoxLayout()
        form_layout.addLayout(left_column, stretch=1)
        form_layout.addLayout(right_column, stretch=1)

        self.default_warranty_input = self.create_input()
        self.default_return_input = self.create_input()
        self.warranty_threshold_input = self.create_input()
        self.return_threshold_input = self.create_input()
        left_column.addWidget(
            self.create_field("Default warranty days", self.default_warranty_input)
        )
        left_column.addWidget(
            self.create_field("Default return days", self.default_return_input)
        )
        right_column.addWidget(
            self.create_field("Warranty warning threshold (days)", self.warranty_threshold_input)
        )
        right_column.addWidget(
            self.create_field("Return warning threshold (days)", self.return_threshold_input)
        )

        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.hide()
        layout.addWidget(self.message_label)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        layout.addLayout(button_layout)
        save_button = QPushButton("Save Settings")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self.save_settings)
        button_layout.addWidget(save_button)
        layout.addStretch(1)

    def create_input(self):
        input_widget = QLineEdit()
        input_widget.setObjectName("formInput")
        input_widget.setMinimumHeight(42)
        return input_widget

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
            self.show_message("\n".join(errors), "errorLabel")
            return

        self.data_manager.save_settings(user_id=self.user_id, **values)
        self.show_message("Settings saved.", "successLabel")
        if self.on_settings_saved is not None:
            self.on_settings_saved()

    def show_message(self, message, object_name):
        self.message_label.setText(message)
        self.message_label.setObjectName(object_name)
        # Qt does not re-evaluate stylesheet selectors when objectName changes,
        # so the widget has to be repolished for the new rule to take effect.
        self.message_label.style().unpolish(self.message_label)
        self.message_label.style().polish(self.message_label)
        self.message_label.show()
