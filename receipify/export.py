"""Export tab: choose receipts and save them as a CSV or JSON file."""

import csv
import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

FIELDS = (
    "product_name", "merchant", "category", "price", "purchase_date", "warranty_days", "return_days",
    "warranty_expiry_date", "return_expiry_date", "warranty_status", "return_status", "image_path", "created_at",
)


def export_row(receipt, settings):
    return {
        "product_name": receipt.product,
        "merchant": receipt.merchant,
        "category": receipt.category,
        "price": f"{receipt.price_cents / 100:.2f}",
        "purchase_date": receipt.purchase_date,
        "warranty_days": receipt.warranty_days,
        "return_days": receipt.return_days,
        "warranty_expiry_date": receipt.warranty_expiry(),
        "return_expiry_date": receipt.return_expiry(),
        "warranty_status": receipt.warranty_status(settings["warranty_warning_threshold"]),
        "return_status": receipt.return_status(settings["return_warning_threshold"]),
        "image_path": receipt.image_path,
        "created_at": receipt.created_at,
    }


def write_export(receipts, path, file_format, settings):
    """Write the receipts to path as 'csv' or 'json'."""
    rows = [export_row(receipt, settings) for receipt in receipts]
    if file_format == "csv":
        with Path(path).open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
    else:
        Path(path).write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


class ExportPage(QWidget):
    def __init__(self, db, user_id):
        super().__init__()
        self.db = db
        self.user_id = user_id
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Choose receipts to export:"))

        selection_row = QHBoxLayout()
        selection_row.setSpacing(10)
        self.select_all_button = QPushButton("Select all")
        self.select_all_button.clicked.connect(lambda: self.tick_all(True))
        self.select_none_button = QPushButton("Select none")
        self.select_none_button.clicked.connect(lambda: self.tick_all(False))
        self.selection_label = QLabel()
        selection_row.addWidget(self.select_all_button)
        selection_row.addWidget(self.select_none_button)
        selection_row.addWidget(self.selection_label)
        selection_row.addStretch(1)
        layout.addLayout(selection_row)

        self.receipt_list = QListWidget()
        self.receipt_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.receipt_list.itemChanged.connect(self.update_buttons)
        layout.addWidget(self.receipt_list, stretch=1)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)
        self.csv_button = QPushButton("Export CSV")
        self.csv_button.clicked.connect(lambda: self.export("csv"))
        self.json_button = QPushButton("Export JSON")
        self.json_button.clicked.connect(lambda: self.export("json"))
        button_row.addWidget(self.csv_button)
        button_row.addWidget(self.json_button)
        button_row.addStretch(1)
        layout.addLayout(button_row)
        self.refresh()

    def items(self):
        return [self.receipt_list.item(row) for row in range(self.receipt_list.count())]

    def ticked_receipts(self):
        return [item.data(Qt.ItemDataRole.UserRole) for item in self.items()
                if item.checkState() == Qt.CheckState.Checked]

    def refresh(self):
        """Reload the list. Receipts the user unticked stay unticked; new receipts start ticked."""
        unticked = {item.data(Qt.ItemDataRole.UserRole).id for item in self.items()
                    if item.checkState() == Qt.CheckState.Unchecked}
        self.receipt_list.blockSignals(True)
        self.receipt_list.clear()
        for receipt in self.db.receipts(self.user_id):
            item = QListWidgetItem(f"{receipt.product}  ·  {receipt.merchant}  ·  "
                                   f"{receipt.purchase_date}  ·  EUR {receipt.price_cents / 100:.2f}")
            item.setData(Qt.ItemDataRole.UserRole, receipt)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked if receipt.id in unticked else Qt.CheckState.Checked)
            self.receipt_list.addItem(item)
        self.receipt_list.blockSignals(False)
        self.update_buttons()

    def tick_all(self, ticked):
        state = Qt.CheckState.Checked if ticked else Qt.CheckState.Unchecked
        self.receipt_list.blockSignals(True)
        for item in self.items():
            item.setCheckState(state)
        self.receipt_list.blockSignals(False)
        self.update_buttons()

    def update_buttons(self):
        total = self.receipt_list.count()
        ticked = len(self.ticked_receipts())
        self.selection_label.setText(f"{ticked} of {total} selected" if total else "No receipts to export yet.")
        self.select_all_button.setEnabled(total > 0)
        self.select_none_button.setEnabled(total > 0)
        self.csv_button.setEnabled(ticked > 0)
        self.json_button.setEnabled(ticked > 0)

    def export(self, file_format):
        extension = "." + file_format
        chosen, _ = QFileDialog.getSaveFileName(
            self, f"Export receipts as {file_format.upper()}", f"receipify-receipts{extension}",
            f"{file_format.upper()} files (*{extension})",
        )
        if not chosen:
            return
        path = Path(chosen)
        if path.suffix.lower() != extension:
            path = path.with_suffix(extension)
        receipts = self.ticked_receipts()
        try:
            write_export(receipts, path, file_format, self.db.get_settings(self.user_id))
        except OSError as error:
            QMessageBox.critical(self, "Export failed", f"Could not export receipts: {error}")
            return
        QMessageBox.information(self, "Export complete", f"Exported {len(receipts)} receipt(s) to:\n{path}")
