"""One bar chart for yearly totals or the twelve months of a selected year."""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from PyQt6.QtCore import QEvent
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QSizePolicy, QToolTip

from app.ui.formatting import format_currency


class SpendingBarChart(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        super().__init__(Figure(figsize=(5, 3), layout="constrained"))
        self.setParent(parent)
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.labels = []
        self.cents = []

    def show_totals(self, labels, cents):
        self.labels, self.cents = list(labels), list(cents)
        self.figure.clear()
        # Matplotlib gives its canvas a white palette; use the application's
        # palette so the figure follows the surrounding native controls.
        palette = QApplication.palette()
        background = palette.color(QPalette.ColorRole.Window).name()
        foreground = palette.color(QPalette.ColorRole.WindowText).name()
        accent = palette.color(QPalette.ColorRole.Highlight).name()
        self.figure.set_facecolor(background)
        axes = self.figure.add_subplot(111)
        axes.set_facecolor(background)
        if not self.labels:
            axes.text(0.5, 0.5, "No Spending Data Available", ha="center", va="center",
                      color=foreground, transform=axes.transAxes)
            axes.set_axis_off()
        else:
            amounts = [value / 100 for value in self.cents]
            axes.bar(range(len(amounts)), amounts, width=0.55, color=accent, zorder=2)
            axes.set_xticks(range(len(amounts)), self.labels)
            axes.set_ylabel("Spending (EUR)", color=foreground, fontsize=9)
            axes.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.2f}"))
            axes.tick_params(colors=foreground, labelsize=8, length=0)
            axes.set_ylim(0, max(amounts) * 1.16 or 1)
            axes.grid(axis="y", color=foreground, alpha=0.2)
            axes.set_axisbelow(True)
            for side in ("top", "right", "left"):
                axes.spines[side].set_visible(False)
            axes.spines["bottom"].set_color(foreground)
        self.draw_idle()

    def mouseMoveEvent(self, event):
        """Show the exact amount without opening a window or navigating."""
        super().mouseMoveEvent(event)
        if self.labels:
            axes = self.figure.axes[0]
            x, y = event.position().x(), event.position().y()
            point = (x * self.device_pixel_ratio, (self.height() - y) * self.device_pixel_ratio)
            if axes.bbox.contains(*point):
                slot = round(axes.transData.inverted().transform(point)[0])
                if 0 <= slot < len(self.labels):
                    QToolTip.showText(event.globalPosition().toPoint(),
                                      f"{self.labels[slot]}: {format_currency(self.cents[slot])}", self)
                    return
        QToolTip.hideText()

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() in (QEvent.Type.PaletteChange, QEvent.Type.ApplicationPaletteChange) and hasattr(self, "labels"):
            self.show_totals(self.labels, self.cents)
