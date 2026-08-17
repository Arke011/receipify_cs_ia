"""Drives login -> main window -> logout -> login inside a single event loop.

The login dialog is opened non-modally with ``open()`` and observed through its
accepted/rejected signals, so the application's one ``QApplication.exec()`` call
is never stopped and restarted.
"""

from app.ui.login_dialog import LoginDialog
from app.ui.main_window import MainWindow


class SessionController:
    def __init__(self, data_manager, quit_callback):
        self.data_manager = data_manager
        self.quit_callback = quit_callback
        self.login_dialog = None
        self.window = None
        self.is_logging_out = False

    def start(self):
        self.show_login()

    def show_login(self):
        self.login_dialog = LoginDialog(self.data_manager)
        self.login_dialog.accepted.connect(self.open_main_window)
        self.login_dialog.rejected.connect(self.quit)
        self.login_dialog.open()
        # After a log out the main window has just closed, so the dialog has to
        # ask for the window focus rather than wait to be found behind others.
        self.login_dialog.raise_()
        self.login_dialog.activateWindow()
        self.login_dialog.username_input.setFocus()

    def open_main_window(self):
        dialog = self.login_dialog
        self.login_dialog = None

        self.window = MainWindow(
            data_manager=self.data_manager,
            user_id=dialog.user_id,
            username=dialog.username,
        )
        self.window.logged_out.connect(self.log_out)
        self.window.closed.connect(self.on_window_closed)
        self.window.show()

        dialog.deleteLater()

    def log_out(self):
        window = self.window
        self.window = None

        # Closing the window emits `closed`, which must not be treated as a quit.
        self.is_logging_out = True
        window.close()
        self.is_logging_out = False
        window.deleteLater()

        self.show_login()

    def on_window_closed(self):
        if not self.is_logging_out:
            self.quit()

    def quit(self):
        self.quit_callback(0)
