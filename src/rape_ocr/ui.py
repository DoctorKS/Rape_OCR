from __future__ import annotations

from pathlib import Path

from .config import load_patterns
from .ocr_service import OcrService, PlaceholderOcrEngine
from .recycling import RecyclingDataset
from .storage import AppStorage
from .template_service import DocxTemplateService


def run_gui() -> int:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication,
            QFileDialog,
            QHBoxLayout,
            QLabel,
            QLineEdit,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QTableWidget,
            QTableWidgetItem,
            QVBoxLayout,
            QWidget,
        )
    except ImportError:
        print("PySide6 is not installed. Run: pip install -r requirements.txt")
        return 1

    class MainWindow(QMainWindow):
        def __init__(self) -> None:
            super().__init__()
            self.setWindowTitle("Rape OCR")
            self.resize(1100, 720)
            self.patterns = load_patterns()
            self.ocr = OcrService(self.patterns, PlaceholderOcrEngine())
            self.storage = AppStorage(Path("data/app.db"))
            self.recycling = RecyclingDataset(Path("data/recycling"))
            self.templates = DocxTemplateService()
            self.current_job = None

            self.image_path = QLineEdit()
            self.image_path.setPlaceholderText("เลือกไฟล์รูปเอกสาร")
            browse = QPushButton("Import")
            browse.clicked.connect(self.import_image)
            process = QPushButton("OCR")
            process.clicked.connect(self.process_image)
            recycle = QPushButton("Save Review")
            recycle.clicked.connect(self.save_review)

            top = QHBoxLayout()
            top.addWidget(QLabel("Image"))
            top.addWidget(self.image_path)
            top.addWidget(browse)
            top.addWidget(process)
            top.addWidget(recycle)

            self.table = QTableWidget(0, 5)
            self.table.setHorizontalHeaderLabels(["Field", "OCR", "Reviewed", "Confidence", "Status"])
            self.table.horizontalHeader().setStretchLastSection(True)

            layout = QVBoxLayout()
            layout.addLayout(top)
            layout.addWidget(self.table)
            root = QWidget()
            root.setLayout(layout)
            self.setCentralWidget(root)

        def import_image(self) -> None:
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Import document image",
                str(Path("docs/example").resolve()),
                "Images (*.jpg *.jpeg *.png *.bmp)",
            )
            if path:
                self.image_path.setText(path)

        def process_image(self) -> None:
            if not self.image_path.text():
                QMessageBox.warning(self, "Missing image", "กรุณาเลือกไฟล์รูปก่อน")
                return
            self.current_job = self.ocr.process(Path(self.image_path.text()))
            self.storage.save_job(self.current_job)
            self.table.setRowCount(len(self.current_job.fields))
            for row, field in enumerate(self.current_job.fields):
                self.table.setItem(row, 0, QTableWidgetItem(field.name))
                self.table.setItem(row, 1, QTableWidgetItem(field.prediction))
                reviewed = QTableWidgetItem(field.final_value)
                reviewed.setFlags(reviewed.flags() | Qt.ItemIsEditable)
                self.table.setItem(row, 2, reviewed)
                self.table.setItem(row, 3, QTableWidgetItem(f"{field.confidence:.2f}"))
                self.table.setItem(row, 4, QTableWidgetItem(field.status))

        def save_review(self) -> None:
            if self.current_job is None:
                QMessageBox.warning(self, "No job", "ยังไม่มีงาน OCR ให้บันทึก")
                return
            for row, field in enumerate(self.current_job.fields):
                item = self.table.item(row, 2)
                field.reviewed_value = item.text() if item is not None else field.prediction
                field.status = "reviewed"
            self.storage.save_job(self.current_job, status="reviewed")
            metadata_path = self.recycling.save_reviewed_job(self.current_job)
            QMessageBox.information(self, "Saved", f"บันทึก review แล้ว:\n{metadata_path}")

    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()

