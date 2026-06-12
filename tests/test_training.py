import json
import tempfile
import unittest
from pathlib import Path

from rape_ocr.recycling import RecyclingDataset
from rape_ocr.training import (
    build_paddleocr_export_command,
    _label_from_field,
    build_paddleocr_finetune_command,
    fine_tune_from_dataset,
    prepare_finetune_dataset,
    reviewed_dataset_output_dir,
    update_ocr_model_config,
)


class TrainingTest(unittest.TestCase):
    def test_label_prefers_reviewed_value(self):
        self.assertEqual(
            _label_from_field(
                {
                    "prediction": "wrong",
                    "final_value": "final",
                    "reviewed_value": "reviewed",
                }
            ),
            "reviewed",
        )

    def test_builds_paddleocr_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "PaddleOCR"
            tools = source / "tools"
            tools.mkdir(parents=True)
            (tools / "train.py").write_text("print('train')", encoding="utf-8")

            command = build_paddleocr_finetune_command(
                Path("rec.yml"),
                source_dir=source,
                overrides=("Global.epoch_num=1",),
            )

        self.assertTrue(any(item.endswith("tools\\train.py") or item.endswith("tools/train.py") for item in command))
        self.assertNotIn("paddle.distributed.launch", command)
        self.assertNotIn("--gpus", command)
        self.assertIn("rec.yml", command)
        self.assertIn("-o", command)
        self.assertIn("Global.use_gpu=False", command)
        self.assertIn("Global.epoch_num=1", command)

    def test_builds_gpu_paddleocr_command_with_launcher(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "PaddleOCR"
            tools = source / "tools"
            tools.mkdir(parents=True)
            (tools / "train.py").write_text("print('train')", encoding="utf-8")

            command = build_paddleocr_finetune_command(
                Path("rec.yml"),
                source_dir=source,
                overrides=("Global.epoch_num=1",),
                gpus="0",
            )

        self.assertIn("paddle.distributed.launch", command)
        self.assertIn("--gpus", command)
        self.assertIn("0", command)
        self.assertNotIn("Global.use_gpu=False", command)
        self.assertTrue(any(item.endswith("tools\\train.py") or item.endswith("tools/train.py") for item in command))

    def test_cpu_paddleocr_command_keeps_explicit_use_gpu_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "PaddleOCR"
            tools = source / "tools"
            tools.mkdir(parents=True)
            (tools / "train.py").write_text("print('train')", encoding="utf-8")

            command = build_paddleocr_finetune_command(
                Path("rec.yml"),
                source_dir=source,
                overrides=("Global.use_gpu=False", "Global.epoch_num=1"),
            )

        self.assertEqual(command.count("Global.use_gpu=False"), 1)

    def test_missing_paddleocr_source_dir_raises_clear_error(self):
        with self.assertRaises(FileNotFoundError):
            build_paddleocr_finetune_command(
                Path("rec.yml"),
                source_dir=Path("missing-paddleocr-source"),
            )

    def test_builds_paddleocr_export_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "PaddleOCR"
            tools = source / "tools"
            tools.mkdir(parents=True)
            (tools / "export_model.py").write_text("print('export')", encoding="utf-8")

            command = build_paddleocr_export_command(
                Path("rec.yml"),
                Path("models/best_accuracy"),
                Path("models/paddleocr/rec/latest"),
                source_dir=source,
            )

        self.assertTrue(any(item.endswith("tools\\export_model.py") or item.endswith("tools/export_model.py") for item in command))
        self.assertIn(f"Global.checkpoints={(Path.cwd() / 'models/best_accuracy').resolve()}", command)
        self.assertIn(f"Global.save_inference_dir={(Path.cwd() / 'models/paddleocr/rec/latest').resolve()}", command)

    def test_relative_training_model_dir_resolves_to_project_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "PaddleOCR"
            tools = source / "tools"
            tools.mkdir(parents=True)
            (tools / "train.py").write_text("print('train')", encoding="utf-8")

            command = build_paddleocr_finetune_command(
                Path("rec.yml"),
                source_dir=source,
                overrides=("Global.save_model_dir=models/paddleocr/rec/checkpoints",),
            )

        self.assertIn(
            f"Global.save_model_dir={(Path.cwd() / 'models/paddleocr/rec/checkpoints').resolve()}",
            command,
        )

    def test_reviewed_dataset_output_dir_uses_finetune_base(self):
        path = reviewed_dataset_output_dir(Path("data/finetune"))

        self.assertEqual(path.parent, Path("data/finetune"))
        self.assertTrue(path.name.startswith("reviewed_"))

    def test_update_ocr_model_config_writes_recognition_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "ocr_models.json"

            update_ocr_model_config(config, Path("models/paddleocr/rec/latest"))

            payload = json.loads(config.read_text(encoding="utf-8"))
        self.assertEqual(payload["text_recognition_model_dir"], "models\\paddleocr\\rec\\latest")

    def test_prepare_finetune_dataset_exports_reviewed_crops(self):
        try:
            import cv2
            import numpy as np
        except Exception as exc:
            raise unittest.SkipTest("opencv and numpy are required for crop export test") from exc
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image_path = root / "sample.png"
            cv2.imwrite(str(image_path), np.full((40, 80, 3), 255, dtype=np.uint8))
            entry_dir = root / "recycling" / "rural_rape" / "20260613T000000Z_test"
            entry_dir.mkdir(parents=True)
            metadata = {
                "pattern_name": "rural_rape",
                "copied_image": str(image_path),
                "fields": [
                    {
                        "name": "patient_name",
                        "kind": "text",
                        "reviewed_value": "Name",
                        "bbox": [0.0, 0.0, 0.5, 0.5],
                    }
                ],
            }
            (entry_dir / "metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False),
                encoding="utf-8",
            )

            result = prepare_finetune_dataset(
                RecyclingDataset(root / "recycling"),
                root / "finetune",
                pattern_name="rural_rape",
            )

            self.assertEqual(result.train_count, 1)
            self.assertEqual(result.val_count, 0)
            train_label = result.train_label_path.read_text(encoding="utf-8")
            self.assertIn("Name", train_label)
            self.assertIn(str((root / "finetune" / "crops").resolve()).replace("\\", "/"), train_label)

    def test_finetune_command_points_to_prepared_dataset_labels(self):
        try:
            import cv2
            import numpy as np
        except Exception as exc:
            raise unittest.SkipTest("opencv and numpy are required for crop export test") from exc
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "PaddleOCR"
            tools = source / "tools"
            tools.mkdir(parents=True)
            (tools / "train.py").write_text("print('train')", encoding="utf-8")
            image_path = root / "sample.png"
            cv2.imwrite(str(image_path), np.full((40, 80, 3), 255, dtype=np.uint8))
            entry_dir = root / "recycling" / "rural_rape" / "20260613T000000Z_test"
            entry_dir.mkdir(parents=True)
            metadata = {
                "pattern_name": "rural_rape",
                "copied_image": str(image_path),
                "fields": [
                    {
                        "name": "patient_name",
                        "kind": "text",
                        "reviewed_value": "Name",
                        "bbox": [0.0, 0.0, 0.5, 0.5],
                    }
                ],
            }
            (entry_dir / "metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False),
                encoding="utf-8",
            )

            result = fine_tune_from_dataset(
                RecyclingDataset(root / "recycling"),
                root / "finetune",
                config_path=Path("rec.yml"),
                source_dir=source,
                overrides=("Global.epoch_num=1",),
            )

        self.assertIsNotNone(result.command)
        command = result.command or ()
        self.assertIn("Train.dataset.data_dir=.", command)
        self.assertIn("Eval.dataset.data_dir=.", command)
        self.assertIn("Global.use_gpu=False", command)
        self.assertTrue(any(item.startswith("Train.dataset.label_file_list=") for item in command))
        self.assertTrue(any(item.startswith("Eval.dataset.label_file_list=") for item in command))
        self.assertIn("Global.epoch_num=1", command)


if __name__ == "__main__":
    unittest.main()
