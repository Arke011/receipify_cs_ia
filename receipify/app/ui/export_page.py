from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
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
        self.refresh()

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
        layout.addWidget(panel, stretch=1)

        panel_title = QLabel("Choose receipts to export")
        panel_title.setObjectName("dashboardPanelTitle")
        panel_layout.addWidget(panel_title)

        description = QLabel(
            "Tick the receipts to include, then choose CSV for spreadsheets or "
            "JSON for structured data."
        )
        description.setObjectName("mutedText")
        description.setWordWrap(True)
        panel_layout.addWidget(description)

        selection_row = QHBoxLayout()
        selection_row.setSpacing(10)
        panel_layout.addLayout(selection_row)

        self.select_all_button = QPushButton("Select all")
        self.select_all_button.setObjectName("secondaryButton")
        self.select_all_button.clicked.connect(lambda: self.set_all_checked(True))
        selection_row.addWidget(self.select_all_button)

        self.select_none_button = QPushButton("Select none")
        self.select_none_button.setObjectName("secondaryButton")
        self.select_none_button.clicked.connect(lambda: self.set_all_checked(False))
        selection_row.addWidget(self.select_none_button)

        self.selection_label = QLabel()
        self.selection_label.setObjectName("mutedText")
        selection_row.addWidget(self.selection_label)
        selection_row.addStretch(1)

        self.receipt_list = QListWidget()
        self.receipt_list.setObjectName("exportList")
        self.receipt_list.setSelectionMode(
            QAbstractItemView.SelectionMode.NoSelection
        )
        self.receipt_list.itemChanged.connect(self.update_selection_state)
        panel_layout.addWidget(self.receipt_list, stretch=1)

        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        panel_layout.addLayout(button_layout)

        self.csv_button = QPushButton("Export CSV")
        self.csv_button.setObjectName("primaryButton")
        self.csv_button.clicked.connect(lambda: self.export_receipts("csv"))
        button_layout.addWidget(self.csv_button)

        self.json_button = QPushButton("Export JSON")
        self.json_button.setObjectName("secondaryButton")
        self.json_button.clicked.connect(lambda: self.export_receipts("json"))
        button_layout.addWidget(self.json_button)
        button_layout.addStretch(1)

    def refresh(self):
        """Rebuild the list from the database.

        Receipts the user deliberately unticked stay unticked; everything else,
        including a receipt added since the last visit, is ready to export.
        """
        excluded_ids = {
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.items()
            if item.checkState() == Qt.CheckState.Unchecked
        }

        self.receipt_list.blockSignals(True)
        self.receipt_list.clear()
        for receipt in self.data_manager.get_all_receipts(self.user_id):
            item = QListWidgetItem(self.describe(receipt))
            item.setData(Qt.ItemDataRole.UserRole, receipt.receipt_id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Unchecked
                if receipt.receipt_id in excluded_ids
                else Qt.CheckState.Checked
            )
            self.receipt_list.addItem(item)
        self.receipt_list.blockSignals(False)

        self.update_selection_state()

    @staticmethod
    def describe(receipt):
        return (
            f"{receipt.product_name}  ·  {receipt.merchant_name}  ·  "
            f"{receipt.purchase_date}  ·  EUR {receipt.price_euros():.2f}"
        )

    def items(self):
        return [self.receipt_list.item(row) for row in range(self.receipt_list.count())]

    def selected_receipt_ids(self):
        return [
            item.data(Qt.ItemDataRole.UserRole)
            for item in self.items()
            if item.checkState() == Qt.CheckState.Checked
        ]

    def set_all_checked(self, is_checked):
        state = Qt.CheckState.Checked if is_checked else Qt.CheckState.Unchecked
        self.receipt_list.blockSignals(True)
        for item in self.items():
            item.setCheckState(state)
        self.receipt_list.blockSignals(False)
        self.update_selection_state()

    def update_selection_state(self, _item=None):
        total = self.receipt_list.count()
        selected = len(self.selected_receipt_ids())

        if total == 0:
            self.selection_label.setText("No receipts to export yet.")
        else:
            self.selection_label.setText(f"{selected} of {total} selected")

        for button in (
            self.csv_button,
            self.json_button,
            self.select_all_button,
            self.select_none_button,
        ):
            button.setEnabled(total > 0)
        self.csv_button.setEnabled(selected > 0)
        self.json_button.setEnabled(selected > 0)

    def export_receipts(self, export_format):
        receipt_ids = self.selected_receipt_ids()
        if not receipt_ids:
            QMessageBox.information(
                self,
                "Nothing selected",
                "Tick at least one receipt to export.",
            )
            return

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
                receipt_ids=receipt_ids,
            )
        except (OSError, ValueError) as error:
            QMessageBox.critical(self, "Export failed", f"Could not export receipts: {error}")
            return

        QMessageBox.information(
            self,
            "Export complete",
            f"Exported {receipt_count} receipt(s) to:\n{output_path}",
        )
