import sys

from PyQt6.QtWidgets import QApplication

from app.data.data_manager import DataManager
from app.ui.session_controller import SessionController


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    session = SessionController(DataManager(), quit_callback=app.exit)
    session.start()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
