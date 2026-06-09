import tempfile
import unittest
from pathlib import Path

from rape_ocr.domain import FieldResult, OcrJob
from rape_ocr.storage import AppStorage


class SkipFieldsTest(unittest.TestCase):
    def test_review_dash_marks_field_as_skipped_for_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            storage = AppStorage(Path(tmp) / "app.db")
            job = OcrJob(
                image_path=Path("sample.jpg"),
                pattern_name="rural_rape",
                fields=[
                    FieldResult(
                        name="specimen_regis_date",
                        label="Specimen regis date",
                        prediction="15 พ.ค.2569",
                        reviewed_value="-",
                        confidence=0.5,
                        bbox=(0.1, 0.1, 0.2, 0.2),
                    )
                ],
            )

            storage.save_job(job, status="reviewed")

            self.assertEqual(storage.get_skipped_fields("rural_rape"), {"specimen_regis_date"})
