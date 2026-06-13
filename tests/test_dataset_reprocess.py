from pathlib import Path
import tempfile
import unittest

from rape_ocr.dataset_reprocess import DatasetReprocessor, _resolve_payload_image
from rape_ocr.domain import FieldResult, OcrJob
from rape_ocr.recycling import RecyclingDataset


class FakeOcrService:
    def process(self, image_path, pattern_name=None, skipped_fields=None):
        return OcrJob(
            image_path=Path(image_path),
            pattern_name=pattern_name or "ppk_rape",
            fields=[
                FieldResult(
                    name="patient_name",
                    label="Patient name",
                    prediction="new prediction",
                    confidence=0.7,
                    bbox=(0.1, 0.1, 0.2, 0.2),
                    docx_tag="patient_name",
                ),
                FieldResult(
                    name="vaginal_result",
                    label="Vaginal result",
                    prediction="positive",
                    confidence=0.7,
                    bbox=(0.2, 0.2, 0.3, 0.3),
                    kind="result_choice",
                    docx_tag="R1",
                ),
            ],
        )


class DatasetReprocessTest(unittest.TestCase):
    def test_resolves_relative_copied_image_from_working_directory(self):
        path = _resolve_payload_image(
            {"copied_image": "tests/test_dataset_reprocess.py"},
            Path("missing_entry"),
        )

        self.assertEqual(path, Path("tests/test_dataset_reprocess.py").resolve())

    def test_reprocess_dry_run_does_not_create_new_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "recycling"
            image_path = Path(tmp) / "sample.jpg"
            image_path.write_bytes(b"fake")
            _save_source_entry(root, image_path)

            result = DatasetReprocessor(RecyclingDataset(root), FakeOcrService()).reprocess()

            self.assertTrue(result.dry_run)
            self.assertEqual(result.processed_count, 1)
            self.assertEqual(len(RecyclingDataset(root).iter_entries()), 1)

    def test_reprocess_writes_new_entry_and_carries_reviewed_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "recycling"
            image_path = Path(tmp) / "sample.jpg"
            image_path.write_bytes(b"fake")
            source_metadata = _save_source_entry(root, image_path)

            result = DatasetReprocessor(RecyclingDataset(root), FakeOcrService()).reprocess(dry_run=False)

            self.assertFalse(result.dry_run)
            self.assertEqual(result.processed_count, 1)
            entries = RecyclingDataset(root).iter_entries()
            self.assertEqual(len(entries), 2)
            new_entry = next(item for item in entries if item.metadata_path != source_metadata)
            fields = {item["name"]: item for item in new_entry.payload["fields"]}
            self.assertEqual(fields["patient_name"]["reviewed_value"], "สมหญิง")
            self.assertEqual(fields["vaginal_result"]["reviewed_value"], "Absence")
            self.assertEqual(new_entry.payload["reprocess"]["source_metadata"], str(source_metadata))


def _save_source_entry(root: Path, image_path: Path) -> Path:
    job = OcrJob(
        image_path=image_path,
        pattern_name="ppk_rape",
        fields=[
            FieldResult(
                name="patient_name",
                label="Patient name",
                prediction="old prediction",
                reviewed_value="สมหญิง",
                confidence=0.5,
                bbox=(0.1, 0.1, 0.2, 0.2),
                status="reviewed",
            ),
            FieldResult(
                name="vaginal_result",
                label="Vaginal result",
                prediction="positive",
                reviewed_value="Negative",
                confidence=0.5,
                bbox=(0.2, 0.2, 0.3, 0.3),
                kind="result_choice",
                status="reviewed",
            ),
        ],
    )
    return RecyclingDataset(root).save_reviewed_job(job)
