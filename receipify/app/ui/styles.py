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

        QLabel#appBrand {
            color: #1E293B;
            font-size: 20px;
            font-weight: 800;
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

        QComboBox#filterCombo {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            color: #334155;
            font-size: 14px;
            padding: 10px 12px;
        }

        QPushButton#filterButton {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 16px;
            color: #1E293B;
            padding: 12px 20px;
            text-align: center;
        }

        QPushButton#filterButton:hover {
            border-color: #2563EB;
            color: #2563EB;
        }

        QPushButton#filterButton[filtersActive="yes"] {
            background-color: #EAF0F8;
            border-color: #2563EB;
            color: #2563EB;
        }

        QComboBox#filterCombo:focus {
            border: 1px solid #2563EB;
        }

        QComboBox#filterCombo::drop-down {
            border: none;
            width: 22px;
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

        QPushButton#navButton {
            background-color: transparent;
            border: 1px solid transparent;
            color: #64748B;
            min-width: 0;
            padding: 8px 12px;
        }

        QPushButton#navButton:hover {
            background-color: #EAF0F8;
            color: #1E293B;
        }

        QPushButton#navButton:checked {
            background-color: #E0EAFC;
            color: #1D4ED8;
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

        QPushButton#panelActionButton {
            background-color: #F1F5F9;
            border: 1px solid #E2E8F0;
            border-radius: 9px;
            color: #334155;
            font-size: 12px;
            font-weight: 800;
            min-width: 0;
            padding: 5px 12px;
        }

        QPushButton#panelActionButton:hover {
            background-color: #E0EAFC;
            border-color: #C7D8F5;
            color: #1D4ED8;
        }

        QPushButton#panelActionButton:disabled {
            color: #94A3B8;
        }

        QPushButton#dangerButton {
            background-color: #FFFFFF;
            border: 1px solid #FECACA;
            color: #DC2626;
            min-width: 96px;
        }

        QPushButton#dangerButton:hover {
            background-color: #FEF2F2;
        }

        QScrollArea#receiptScrollArea {
            background-color: transparent;
            border: none;
        }

        QScrollArea#dashboardScrollArea {
            background-color: transparent;
            border: none;
        }

        QWidget#galleryWidget {
            background-color: transparent;
        }

        QWidget#dashboardContent {
            background-color: transparent;
        }

        QFrame#receiptCard,
        QFrame#formContainer,
        QFrame#dashboardSummaryCard,
        QFrame#dashboardPanel,
        QFrame#exportPanel {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 18px;
        }

        QFrame#imageSelector {
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
        }

        QLabel#imagePreview {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 8px;
            color: #94A3B8;
            font-size: 10px;
            font-weight: 700;
        }

        QLabel#imageName {
            color: #1E293B;
            font-size: 14px;
            font-weight: 700;
        }

        QLabel#imageHint {
            color: #94A3B8;
            font-size: 12px;
        }

        /* The category bars paint themselves: see CategoryBar, which keeps the
           round ends that Qt's own chunk rendering drops on a small fill. Their
           colours live with that class rather than here. */

        QLabel#categoryName {
            color: #1E293B;
            font-size: 13px;
            font-weight: 700;
        }

        QLabel#categoryAmount {
            color: #334155;
            font-size: 13px;
            font-weight: 800;
        }

        QScrollArea#deadlineScrollArea,
        QWidget#deadlineContent {
            background-color: transparent;
            border: none;
        }

        QFrame#deadlineRow {
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
        }

        QLabel#deadlineProduct {
            color: #1E293B;
            font-size: 14px;
            font-weight: 800;
        }

        QLabel#deadlineMeta {
            color: #64748B;
            font-size: 12px;
        }

        QLabel#deadlineDate {
            color: #334155;
            font-size: 13px;
            font-weight: 700;
        }

        QFrame#purchaseRow {
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
        }

        QLabel#purchaseProduct {
            color: #1E293B;
            font-size: 14px;
            font-weight: 800;
        }

        QLabel#purchaseMeta {
            color: #64748B;
            font-size: 12px;
        }

        QLabel#purchasePrice {
            color: #1E293B;
            font-size: 14px;
            font-weight: 800;
        }

        QListWidget#exportList {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 14px;
            color: #1E293B;
            font-size: 14px;
            padding: 6px;
        }

        QListWidget#exportList::item {
            border-bottom: 1px solid #F1F5F9;
            padding: 10px 8px;
        }

        QLabel#dashboardMetricLabel,
        QLabel#dashboardEmpty {
            color: #64748B;
            font-size: 12px;
            font-weight: 700;
        }

        QLabel#dashboardMetricValue {
            color: #1E293B;
            font-size: 24px;
            font-weight: 800;
        }

        QComboBox#chartRangeSelector {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 9px;
            color: #1E293B;
            font-size: 12px;
            font-weight: 700;
            min-width: 172px;
            padding: 5px 10px;
        }

        QComboBox#chartRangeSelector::drop-down {
            border: none;
            width: 22px;
        }

        QPushButton#stepButton {
            background-color: #F1F5F9;
            border: 1px solid #E2E8F0;
            border-radius: 9px;
            color: #334155;
            font-size: 13px;
            font-weight: 800;
            min-width: 0;
            padding: 4px 12px;
        }

        QPushButton#stepButton:hover {
            background-color: #E0EAFC;
            border-color: #C7D8F5;
            color: #1D4ED8;
        }

        QPushButton#stepButton:disabled {
            color: #CBD5E1;
        }

        QLabel#statisticValue {
            color: #1E293B;
            font-size: 20px;
            font-weight: 800;
        }

        QLabel#panelCaption {
            color: #64748B;
            font-size: 12px;
            font-weight: 700;
        }

        QLabel#dashboardPanelTitle {
            color: #1E293B;
            font-size: 16px;
            font-weight: 800;
        }

        QLabel#dashboardItem {
            color: #334155;
            font-size: 13px;
            padding: 5px 0;
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

        QLabel#receiptImage {
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            border-radius: 10px;
            color: #64748B;
            font-size: 11px;
        }

        QLabel#fullReceiptImage {
            background-color: #F8FAFC;
            border: 1px solid #E2E8F0;
            color: #64748B;
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

        QLabel#successLabel {
            color: #16A34A;
            font-size: 13px;
            font-weight: 700;
        }

        QLabel#emptyLabel {
            color: #64748B;
            font-size: 16px;
            padding: 90px 28px;
        }
    """
