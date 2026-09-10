from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QDialog, QToolTip

from app.ui.trend_chart import SpendingBarChart


def test_chart_renders_amounts_and_currency(qapp):
    chart = SpendingBarChart()
    chart.show_totals(["2024", "2025", "2026"], [1234, 0, 99])
    axes = chart.figure.axes[0]
    assert [bar.get_height() for bar in axes.patches] == [12.34, 0, 0.99]
    assert [label.get_text() for label in axes.get_xticklabels()] == ["2024", "2025", "2026"]
    assert axes.get_ylabel() == "Spending (EUR)"


def test_clicking_chart_opens_no_dialog(qapp):
    chart = SpendingBarChart()
    chart.show_totals(["Jan", "Feb"], [100, 200])
    chart.show()
    qapp.processEvents()
    before = {widget for widget in QApplication.topLevelWidgets() if isinstance(widget, QDialog)}
    QTest.mouseClick(chart, Qt.MouseButton.LeftButton)
    QTest.mouseDClick(chart, Qt.MouseButton.LeftButton)
    qapp.processEvents()
    assert {widget for widget in QApplication.topLevelWidgets() if isinstance(widget, QDialog)} == before
    assert chart.labels == ["Jan", "Feb"]
    chart.close()


def test_hover_shows_exact_amount(qapp, monkeypatch):
    from PyQt6.QtCore import QPoint

    chart = SpendingBarChart()
    chart.show_totals(["2026"], [123456])
    chart.show()
    chart.draw()
    shown = []
    monkeypatch.setattr(QToolTip, "showText", lambda position, text, widget: shown.append(text))
    x, y = chart.figure.axes[0].transData.transform((0, 500))
    QTest.mouseMove(chart, QPoint(round(x / chart.device_pixel_ratio), round(chart.height() - y / chart.device_pixel_ratio)))
    assert shown[-1] == "2026: EUR 1,234.56"
    chart.close()
