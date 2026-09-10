"""Interaction regressions for the standard Qt layouts and controls."""

from unittest.mock import Mock

import pytest
from matplotlib.colors import to_hex
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QDialog, QTabWidget

from app.data.data_manager import DataManager
from app.services.receipt_browsing_service import default_filters
from app.ui import receipt_dialog
from app.ui.filter_dialog import FilterDialog
from app.ui.login_dialog import LoginDialog
from app.ui.main_window import MainWindow
from app.ui.receipt_dialog import AddReceiptDialog
from app.ui.trend_chart import SpendingBarChart


def test_tab_navigation_refreshes_data_and_preserves_browse_state(qapp, tmp_path, monkeypatch):
    window = MainWindow(DataManager(tmp_path / "test.db"))
    assert isinstance(window.page_stack, QTabWidget)
    assert [window.page_stack.tabText(i) for i in range(4)] == [
        "Receipts", "Dashboard", "Export", "Settings"
    ]
    window.search_bar.setText("mouse")
    for name, page, method in (
        ("Dashboard", window.dashboard_page, "refresh"),
        ("Export", window.export_page, "refresh"),
        ("Settings", window.settings_page, "load_settings"),
    ):
        refresh = Mock(wraps=getattr(page, method))
        monkeypatch.setattr(page, method, refresh)
        window.page_stack.setCurrentWidget(page)
        refresh.assert_called_once_with()
        assert window.page_stack.currentWidget() is window.pages[name]
    window.show_page("Receipts")
    assert window.search_bar.text() == "mouse"
    window.close()


@pytest.mark.parametrize("kind", ["receipt", "filter", "login"])
def test_enter_accepts_once_and_escape_cancels(qapp, tmp_path, kind):
    manager = DataManager(tmp_path / "test.db")

    def make_dialog():
        if kind == "receipt":
            dialog = AddReceiptDialog()
            for field, value in (("product_name", "Mouse"), ("merchant_name", "Shop"),
                                 ("category_name", "Office"), ("price", "12.34"),
                                 ("purchase_date", "2026-01-01")):
                getattr(dialog, field + "_input").setText(value)
            return dialog, dialog.price_input
        if kind == "filter":
            dialog = FilterDialog(default_filters(), [], [])
            dialog.purchase_date_from.setText("2026-01-01")
            return dialog, dialog.purchase_date_from
        dialog = LoginDialog(manager)
        dialog.username_input.setText("alice")
        dialog.password_input.setText("password123")
        dialog.confirm_password_input.setText("password123")
        return dialog, dialog.password_input

    dialog, field = make_dialog()
    accepted = []
    dialog.accepted.connect(lambda: accepted.append(True))
    dialog.show()
    field.setFocus()
    qapp.processEvents()
    QTest.keyClick(field, Qt.Key.Key_Return)
    assert accepted == [True]
    assert dialog.result() == QDialog.DialogCode.Accepted
    if kind == "receipt":
        assert dialog.cleaned_values["price_cents"] == 1234
    elif kind == "filter":
        assert dialog.values["purchase_date_from"] == "2026-01-01"
    else:
        assert manager.count_claimed_accounts() == 1

    dialog, field = make_dialog()
    rejected = []
    dialog.rejected.connect(lambda: rejected.append(True))
    dialog.show()
    field.setFocus()
    qapp.processEvents()
    QTest.keyClick(field, Qt.Key.Key_Escape)
    assert rejected == [True]
    assert not dialog.isVisible()


def test_invalid_receipt_enter_keeps_form_open_without_copying_image(qapp, monkeypatch):
    copy = Mock()
    monkeypatch.setattr(receipt_dialog, "copy_receipt_image", copy)
    dialog = AddReceiptDialog()
    dialog.selected_image_path = "/tmp/receipt.png"
    dialog.show()
    dialog.price_input.setFocus()
    qapp.processEvents()
    QTest.keyClick(dialog.price_input, Qt.Key.Key_Return)
    assert dialog.isVisible()
    assert dialog.error_label.isVisible()
    assert dialog.error_label.text()
    assert dialog.cleaned_values == {}
    copy.assert_not_called()
    for button in (dialog.scan_image_button, dialog.choose_image_button, dialog.remove_image_button):
        assert not button.autoDefault()
        assert not button.isDefault()
    dialog.close()


def test_gallery_empty_state_survives_filter_and_data_transitions(qapp, tmp_path):
    manager = DataManager(tmp_path / "test.db")
    window = MainWindow(manager)
    window.show()
    qapp.processEvents()
    assert window.empty_state.isVisible()
    receipt_id = manager.add_receipt("Mouse", "Shop", "Office", 1234, "2026-01-01", 0, 0)
    window.load_receipts()
    qapp.processEvents()
    assert not window.empty_state.isVisible()
    old_card = window.receipt_cards[0]
    window.search_bar.setText("absent")
    assert old_card.isHidden()
    qapp.processEvents()
    assert window.empty_state.isVisible()
    assert window.clear_filters_button.isVisible()
    window.clear_filters_button.click()
    qapp.processEvents()
    assert not window.empty_state.isVisible()
    assert len(window.receipt_cards) == 1
    manager.delete_receipt(receipt_id)
    window.load_receipts()
    qapp.processEvents()
    assert window.empty_state.isVisible()
    assert not window.clear_filters_button.isVisible()
    window.close()


def test_thumbnail_can_be_opened_with_keyboard(qapp, tmp_path):
    manager = DataManager(tmp_path / "test.db")
    manager.add_receipt("Mouse", "Shop", "Office", 1234, "2026-01-01", 0, 0,
                        image_path=str(tmp_path / "receipt.png"))
    window = MainWindow(manager)
    card = window.receipt_cards[0]
    viewed = []
    card.on_view_image = viewed.append
    window.show()
    card.image_label.setFocus()
    qapp.processEvents()
    QTest.keyClick(card.image_label, Qt.Key.Key_Return)
    QTest.keyClick(card.image_label, Qt.Key.Key_Space)
    assert viewed == [card.receipt, card.receipt]
    window.close()


def test_chart_follows_application_palette_changes(qapp):
    original = qapp.palette()
    chart = SpendingBarChart()
    chart.show_totals(["2026"], [1234])
    chart.show()
    try:
        for background, foreground, accent in (
            ("#202124", "#eeeeee", "#8ab4f8"),
            ("#f0f0f0", "#202124", "#235faa"),
        ):
            palette = QPalette(original)
            for role, color in ((QPalette.ColorRole.Window, background),
                                (QPalette.ColorRole.WindowText, foreground),
                                (QPalette.ColorRole.Highlight, accent)):
                palette.setColor(role, QColor(color))
            qapp.setPalette(palette)
            qapp.processEvents()
            axes = chart.figure.axes[0]
            assert to_hex(chart.figure.get_facecolor()) == background
            assert to_hex(axes.get_facecolor()) == background
            assert to_hex(axes.yaxis.label.get_color()) == foreground
            assert to_hex(axes.patches[0].get_facecolor()) == accent
            assert chart.cents == [1234]
    finally:
        chart.close()
        qapp.setPalette(original)
        qapp.processEvents()
