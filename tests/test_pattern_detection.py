import tempfile
import unittest
from pathlib import Path

from rape_ocr.config import load_patterns
from rape_ocr.ocr_service import OcrEngine, OcrService, PATTERN_HEADER_RATIO


class LayoutTextEngine(OcrEngine):
    name = "layout_text"

    def __init__(self, text: str) -> None:
        self.text = text

    def recognize(self, image):
        return self.text, 0.9

    def recognize_layout(self, image):
        return [(self.text, (0.0, 0.0, 1.0, 1.0), 0.9)]


class CaptureShapeEngine(LayoutTextEngine):
    def __init__(self, text: str) -> None:
        super().__init__(text)
        self.seen_shape = None

    def recognize_layout(self, image):
        self.seen_shape = image.shape
        return super().recognize_layout(image)


class RotatedHeaderEngine(OcrEngine):
    name = "rotated_header"

    def recognize(self, image):
        return "", 0.0

    def recognize_layout(self, image):
        height, width = image.shape[:2]
        if width > height * 3:
            return [("โรงพยาบาลพระปกเกล้า", (0.0, 0.0, 1.0, 1.0), 0.9)]
        return [("Order NO.", (0.0, 0.0, 1.0, 1.0), 0.9)]


class PatternDetectionTest(unittest.TestCase):
    def test_detects_ppk_from_page_text_for_unknown_filename(self):
        image_path = self.write_minimal_jpeg("unknown.jpg")
        service = OcrService(
            load_patterns(),
            engine=LayoutTextEngine("โรงพยาบาลพระปกเกล้า"),
        )

        self.assertEqual(service.detect_pattern(image_path), "ppk_rape")

    def test_detects_rural_when_header_does_not_contain_ppk_hospital(self):
        image_path = self.write_minimal_jpeg("unknown.jpg")
        service = OcrService(
            load_patterns(),
            engine=LayoutTextEngine("ใบแสดงรายการชันสูตรและบริการทางนิติเวช Order NO."),
        )

        self.assertEqual(service.detect_pattern(image_path), "rural_rape")

    def test_pattern_detection_scans_upper_form_area(self):
        image_path = self.write_minimal_jpeg("unknown.jpg", height=100)
        engine = CaptureShapeEngine("รพ.พระปกเกล้า")
        service = OcrService(load_patterns(), engine=engine)

        self.assertEqual(service.detect_pattern(image_path), "ppk_rape")
        self.assertEqual(engine.seen_shape[0], round(100 * PATTERN_HEADER_RATIO))

    def test_pattern_detection_checks_rotated_header_area(self):
        image_path = self.write_minimal_jpeg("unknown.jpg", height=100, width=60)
        service = OcrService(load_patterns(), engine=RotatedHeaderEngine())

        self.assertEqual(service.detect_pattern(image_path), "ppk_rape")

    @staticmethod
    def write_minimal_jpeg(name: str, height: int = 12, width: int = 12) -> Path:
        try:
            import cv2
            import numpy as np
        except Exception as exc:
            raise unittest.SkipTest("OpenCV/numpy is required for image pattern detection test") from exc
        root = Path(tempfile.mkdtemp())
        image_path = root / name
        image = np.full((height, width, 3), 255, dtype=np.uint8)
        cv2.imwrite(str(image_path), image)
        return image_path
