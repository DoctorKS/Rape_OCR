from __future__ import annotations

from pathlib import Path

from .config import load_patterns
from .dataset_reprocess import DatasetReprocessor
from .export_mapping import build_docx_export_payload
from .ocr_service import OcrService, create_ocr_engine, normalize_field_value
from .recycling import RecyclingDataset
from .storage import AppStorage
from .template_service import DocxTemplateService


def run_gui() -> int:
    try:
        from PySide6.QtCore import QObject, Qt, QThread, Signal
        from PySide6.QtWidgets import (
            QApplication,
            QFileDialog,
            QHBoxLayout,
            QInputDialog,
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

    class OcrWorker(QObject):
        finished = Signal(object)
        failed = Signal(str)

        def __init__(self, ocr: OcrService, storage: AppStorage, image_path: Path) -> None:
            super().__init__()
            self.ocr = ocr
            self.storage = storage
            self.image_path = image_path

        def run(self) -> None:
            try:
                pattern_name = self.ocr.detect_pattern(self.image_path)
                skipped_fields = self.storage.get_skipped_fields(pattern_name)
                job = self.ocr.process(
                    self.image_path,
                    pattern_name=pattern_name,
                    skipped_fields=skipped_fields,
                )
                self.storage.save_job(job)
                self.finished.emit(job)
            except Exception as exc:
                self.failed.emit(str(exc))

    class ReprocessWorker(QObject):
        finished = Signal(object)
        failed = Signal(str)

        def __init__(
            self,
            recycling: RecyclingDataset,
            ocr: OcrService,
            storage: AppStorage,
            pattern_name: str | None,
            dry_run: bool,
        ) -> None:
            super().__init__()
            self.recycling = recycling
            self.ocr = ocr
            self.storage = storage
            self.pattern_name = pattern_name
            self.dry_run = dry_run

        def run(self) -> None:
            try:
                result = DatasetReprocessor(
                    self.recycling,
                    self.ocr,
                    storage=self.storage,
                ).reprocess(
                    pattern_name=self.pattern_name,
                    dry_run=self.dry_run,
                )
                self.finished.emit(result)
            except Exception as exc:
                self.failed.emit(str(exc))

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
            self.ocr_thread = None
            self.ocr_worker = None
            self.reprocess_thread = None
            self.reprocess_worker = None
            self.pending_reprocess_pattern = None
            self.reprocess_write_requested = False
            self.ocr_running = False

            engine = QLabel(f"OCR engine: {self.ocr.engine.name}")
            self.status = QLabel("Ready")
            self.image_path = QLineEdit()
            self.image_path.setPlaceholderText("Select document image")

            self.import_button = QPushButton("Import")
            self.import_button.clicked.connect(self.import_image)
            self.ocr_button = QPushButton("OCR")
            self.ocr_button.clicked.connect(self.process_image)
            self.save_button = QPushButton("Save Review")
            self.save_button.clicked.connect(self.save_review)
            self.export_button = QPushButton("Export DOCX")
            self.export_button.clicked.connect(self.export_docx)
            self.reprocess_button = QPushButton("Reprocess Dataset")
            self.reprocess_button.clicked.connect(self.reprocess_dataset)

            top = QHBoxLayout()
            top.addWidget(engine)
            top.addWidget(self.status)
            top.addWidget(QLabel("Image"))
            top.addWidget(self.image_path)
            top.addWidget(self.import_button)
            top.addWidget(self.ocr_button)
            top.addWidget(self.save_button)
            top.addWidget(self.export_button)
            top.addWidget(self.reprocess_button)

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
            if self.ocr_running:
                QMessageBox.information(self, "OCR running", "Please wait until OCR is finished.")
                return
            path, _ = QFileDialog.getOpenFileName(
                self,
                "Import document image",
                str(Path("docs/example").resolve()),
                "Images (*.jpg *.jpeg *.png *.bmp)",
            )
            if path:
                self.image_path.setText(path)

        def process_image(self) -> None:
            if self.ocr_running:
                return
            if not self.image_path.text():
                QMessageBox.warning(self, "Missing image", "Please select an image first.")
                return

            self.current_job = None
            self.table.setRowCount(0)
            self.set_busy(True, "OCR processing...")

            self.ocr_thread = QThread()
            self.ocr_worker = OcrWorker(self.ocr, self.storage, Path(self.image_path.text()))
            self.ocr_worker.moveToThread(self.ocr_thread)
            self.ocr_thread.started.connect(self.ocr_worker.run)
            self.ocr_worker.finished.connect(self.on_ocr_finished)
            self.ocr_worker.failed.connect(self.on_ocr_failed)
            self.ocr_worker.finished.connect(self.ocr_thread.quit)
            self.ocr_worker.failed.connect(self.ocr_thread.quit)
            self.ocr_worker.finished.connect(self.ocr_worker.deleteLater)
            self.ocr_worker.failed.connect(self.ocr_worker.deleteLater)
            self.ocr_thread.finished.connect(self.ocr_thread.deleteLater)
            self.ocr_thread.finished.connect(self.on_ocr_thread_finished)
            self.ocr_thread.start()

        def reprocess_dataset(self) -> None:
            if self.ocr_running:
                return
            choices = ["all", *sorted(self.patterns.keys())]
            selected, ok = QInputDialog.getItem(
                self,
                "Reprocess Dataset",
                "Pattern",
                choices,
                choices.index("ppk_rape") if "ppk_rape" in choices else 0,
                False,
            )
            if not ok:
                return
            pattern_name = None if selected == "all" else selected
            self.pending_reprocess_pattern = pattern_name
            self.start_reprocess(pattern_name=pattern_name, dry_run=True)

        def start_reprocess(self, pattern_name: str | None, dry_run: bool) -> None:
            self.set_busy(True, "Reprocess dry-run..." if dry_run else "Reprocess writing new entries...")
            self.reprocess_thread = QThread()
            self.reprocess_worker = ReprocessWorker(
                self.recycling,
                self.ocr,
                self.storage,
                pattern_name,
                dry_run,
            )
            self.reprocess_worker.moveToThread(self.reprocess_thread)
            self.reprocess_thread.started.connect(self.reprocess_worker.run)
            self.reprocess_worker.finished.connect(self.on_reprocess_finished)
            self.reprocess_worker.failed.connect(self.on_reprocess_failed)
            self.reprocess_worker.finished.connect(self.reprocess_thread.quit)
            self.reprocess_worker.failed.connect(self.reprocess_thread.quit)
            self.reprocess_worker.finished.connect(self.reprocess_worker.deleteLater)
            self.reprocess_worker.failed.connect(self.reprocess_worker.deleteLater)
            self.reprocess_thread.finished.connect(self.reprocess_thread.deleteLater)
            self.reprocess_thread.finished.connect(self.on_reprocess_thread_finished)
            self.reprocess_thread.start()

        def on_ocr_finished(self, job) -> None:
            self.current_job = job
            self.populate_table(job)
            self.status.setText(f"OCR complete: {job.pattern_name}")

        def on_ocr_failed(self, message: str) -> None:
            self.current_job = None
            QMessageBox.critical(self, "OCR failed", message)
            self.status.setText("OCR failed")

        def on_ocr_thread_finished(self) -> None:
            self.ocr_thread = None
            self.ocr_worker = None
            self.set_busy(False)

        def on_reprocess_finished(self, result) -> None:
            summary = self.format_reprocess_summary(result)
            self.reprocess_write_requested = False
            if result.dry_run and result.processed_count > 0:
                answer = QMessageBox.question(
                    self,
                    "Reprocess dry-run complete",
                    summary + "\n\nWrite new recycling entries now?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No,
                )
                if answer == QMessageBox.Yes:
                    self.reprocess_write_requested = True
                    self.status.setText("Reprocess write queued")
                else:
                    self.status.setText("Reprocess dry-run complete")
            else:
                QMessageBox.information(self, "Reprocess complete", summary)
                self.status.setText("Reprocess complete")

        def on_reprocess_failed(self, message: str) -> None:
            QMessageBox.critical(self, "Reprocess failed", message)
            self.status.setText("Reprocess failed")

        def on_reprocess_thread_finished(self) -> None:
            self.reprocess_thread = None
            self.reprocess_worker = None
            self.set_busy(False)
            if self.reprocess_write_requested:
                self.reprocess_write_requested = False
                self.start_reprocess(self.pending_reprocess_pattern, dry_run=False)

        def set_busy(self, busy: bool, status: str | None = None) -> None:
            self.ocr_running = busy
            self.import_button.setEnabled(not busy)
            self.ocr_button.setEnabled(not busy)
            self.save_button.setEnabled(not busy)
            self.export_button.setEnabled(not busy)
            self.reprocess_button.setEnabled(not busy)
            if status:
                self.status.setText(status)

        @staticmethod
        def format_reprocess_summary(result) -> str:
            lines = [
                f"mode={'dry-run' if result.dry_run else 'write'}",
                f"items={len(result.items)}",
                f"processed={result.processed_count}",
                f"skipped={result.skipped_count}",
                f"errors={result.error_count}",
            ]
            for item in result.items[:12]:
                lines.append(f"{item.status}: {item.pattern_name} {item.message}")
            if len(result.items) > 12:
                lines.append(f"...and {len(result.items) - 12} more")
            return "\n".join(lines)

        def populate_table(self, job) -> None:
            self.table.setRowCount(len(job.fields))
            for row, field in enumerate(job.fields):
                self.table.setItem(row, 0, QTableWidgetItem(field.name))
                self.table.setItem(row, 1, QTableWidgetItem(field.prediction))
                reviewed = QTableWidgetItem(field.final_value)
                reviewed.setFlags(reviewed.flags() | Qt.ItemIsEditable)
                self.table.setItem(row, 2, reviewed)
                self.table.setItem(row, 3, QTableWidgetItem(f"{field.confidence:.2f}"))
                self.table.setItem(row, 4, QTableWidgetItem(field.status))

        def save_review(self) -> None:
            if self.current_job is None:
                QMessageBox.warning(self, "No job", "No OCR job to save.")
                return
            self.apply_reviewed_values()
            self.storage.save_job(self.current_job, status="reviewed")
            metadata_path = self.recycling.save_reviewed_job(self.current_job)
            QMessageBox.information(
                self,
                "Saved",
                "Review saved.\n"
                "If a field is reviewed as '-', that field will be skipped next time for the same pattern.\n"
                f"{metadata_path}",
            )

        def export_docx(self) -> None:
            if self.current_job is None:
                QMessageBox.warning(self, "No job", "No OCR job to export.")
                return
            template_path = Path("docs/example/prototype.docx").resolve()
            if not template_path.exists():
                QMessageBox.warning(
                    self,
                    "Missing DOCX template",
                    f"Default template not found:\n{template_path}",
                )
                return
            self.apply_reviewed_values()
            payload = build_docx_export_payload(self.current_job.fields)
            if not self.templates.has_fill_targets(template_path, payload.values, payload.date_values):
                QMessageBox.warning(
                    self,
                    "Invalid DOCX template",
                    f"The default DOCX template does not contain fillable placeholders/content controls:\n{template_path}",
                )
                return
            output_path, _ = QFileDialog.getSaveFileName(
                self,
                "Save generated DOCX",
                str(Path("output/generated.docx").resolve()),
                "Word documents (*.docx)",
            )
            if not output_path:
                return
            self.storage.save_job(self.current_job, status="reviewed")
            self.recycling.save_reviewed_job(self.current_job)
            saved_path = self.templates.fill(
                template_path,
                Path(output_path),
                payload.values,
                payload.date_values,
            )
            QMessageBox.information(self, "Exported", f"Generated document:\n{saved_path}")

        def apply_reviewed_values(self) -> None:
            if self.current_job is None:
                return
            for row, field in enumerate(self.current_job.fields):
                item = self.table.item(row, 2)
                reviewed = item.text() if item is not None else field.prediction
                field.reviewed_value = normalize_field_value(
                    self.current_job.pattern_name,
                    field.name,
                    field.kind,
                    reviewed,
                    reviewed,
                )
                field.status = "reviewed"

    app = QApplication([])
    window = MainWindow()
    window.show()
    return app.exec()
