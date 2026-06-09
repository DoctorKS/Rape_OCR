from __future__ import annotations

from pathlib import Path

from .config import load_patterns
from .export_mapping import build_docx_export_payload
from .ocr_service import OcrService, create_ocr_engine
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
            self.ocr = OcrService(self.patterns, create_ocr_engine())
            self.storage = AppStorage(Path("data/app.db"))
            self.recycling = RecyclingDataset(Path("data/recycling"))
            self.templates = DocxTemplateService()
            self.current_job = None

            engine = QLabel(f"OCR engine: {self.ocr.engine.name}")
            self.image_path = QLineEdit()
            self.image_path.setPlaceholderText("เลือกไฟล์รูปเอกสาร")
            browse = QPushButton("Import")
            browse.clicked.connect(self.import_image)
            process = QPushButton("OCR")
            process.clicked.connect(self.process_image)
            recycle = QPushButton("Save Review")
            recycle.clicked.connect(self.save_review)
            export = QPushButton("Export DOCX")
            export.clicked.connect(self.export_docx)

            top = QHBoxLayout()
            top.addWidget(engine)
            top.addWidget(QLabel("Image"))
            top.addWidget(self.image_path)
            top.addWidget(browse)
            top.addWidget(process)
            top.addWidget(recycle)
            top.addWidget(export)

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
            image_path = Path(self.image_path.text())
            pattern_name = self.ocr.detect_pattern(image_path)
            skipped_fields = self.storage.get_skipped_fields(pattern_name)
            self.current_job = self.ocr.process(
                image_path,
                pattern_name=pattern_name,
                skipped_fields=skipped_fields,
            )
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
            QMessageBox.information(
                self,
                "Saved",
                "บันทึก review แล้ว\n"
                "ถ้า field ใดใส่ '-' ระบบจะข้าม OCR field นั้นในครั้งต่อไป\n"
                f"{metadata_path}",
            )

        def export_docx(self) -> None:
            if self.current_job is None:
                QMessageBox.warning(self, "No job", "ยังไม่มีงาน OCR ให้ export")
                return
            template_path, _ = QFileDialog.getOpenFileName(
                self,
                "Select DOCX template",
                str(Path("docs/example").resolve()),
                "Word documents (*.docx)",
            )
            if not template_path:
                return
            output_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save generated DOCX",
                str(Path("output/generated.docx").resolve()),
                "Word documents (*.docx)",
            )
            if not output_path:
                return
            for row, field in enumerate(self.current_job.fields):
                item = self.table.item(row, 2)
                field.reviewed_value = item.text() if item is not None else field.prediction
                field.status = "reviewed"
            self.storage.save_job(self.current_job, status="reviewed")
            self.recycling.save_reviewed_job(self.current_job)
            payload = build_docx_export_payload(self.current_job.fields)
            saved_path = self.templates.fill(
                Path(template_path),
                Path(output_path),
                payload.values,
                payload.date_values,
            )
            QMessageBox.information(self, "Exported", f"สร้างเอกสารแล้ว:\n{saved_path}")

    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
