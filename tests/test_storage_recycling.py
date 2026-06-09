from pathlib import Path
import unittest

from rape_ocr.domain import FieldResult, OcrJob
from rape_ocr.recycling import RecyclingDataset
from rape_ocr.storage import AppStorage


class StorageRecyclingTest(unittest.TestCase):
    def test_storage_and_recycling_save_reviewed_job(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            image_path = tmp_path / "sample.jpg"
            image_path.write_bytes(b"fake image bytes")
            job = OcrJob(
                image_path=image_path,
                pattern_name="ppk_rape",
                fields=[
                    FieldResult(
                        name="patient_name",
                        label="ชื่อผู้ป่วย",
                        prediction="",
                        reviewed_value="ทดสอบ",
                        confidence=0.0,
                        bbox=(0.1, 0.1, 0.2, 0.2),
                        docx_tag="patient_name",
                        status="reviewed",
                    )
                ],
            )

            storage = AppStorage(tmp_path / "app.db")
            storage.save_job(job, status="reviewed")
            metadata_path = RecyclingDataset(tmp_path / "recycling").save_reviewed_job(job)

            self.assertEqual(storage.count_jobs(), 1)
            self.assertTrue(metadata_path.exists())
            self.assertNotEqual(Path(metadata_path).read_text(encoding="utf-8").find("ทดสอบ"), -1)
