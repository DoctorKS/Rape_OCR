import tempfile
import unittest
from pathlib import Path

from rape_ocr.config import load_patterns
from rape_ocr.ocr_service import OcrEngine, OcrService


class LayoutTextEngine(OcrEngine):
    name = "layout_text"

    def __init__(self, text: str) -> None:
        self.text = text

    def recognize(self, image):
        return self.text, 0.9

    def recognize_layout(self, image):
        return [(self.text, (0.0, 0.0, 1.0, 1.0), 0.9)]


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

    @staticmethod
    def write_minimal_jpeg(name: str) -> Path:
        try:
            import cv2
            import numpy as np
        except Exception as exc:
            raise unittest.SkipTest("OpenCV/numpy is required for image pattern detection test") from exc
        root = Path(tempfile.mkdtemp())
        image_path = root / name
        image = np.full((12, 12, 3), 255, dtype=np.uint8)
        cv2.imwrite(str(image_path), image)
        return image_path
