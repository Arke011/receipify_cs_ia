def app_stylesheet():
    return """
        QWidget#appRoot {
            background-color: #F4F7FB;
            color: #1E293B;
            font-family: Arial;
            font-size: 14px;
        }

        QWidget#dialogRoot {
            background-color: #FFFFFF;
            color: #1E293B;
            font-family: Arial;
            font-size: 14px;
        }

        QLabel#pageTitle {
            color: #1E293B;
            font-size: 32px;
            font-weight: 800;
            letter-spacing: 0px;
        }

        QLabel#pageSubtitle,
        QLabel#dialogSubtitle,
        QLabel#cardMeta,
        QLabel#mutedText {
            color: #64748B;
        }

        QLabel#dialogTitle {
            color: #1E293B;
            font-size: 24px;
            font-weight: 800;
            letter-spacing: 0px;
        }

        QLineEdit#searchBar {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 16px;
            color: #1E293B;
            font-size: 15px;
            padding: 12px 16px;
        }

        QLineEdit#searchBar:focus {
            border: 1px solid #2563EB;
        }

        QLineEdit#formInput {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            color: #1E293B;
            font-size: 14px;
            padding: 10px 12px;
        }

        QLineEdit#formInput:focus {
            border: 1px solid #2563EB;
        }

        QLabel#fieldLabel {
            color: #334155;
            font-size: 13px;
            font-weight: 700;
        }

        QPushButton {
            border-radius: 12px;
            font-size: 14px;
            font-weight: 800;
            padding: 11px 18px;
        }

        QPushButton#primaryButton {
            background-color: #2563EB;
            border: 1px solid #2563EB;
            color: #FFFFFF;
            min-width: 132px;
        }

        QPushButton#primaryButton:hover {
            background-color: #1D4ED8;
            border-color: #1D4ED8;
        }

        QPushButton#secondaryButton {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            color: #334155;
            min-width: 96px;
        }

        QPushButton#secondaryButton:hover {
            background-color: #F8FAFC;
        }

        QScrollArea#receiptScrollArea {
            background-color: transparent;
            border: none;
        }

        QWidget#galleryWidget {
            background-color: transparent;
        }

        QFrame#receiptCard,
        QFrame#formContainer {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 18px;
        }

        QLabel#cardTitle {
            color: #1E293B;
            font-size: 21px;
            font-weight: 800;
            letter-spacing: 0px;
        }

        QLabel#cardPrice {
            color: #1E293B;
            font-size: 19px;
            font-weight: 800;
        }

        QLabel#detailLabel,
        QLabel#statusLabel {
            color: #64748B;
            font-size: 12px;
            font-weight: 800;
        }

        QLabel#detailValue,
        QLabel#statusDate,
        QLabel#statusDays {
            color: #1E293B;
            font-size: 14px;
        }

        QFrame#statusBlock {
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
        }

        QLabel#statusBadge {
            border-radius: 10px;
            color: #FFFFFF;
            font-size: 12px;
            font-weight: 800;
            padding: 4px 10px;
        }

        QLabel#statusBadge[statusColor="green"] {
            background-color: #16A34A;
        }

        QLabel#statusBadge[statusColor="orange"] {
            background-color: #F59E0B;
        }

        QLabel#statusBadge[statusColor="red"] {
            background-color: #DC2626;
        }

        QLabel#statusBadge[statusColor="grey"] {
            background-color: #94A3B8;
        }

        QLabel#errorLabel {
            color: #DC2626;
            font-size: 13px;
            font-weight: 700;
        }

        QLabel#emptyLabel {
            color: #64748B;
            font-size: 16px;
            padding: 90px 28px;
        }
    """
