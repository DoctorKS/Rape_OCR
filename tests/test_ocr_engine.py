import unittest

from rape_ocr.ocr_service import (
    PlaceholderOcrEngine,
    _normalize_case_code,
    _normalize_hospital_name,
    _normalize_result_choice,
    create_ocr_engine,
)


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
        self.assertEqual(_normalize_result_choice("unclear"), "")

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
