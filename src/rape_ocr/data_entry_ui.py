from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

from .template_service import DocxTemplateService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
DEFAULT_TEMPLATE_PATH = BUNDLE_ROOT / "docs" / "example" / "prototype.docx"
DEFAULT_OUTPUT_PATH = Path.home() / "Documents" / "generated.docx"
ENTRY_KEYS = tuple([f"i{index}" for index in range(1, 10)] + [f"R{index}" for index in range(1, 4)])
FIELD_LABELS = {
    "i1": "Lab No",
    "i2": "Name",
    "i3": "Age",
    "i4": "HN",
    "i5": "Hospital",
    "i6": "Collection date",
    "i7": "Collection time",
    "i8": "Received date",
    "i9": "Reported Date",
    "R1": "Vulvar",
    "R2": "Vaginal",
    "R3": "Endocervical",
}
HOSPITAL_OPTIONS = (
    "",
    "โรงพยาบาลพระปกเกล้า",
    "โรงพยาบาลโป่งน้ำร้อน",
    "โรงพยาบาลนายายอาม",
    "โรงพยาบาลแหลมสิงห์",
    "โรงพยาบาลเขาสุกิม",
    "โรงพยาบาลเขาคิชฌกูฏ",
    "โรงพยาบาลมะขาม",
    "โรงพยาบาลสอยดาว",
    "โรงพยาบาลขลุง",
    "โรงพยาบาลสองพี่น้อง",
    "โรงพยาบาลท่าใหม่",
)
RESULT_OPTIONS = (
    "",
    "Absence of spermatozoa",
    "Presence of spermatozoa",
)
THAI_MONTH_NAMES = (
    "",
    "มกราคม",
    "กุมภาพันธ์",
    "มีนาคม",
    "เมษายน",
    "พฤษภาคม",
    "มิถุนายน",
    "กรกฎาคม",
    "สิงหาคม",
    "กันยายน",
    "ตุลาคม",
    "พฤศจิกายน",
    "ธันวาคม",
)


def format_buddhist_date(day: int, month: int, gregorian_year: int) -> str:
    buddhist_year = gregorian_year + 543
    return f"{day:02d}/{month:02d}/{buddhist_year % 100:02d}"


def format_24_hour_time(hour: int | None, minute: int | None) -> str:
    if hour is None or minute is None:
        return ""
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError("Hour must be 00-23 and minute must be 00-59")
    return f"{hour:02d}.{minute:02d}"


def normalize_entry_values(values: dict[str, str]) -> dict[str, str]:
    return {key: str(values.get(key, "")).strip() for key in ENTRY_KEYS}


def generate_entry_docx(
    output_path: Path,
    values: dict[str, str],
    template_path: Path = DEFAULT_TEMPLATE_PATH,
) -> Path:
    if not template_path.exists():
        raise FileNotFoundError(f"DOCX template not found: {template_path}")
    normalized_values = normalize_entry_values(values)
    service = DocxTemplateService()
    if not service.has_fill_targets(template_path, normalized_values):
        raise ValueError(f"DOCX template does not contain i1-i9/R1-R3 targets: {template_path}")
    return service.fill(template_path, output_path, normalized_values)


