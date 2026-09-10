"""One bar chart for yearly totals or the twelve months of a selected year."""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from PyQt6.QtWidgets import QSizePolicy, QToolTip

from app.ui.formatting import format_currency


class SpendingBarChart(FigureCanvasQTAgg):
    def __init__(self, parent=None):
        super().__init__(Figure(figsize=(5, 3), facecolor="white", layout="constrained"))
        self.setParent(parent)
        self.setMinimumHeight(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self.labels = []
        self.cents = []

    def show_totals(self, labels, cents):
        self.labels, self.cents = list(labels), list(cents)
        self.figure.clear()
        axes = self.figure.add_subplot(111)
        if not self.labels:
            axes.text(0.5, 0.5, "No Spending Data Available", ha="center", va="center",
                      color="#64748B", transform=axes.transAxes)
            axes.set_axis_off()
        else:
            amounts = [value / 100 for value in self.cents]
            axes.bar(range(len(amounts)), amounts, width=0.55, color="#2563EB", zorder=2)
            axes.set_xticks(range(len(amounts)), self.labels)
            axes.set_ylabel("Spending (EUR)", color="#64748B", fontsize=9)
            axes.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:,.2f}"))
            axes.tick_params(colors="#64748B", labelsize=8, length=0)
            axes.set_ylim(0, max(amounts) * 1.16 or 1)
            axes.grid(axis="y", color="#E2E8F0")
            axes.set_axisbelow(True)
            for side in ("top", "right", "left"):
                axes.spines[side].set_visible(False)
            axes.spines["bottom"].set_color("#E2E8F0")
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
