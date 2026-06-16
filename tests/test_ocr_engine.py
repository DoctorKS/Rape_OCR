import unittest
from unittest.mock import patch

from rape_ocr.ocr_service import (
    PlaceholderOcrEngine,
    OcrService,
    TyphoonOllamaOcrEngine,
    _detect_pattern_from_text,
    _deskew_image,
    _encode_image_png_base64,
    _extract_page_text_items,
    _extract_typhoon_response_text,
    _layout_prediction_for_field,
    _load_ocr_model_options,
    _normalize_case_code,
    _normalize_hospital_name,
    _normalize_named_field_prediction,
    _normalize_result_choice,
    create_ocr_engine,
    normalize_field_value,
)
from rape_ocr.domain import FieldConfig, PatternConfig


class OcrEngineTest(unittest.TestCase):
    def test_can_force_placeholder_engine(self):
        engine = create_ocr_engine(prefer_paddle=False)

        self.assertIsInstance(engine, PlaceholderOcrEngine)
        self.assertEqual(engine.name, "placeholder")

    def test_load_ocr_model_options_prefers_env_rec_model_dir(self):
        options = _load_ocr_model_options(
            env={
                "RAPE_OCR_REC_MODEL_DIR": "models/paddleocr/rec/latest",
                "RAPE_OCR_DET_MODEL_DIR": "",
                "RAPE_OCR_TEXTLINE_MODEL_DIR": "",
            }
        )

        self.assertEqual(
            options["text_recognition_model_dir"],
            "models/paddleocr/rec/latest",
        )

    def test_create_ocr_engine_returns_engine_when_paddle_preferred(self):
        engine = create_ocr_engine(prefer_paddle=True)

        self.assertIsNotNone(engine)
        self.assertTrue(hasattr(engine, "recognize"))

    def test_create_ocr_engine_can_select_typhoon_ollama(self):
        with patch.dict("os.environ", {"RAPE_OCR_ENGINE": "typhoon_ollama"}):
            engine = create_ocr_engine(prefer_paddle=True)

        self.assertIsInstance(engine, TyphoonOllamaOcrEngine)
        self.assertEqual(engine.name, "typhoon_ollama")

    def test_extracts_typhoon_ollama_response_text(self):
        self.assertEqual(_extract_typhoon_response_text('{"response":"ข้อความ"}'), "ข้อความ")
        self.assertEqual(_extract_typhoon_response_text('{"message":{"content":"ชื่อ"}}'), "ชื่อ")

    def test_typhoon_ollama_engine_sends_image_payload(self):
        try:
            import numpy as np
        except Exception as exc:
            raise unittest.SkipTest("numpy is required for Typhoon payload test") from exc

        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, traceback):
                return False

            def read(self):
                return b'{"response":"sample text"}'

        def fake_urlopen(req, timeout):
            captured["url"] = req.full_url
            captured["body"] = req.data.decode("utf-8")
            captured["timeout"] = timeout
            return FakeResponse()

        image = np.full((12, 24, 3), 255, dtype=np.uint8)
        engine = TyphoonOllamaOcrEngine(
            model="test-model",
            endpoint="http://localhost:11434/api/generate",
            urlopen=fake_urlopen,
        )

        text, confidence = engine.recognize(image)

        self.assertEqual(text, "sample text")
        self.assertGreater(confidence, 0)
        self.assertIn("api/generate", captured["url"])
        self.assertIn('"model": "test-model"', captured["body"])
        self.assertIn('"stream": false', captured["body"])
        self.assertIn('"images": ["', captured["body"])

    def test_typhoon_image_encoding_rejects_empty_crop_cleanly(self):
        try:
            import numpy as np
        except Exception as exc:
            raise unittest.SkipTest("numpy is required for empty crop test") from exc

        with self.assertRaisesRegex(RuntimeError, "image encoding"):
            _encode_image_png_base64(np.zeros((0, 10, 3), dtype=np.uint8))

    def test_process_skips_empty_out_of_bounds_crop(self):
        try:
            import cv2
            import numpy as np
            import tempfile
            from pathlib import Path
        except Exception as exc:
            raise unittest.SkipTest("opencv and numpy are required for empty crop test") from exc

        class FailOnRecognizeEngine(PlaceholderOcrEngine):
            def recognize(self, image):
                raise AssertionError("empty crop should not be sent to OCR engine")

        with tempfile.TemporaryDirectory() as tmp:
            image_path = Path(tmp) / "sample.jpg"
            cv2.imwrite(str(image_path), np.full((20, 20, 3), 255, dtype=np.uint8))
            pattern = PatternConfig(
                name="test_pattern",
                display_name="Test",
                version="1",
                fields=(
                    FieldConfig(
                        name="field",
                        label="field",
                        bbox=(1.0, 0.0, 1.1, 0.1),
                    ),
                ),
            )
            service = OcrService({"test_pattern": pattern}, engine=FailOnRecognizeEngine())

            job = service.process(image_path, pattern_name="test_pattern")

        self.assertEqual(job.fields[0].prediction, "")
        self.assertEqual(job.fields[0].confidence, 0.0)

    def test_detect_pattern_from_ppk_text(self):
        self.assertEqual(
            _detect_pattern_from_text("โรงพยาบาลพระปกเกล้า"),
            "ppk_rape",
        )
        self.assertEqual(
            _detect_pattern_from_text("รพ.พระปกเกล้า"),
            "ppk_rape",
        )
        self.assertEqual(
            _detect_pattern_from_text("โรงพยาบาลพรปกเกล้า"),
            "ppk_rape",
        )
        self.assertEqual(
            _detect_pattern_from_text("TW.พระปกกล้า"),
            "ppk_rape",
        )

    def test_detect_pattern_from_text_defaults_to_rural_without_ppk_header(self):
        self.assertEqual(
            _detect_pattern_from_text("ใบแสดงรายการชันสูตรและบริการทางนิติเวช Order NO."),
            "rural_rape",
        )

    def test_normalize_result_choice(self):
        self.assertEqual(_normalize_result_choice("Negative"), "Absence")
        self.assertEqual(_normalize_result_choice("neg."), "Absence")
        self.assertEqual(_normalize_result_choice("Absent"), "Absence")
        self.assertEqual(_normalize_result_choice("Present"), "Presence")
        self.assertEqual(_normalize_result_choice("positive"), "Presence")
        self.assertEqual(_normalize_result_choice("Presence"), "Presence")
        self.assertEqual(_normalize_result_choice("unclear"), "")

    def test_extract_page_text_items_accepts_numpy_boxes(self):
        try:
            import numpy as np
        except Exception as exc:
            raise unittest.SkipTest("numpy is required for PaddleOCR layout parser test") from exc
        result = {
            "rec_texts": ["TW.พระปกกล้า"],
            "rec_boxes": np.array([[10, 20, 30, 40]]),
            "rec_scores": [0.9],
        }

        items = _extract_page_text_items(result, width=100, height=100)

        self.assertEqual(items[0][0], "TW.พระปกกล้า")
        self.assertEqual(items[0][1], (0.1, 0.2, 0.3, 0.4))

    def test_deskew_preserves_image_shape(self):
        try:
            import cv2
            import numpy as np
        except Exception as exc:
            raise unittest.SkipTest("opencv and numpy are required for deskew test") from exc
        image = np.full((120, 240, 3), 255, dtype=np.uint8)
        cv2.line(image, (20, 60), (220, 70), (0, 0, 0), 2)

        corrected = _deskew_image(image, max_degrees=8.0)

        self.assertEqual(corrected.shape, image.shape)

    def test_rural_header_layout_prediction_reads_grouped_fields(self):
        items = [
            ("Name:", (0.01, 0.17, 0.09, 0.20), 0.99),
            ("sample patient", (0.12, 0.18, 0.35, 0.21), 0.8),
            ("Age: 19", (0.60, 0.18, 0.69, 0.20), 0.92),
            ("yrs HN: 6303163", (0.71, 0.18, 0.91, 0.20), 0.76),
            ("Hospital:", (0.01, 0.20, 0.11, 0.23), 0.96),
            ("sample hospital", (0.12, 0.20, 0.24, 0.23), 0.7),
            ("Date of specimen collectionDate:1.69", (0.02, 0.23, 0.50, 0.26), 0.94),
            ("Time: 14.00", (0.70, 0.23, 0.88, 0.26), 0.87),
        ]

        self.assertEqual(_layout_prediction_for_field("rural_rape", "age", items)[0], "19")
        self.assertEqual(_layout_prediction_for_field("rural_rape", "hn", items)[0], "6303163")
        self.assertEqual(_layout_prediction_for_field("rural_rape", "collection_time", items)[0], "14.00")
        self.assertEqual(
            _layout_prediction_for_field("rural_rape", "patient_name", items)[0],
            "sample patient",
        )

    def test_rural_header_layout_prediction_respects_field_position(self):
        items = [
            ("HN: 11111", (0.20, 0.18, 0.30, 0.20), 0.8),
            ("HN: 6303163", (0.84, 0.18, 0.94, 0.20), 0.9),
        ]

        self.assertEqual(
            _layout_prediction_for_field("rural_rape", "hn", items, (0.83, 0.15, 0.97, 0.20))[0],
            "6303163",
        )

    def test_field_validation_rejects_values_outside_known_conditions(self):
        self.assertEqual(
            normalize_field_value(
                "rural_rape",
                "hospital",
                "hospital_name",
                "พืชผักและผลไม้หลายชนิดมีการใช้ประโยชน์จากใบมากกว่า",
                "พืชผักและผลไม้หลายชนิดมีการใช้ประโยชน์จากใบมากกว่า",
            ),
            "",
        )
        self.assertEqual(
            normalize_field_value("rural_rape", "specimen_regis_date", "text", "ficer only", "ficer only"),
            "",
        )
        self.assertEqual(
            normalize_field_value("rural_rape", "collection_time", "text", "15:30 น.", "15:30 น."),
            "15.30",
        )
        self.assertEqual(
            normalize_field_value("ppk_rape", "handwritten_number", "case_code", "S042/69", "S042/69"),
            "S042/69",
        )

    def test_normalize_case_code(self):
        self.assertEqual(_normalize_case_code("S042/69"), "5042/69")
        self.assertEqual(_normalize_case_code("5042/69"), "5042/69")
        self.assertEqual(_normalize_case_code("SO42|69"), "5042/69")
        self.assertEqual(_normalize_case_code("SO42", default_year="69"), "5042/69")
        self.assertEqual(_normalize_case_code("S042/", default_year="69"), "5042/69")

    def test_normalize_hospital_name(self):
        self.assertEqual(_normalize_hospital_name("โรงพยาบาลนายาอาม"), "โรงพยาบาลนายายอาม")
        self.assertEqual(_normalize_hospital_name("นายายอาม"), "โรงพยาบาลนายายอาม")
        self.assertEqual(_normalize_hospital_name("รพ.พระปกเกล้า"), "โรงพยาบาลพระปกเกล้า")
        self.assertEqual(_normalize_hospital_name("พระปกเกล้า"), "โรงพยาบาลพระปกเกล้า")

    def test_normalize_named_header_fields(self):
        self.assertEqual(
            _normalize_named_field_prediction("rural_rape", "patient_name", "text", "Name: กนกพร 123", "Name: กนกพร 123"),
            "กนกพร",
        )
        self.assertEqual(
            _normalize_named_field_prediction("rural_rape", "age", "text", "13 yrs", "13 yrs"),
            "13",
        )
        self.assertEqual(
            _normalize_named_field_prediction("rural_rape", "hn", "text", "HN: 3002973", "HN: 3002973"),
            "3002973",
        )
        self.assertEqual(
            _normalize_named_field_prediction("rural_rape", "collection_date", "text", "18 พฤษภาคม 2569", "18 พฤษภาคม 2569"),
            "18 พฤษภาคม 2569",
        )
        self.assertEqual(
            _normalize_named_field_prediction("rural_rape", "collection_date", "text", "18/05/2569", "18/05/2569"),
            "",
        )
        self.assertEqual(
            _normalize_named_field_prediction("rural_rape", "collection_time", "text", "เวลา 21.00 น.", "เวลา 21.00 น."),
            "21.00",
        )

    def test_rural_hospital_rejects_ppk_result(self):
        self.assertEqual(
            _normalize_named_field_prediction(
                "rural_rape",
                "hospital",
                "hospital_name",
                "โรงพยาบาลพระปกเกล้า",
                "รพ.พระปกเกล้า",
                "โรงพยาบาลนายายอาม",
            ),
            "โรงพยาบาลนายายอาม",
        )

    def test_normalize_named_ppk_fields(self):
        self.assertEqual(
            _normalize_named_field_prediction("ppk_rape", "vulvar_result", "result_choice", "POSITIVE", "POSITIVE"),
            "Presence",
        )
        self.assertEqual(
            _normalize_named_field_prediction("ppk_rape", "vaginal_result", "result_choice", "Negative", "Negative"),
            "Absence",
        )
        self.assertEqual(
            _normalize_named_field_prediction("ppk_rape", "handwritten_date", "table_date", "4.06", "4.06"),
            "4.06",
        )
        self.assertEqual(
            _normalize_named_field_prediction("ppk_rape", "handwritten_number", "case_code", "5042/69", "S042/69"),
            "S042/69",
        )
        self.assertEqual(
            _normalize_named_field_prediction("ppk_rape", "handwritten_number", "case_code", "5042", "S042"),
            "",
        )
