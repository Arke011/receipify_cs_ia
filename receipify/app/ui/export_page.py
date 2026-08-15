from pathlib import Path

from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.services.export_service import export_user_receipts


class ExportPage(QWidget):
    def __init__(self, data_manager, user_id, parent=None):
        super().__init__(parent)
        self.data_manager = data_manager
        self.user_id = user_id
        self.build_ui()

    def build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        title = QLabel("Export")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        subtitle = QLabel("Save a copy of your receipt data in a portable format.")
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(subtitle)

        panel = QFrame()
        panel.setObjectName("exportPanel")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(22, 20, 22, 20)
        panel_layout.setSpacing(12)
        layout.addWidget(panel)

        panel_title = QLabel("Export all receipts")
        panel_title.setObjectName("dashboardPanelTitle")
        panel_layout.addWidget(panel_title)

        description = QLabel(
            "Choose CSV for spreadsheets or JSON for structured data. "
            "Only receipts from the current user are included."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        panel_layout.addWidget(description)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        panel_layout.addLayout(button_layout)

        csv_button = QPushButton("Export CSV")
        csv_button.setObjectName("primaryButton")
        csv_button.clicked.connect(lambda: self.export_receipts("csv"))
        button_layout.addWidget(csv_button)

        json_button = QPushButton("Export JSON")
        json_button.setObjectName("secondaryButton")
        json_button.clicked.connect(lambda: self.export_receipts("json"))
        button_layout.addWidget(json_button)
        button_layout.addStretch(1)
        layout.addStretch(1)

    def export_receipts(self, export_format):
        extension = f".{export_format}"
        selected_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export receipts as {export_format.upper()}",
            f"receipify-receipts{extension}",
            f"{export_format.upper()} files (*{extension})",
        )
        if not selected_path:
            return

        output_path = Path(selected_path)
        if output_path.suffix.lower() != extension:
            output_path = output_path.with_suffix(extension)

        try:
            receipt_count = export_user_receipts(
                self.data_manager,
                self.user_id,
                output_path,
                export_format,
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Export failed", f"Could not export receipts: {error}")
            return

        QMessageBox.information(
            self,
            "Export complete",
            f"Exported {receipt_count} receipt(s) to:\n{output_path}",
        )
