import unittest

from rape_ocr.ocr_service import (
    PlaceholderOcrEngine,
    _normalize_case_code,
    _normalize_hospital_name,
    _normalize_named_field_prediction,
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
            "18/69",
        )
        self.assertEqual(
            _normalize_named_field_prediction("rural_rape", "collection_date", "text", "18/05/2569", "18/05/2569"),
            "18/69",
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
            "positive",
        )
        self.assertEqual(
            _normalize_named_field_prediction("ppk_rape", "vaginal_result", "result_choice", "Negative", "Negative"),
            "negative",
        )
        self.assertEqual(
            _normalize_named_field_prediction("ppk_rape", "handwritten_date", "table_date", "4.06", "4.06"),
            "4.06",
        )
        self.assertEqual(
            _normalize_named_field_prediction("ppk_rape", "handwritten_number", "case_code", "5042/69", "S042/69"),
            "S042",
        )
