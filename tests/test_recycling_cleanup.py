import tempfile
import unittest
from pathlib import Path

from rape_ocr.recycling import RecyclingDataset


class RecyclingCleanupTest(unittest.TestCase):
    def test_cleanup_old_entries_dry_run_does_not_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "recycling"
            old_entry = root / "rural_rape" / "20000101T000000Z_old"
            old_entry.mkdir(parents=True)
            (old_entry / "metadata.json").write_text("{}", encoding="utf-8")

            result = RecyclingDataset(root).cleanup_old_entries(older_than_days=1)

            self.assertEqual(result.matched_dirs, (old_entry,))
            self.assertEqual(result.deleted_dirs, ())
            self.assertTrue(old_entry.exists())

    def test_cleanup_old_entries_with_confirm_deletes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "recycling"
            old_entry = root / "rural_rape" / "20000101T000000Z_old"
            old_entry.mkdir(parents=True)
            (old_entry / "metadata.json").write_text("{}", encoding="utf-8")

            result = RecyclingDataset(root).cleanup_old_entries(older_than_days=1, dry_run=False)

            self.assertEqual(result.deleted_dirs, (old_entry,))
            self.assertFalse(old_entry.exists())

    def test_cleanup_requires_positive_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                RecyclingDataset(Path(tmp)).cleanup_old_entries(older_than_days=0)

    def test_delete_entry_dry_run_does_not_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "recycling"
            entry = root / "rural_rape" / "20260101T000000Z_job"
            entry.mkdir(parents=True)

            result = RecyclingDataset(root).delete_entry("rural_rape/20260101T000000Z_job")

            self.assertFalse(result.deleted)
            self.assertTrue(entry.exists())

    def test_delete_entry_with_confirm_deletes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "recycling"
            entry = root / "rural_rape" / "20260101T000000Z_job"
            entry.mkdir(parents=True)

            result = RecyclingDataset(root).delete_entry(
                "rural_rape/20260101T000000Z_job",
                dry_run=False,
            )

            self.assertTrue(result.deleted)
            self.assertFalse(entry.exists())

    def test_delete_entry_refuses_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                RecyclingDataset(Path(tmp) / "recycling").delete_entry("../outside")
