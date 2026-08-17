"""A small full-size viewer for a receipt's stored image."""

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout

from app.services.image_service import resolve_image_path


class ReceiptImageViewer(QDialog):
    def __init__(self, image_path, parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.original_pixmap = QPixmap()
        self.setWindowTitle("Receipt image")
        self.resize(840, 620)
        self.setMinimumSize(420, 320)

        layout = QVBoxLayout(self)
        self.image_label = QLabel()
        self.image_label.setObjectName("fullReceiptImage")
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setWordWrap(True)
        layout.addWidget(self.image_label, stretch=1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.load_image()

    def load_image(self):
        if not self.image_path:
            self.image_label.setText("No image is attached to this receipt.")
            return

        path = resolve_image_path(self.image_path)
        if not path.is_file():
            self.image_label.setText("This receipt image is unavailable.")
            return

        self.original_pixmap = QPixmap(str(path))
        if self.original_pixmap.isNull():
            self.image_label.setText("This receipt image could not be read.")
            return
        self.scale_image()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self.original_pixmap.isNull():
            self.scale_image()

    def scale_image(self):
        available_size = self.image_label.size()
        self.image_label.setPixmap(
            self.original_pixmap.scaled(
                available_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