def run_data_entry_gui() -> int:
    try:
        from PySide6.QtCore import QDate, QEvent, QLocale, Qt
        from PySide6.QtWidgets import (
            QApplication,
            QCalendarWidget,
            QComboBox,
            QDialog,
            QFileDialog,
            QGridLayout,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QToolButton,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        print("PySide6 is not installed. Run: pip install -e \".[app]\"")
        return 1

    class BuddhistCalendarDialog(QDialog):
        def __init__(self, selected_date: QDate | None, parent=None) -> None:
            super().__init__(parent)
            self.setWindowTitle("เลือกวันที่")
            self.setModal(True)
            self.selected_date: QDate | None = None

            self.previous_button = QToolButton()
            self.previous_button.setText("<")
            self.previous_button.setToolTip("เดือนก่อนหน้า")
            self.next_button = QToolButton()
            self.next_button.setText(">")
            self.next_button.setToolTip("เดือนถัดไป")
            self.month_label = QLabel()
            self.month_label.setAlignment(Qt.AlignCenter)
            self.month_label.setStyleSheet("font-size: 16px; font-weight: 600;")

            navigation = QHBoxLayout()
            navigation.addWidget(self.previous_button)
            navigation.addWidget(self.month_label, 1)
            navigation.addWidget(self.next_button)

            self.calendar = QCalendarWidget()
            self.calendar.setLocale(QLocale("th_TH"))
            self.calendar.setNavigationBarVisible(False)
            self.calendar.setGridVisible(True)
            initial_date = selected_date if selected_date and selected_date.isValid() else QDate.currentDate()
            self.calendar.setSelectedDate(initial_date)
            self.calendar.setCurrentPage(initial_date.year(), initial_date.month())

            self.previous_button.clicked.connect(self.calendar.showPreviousMonth)
            self.next_button.clicked.connect(self.calendar.showNextMonth)
            self.calendar.currentPageChanged.connect(self.update_month_label)
            self.calendar.clicked.connect(self.select_date)
            self.update_month_label(initial_date.year(), initial_date.month())

            layout = QVBoxLayout()
            layout.addLayout(navigation)
            layout.addWidget(self.calendar)
            self.setLayout(layout)

        def update_month_label(self, year: int, month: int) -> None:
            self.month_label.setText(f"{THAI_MONTH_NAMES[month]} {year + 543}")

        def select_date(self, selected_date: QDate) -> None:
            self.selected_date = selected_date
            self.accept()

    class BuddhistDateField(QWidget):
        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self.selected_date: QDate | None = None
            self.editor = QLineEdit()
            self.editor.setReadOnly(True)
            self.editor.setPlaceholderText("วว/ดด/ปป")
            self.editor.setMinimumHeight(32)
            self.select_button = QPushButton("เลือกวันที่")
            self.select_button.setAutoDefault(False)
            self.select_button.clicked.connect(self.open_calendar)

            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            layout.addWidget(self.editor, 1)
            layout.addWidget(self.select_button)
            self.setLayout(layout)
            self.setFocusProxy(self.editor)

        def open_calendar(self) -> None:
            dialog = BuddhistCalendarDialog(self.selected_date, self)
            if dialog.exec() == QDialog.Accepted and dialog.selected_date is not None:
                self.selected_date = dialog.selected_date
                self.editor.setText(
                    format_buddhist_date(
                        self.selected_date.day(),
                        self.selected_date.month(),
                        self.selected_date.year(),
                    )
                )

        def value(self) -> str:
            return self.editor.text()

        def clear(self) -> None:
            self.selected_date = None
            self.editor.clear()

        def focus_widgets(self) -> list[QWidget]:
            return [self.editor]

    class TimeField(QWidget):
        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self.hour = QComboBox()
            self.hour.addItem("")
            self.hour.addItems([f"{value:02d}" for value in range(24)])
            self.minute = QComboBox()
            self.minute.addItem("")
            self.minute.addItems([f"{value:02d}" for value in range(60)])
            for control in (self.hour, self.minute):
                control.setMinimumHeight(32)

            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(6)
            layout.addWidget(QLabel("ชม."))
            layout.addWidget(self.hour)
            layout.addWidget(QLabel("นาที"))
            layout.addWidget(self.minute)
            layout.addStretch()
            self.setLayout(layout)
            self.setFocusProxy(self.hour)

        def value(self) -> str:
            hour = int(self.hour.currentText()) if self.hour.currentText() else None
            minute = int(self.minute.currentText()) if self.minute.currentText() else None
            return format_24_hour_time(hour, minute)

        def clear(self) -> None:
            self.hour.setCurrentIndex(0)
            self.minute.setCurrentIndex(0)

        def focus_widgets(self) -> list[QWidget]:
            return [self.hour, self.minute]

    class DataEntryWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("DOCX Data Entry")
            self.setMinimumSize(920, 600)
            self.controls: dict[str, QWidget] = {}
            self.value_getters: dict[str, Callable[[], str]] = {}
            self.clear_actions: list[Callable[[], None]] = []
            self.tab_widgets: list[QWidget] = []

            title = QLabel("Prototype DOCX Data Entry")
            title.setStyleSheet("font-size: 20px; font-weight: 600;")

            form = QGridLayout()
            form.setHorizontalSpacing(18)
            form.setVerticalSpacing(10)
            for index, key in enumerate(ENTRY_KEYS):
                column_group = 0 if index < 9 else 1
                row = index if index < 9 else index - 9
                label_column = column_group * 2
                input_column = label_column + 1
                label = QLabel(FIELD_LABELS[key])
                label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
                control = self.create_control(key)
                form.addWidget(label, row, label_column)
                form.addWidget(control, row, input_column)
                self.controls[key] = control

            for previous, current in zip(self.tab_widgets, self.tab_widgets[1:]):
                QWidget.setTabOrder(previous, current)
            for widget in self.tab_widgets:
                widget.installEventFilter(self)

            self.clear_button = QPushButton("Clear")
            self.clear_button.setAutoDefault(False)
            self.clear_button.clicked.connect(self.clear_form)
            self.generate_button = QPushButton("Generate DOCX")
            self.generate_button.setAutoDefault(False)
            self.generate_button.clicked.connect(self.save_document)

            actions = QHBoxLayout()
            actions.addStretch()
            actions.addWidget(self.clear_button)
            actions.addWidget(self.generate_button)

            layout = QVBoxLayout()
            layout.setContentsMargins(24, 22, 24, 22)
            layout.setSpacing(18)
            layout.addWidget(title)
            layout.addLayout(form)
            layout.addStretch()
            layout.addLayout(actions)

            root = QWidget()
            root.setLayout(layout)
            self.setCentralWidget(root)
            self.setStyleSheet(
                "QLineEdit, QComboBox { padding: 4px 7px; }"
                "QPushButton { min-height: 30px; padding: 2px 12px; }"
            )
            self.tab_widgets[0].setFocus()

        def create_control(self, key: str) -> QWidget:
            if key in {"i6", "i8", "i9"}:
                control = BuddhistDateField()
                self.value_getters[key] = control.value
                self.clear_actions.append(control.clear)
                self.tab_widgets.extend(control.focus_widgets())
                return control
            if key == "i7":
                control = TimeField()
                self.value_getters[key] = control.value
                self.clear_actions.append(control.clear)
                self.tab_widgets.extend(control.focus_widgets())
                return control
            if key == "i5" or key in {"R1", "R2", "R3"}:
                control = QComboBox()
                control.addItems(HOSPITAL_OPTIONS if key == "i5" else RESULT_OPTIONS)
                control.setMinimumHeight(32)
                self.value_getters[key] = control.currentText
                self.clear_actions.append(lambda item=control: item.setCurrentIndex(0))
                self.tab_widgets.append(control)
                return control

            control = QLineEdit()
            control.setMinimumHeight(32)
            self.value_getters[key] = control.text
            self.clear_actions.append(control.clear)
            self.tab_widgets.append(control)
            return control

        def eventFilter(self, watched, event) -> bool:
            if event.type() == QEvent.KeyPress and event.key() in {Qt.Key_Return, Qt.Key_Enter}:
                self.save_document()
                return True
            return super().eventFilter(watched, event)

        def form_values(self) -> dict[str, str]:
            return {key: getter() for key, getter in self.value_getters.items()}

        def clear_form(self) -> None:
            for clear in self.clear_actions:
                clear()
            self.tab_widgets[0].setFocus()

        def save_document(self) -> None:
            output_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save generated DOCX",
                str(DEFAULT_OUTPUT_PATH),
                "Word documents (*.docx)",
            )
            if not output_path:
                return
            selected_path = Path(output_path)
            if selected_path.suffix.lower() != ".docx":
                selected_path = selected_path.with_suffix(".docx")
            try:
                saved_path = generate_entry_docx(selected_path, self.form_values())
            except (FileNotFoundError, ValueError, OSError) as exc:
                QMessageBox.critical(self, "Generate failed", str(exc))
                return
            QMessageBox.information(self, "DOCX created", f"Created file:\n{saved_path}")

    app = QApplication([])
    window = DataEntryWindow()
    window.show()
    return app.exec()
