"""Starts Receipify: log in, use the main window, and return to the login after logging out."""

import sys

from PyQt6.QtWidgets import QApplication

from database import Database
from login import LoginDialog
from main_window import MainWindow


class Session:
    """Switches between the login dialog and the main window inside Qt's single event loop."""

    def __init__(self, db, quit_app):
        self.db = db
        self.quit_app = quit_app
        self.login = None
        self.window = None

    def show_login(self):
        self.login = LoginDialog(self.db)
        self.login.accepted.connect(self.open_window)
        self.login.rejected.connect(self.quit)
        self.login.open()  # non-modal, so the event loop never has to be stopped and restarted
        # After a log out the main window has just closed, so ask for focus instead of hiding behind other windows.
        self.login.raise_()
        self.login.activateWindow()
        self.login.username_input.setFocus()

    def open_window(self):
        dialog, self.login = self.login, None
        self.window = MainWindow(self.db, dialog.user_id, dialog.username)
        self.window.logged_out.connect(self.log_out)
        self.window.closed.connect(self.quit)
        self.window.show()
        dialog.deleteLater()

    def log_out(self):
        window, self.window = self.window, None
        window.closed.disconnect(self.quit)  # this close is a log out, not a quit
        window.close()
        window.deleteLater()
        self.show_login()

    def quit(self):
        self.quit_app(0)


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # the app quits through Session.quit instead
    db = Database()
    session = Session(db, app.exit)
    session.show_login()
    exit_code = app.exec()
    db.close()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
