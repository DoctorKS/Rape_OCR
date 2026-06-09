import unittest

from rape_ocr.ocr_service import PlaceholderOcrEngine, _normalize_result_choice, create_ocr_engine


class OcrEngineTest(unittest.TestCase):
    def test_can_force_placeholder_engine(self):
        engine = create_ocr_engine(prefer_paddle=False)

        self.assertIsInstance(engine, PlaceholderOcrEngine)
        self.assertEqual(engine.name, "placeholder")

    def test_normalize_result_choice(self):
        self.assertEqual(_normalize_result_choice("Negative"), "negative")
        self.assertEqual(_normalize_result_choice("neg."), "negative")
        self.assertEqual(_normalize_result_choice("Present"), "positive")
        self.assertEqual(_normalize_result_choice("positive"), "positive")
