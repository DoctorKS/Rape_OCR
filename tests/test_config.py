import unittest

from rape_ocr.config import load_patterns


class ConfigTest(unittest.TestCase):
    def test_load_patterns_contains_expected_patterns(self):
        patterns = load_patterns()

        self.assertIn("ppk_rape", patterns)
        self.assertIn("rural_rape", patterns)
        self.assertTrue(patterns["ppk_rape"].fields)
        self.assertTrue(patterns["rural_rape"].fields)

    def test_rural_top_fields_follow_header_order(self):
        patterns = load_patterns()

        top_field_names = [field.name for field in patterns["rural_rape"].fields[:6]]

        self.assertEqual(
            top_field_names,
            [
                "patient_name",
                "age",
                "hn",
                "hospital",
                "collection_date",
                "collection_time",
            ],
        )

    def test_rural_hospital_is_ocr_field_without_default(self):
        patterns = load_patterns()
        hospital = next(field for field in patterns["rural_rape"].fields if field.name == "hospital")

        self.assertEqual(hospital.kind, "hospital_name")
        self.assertEqual(hospital.preprocess, "handwriting")
        self.assertIsNone(hospital.default_value)

    def test_rural_top_fields_use_anchor_fallbacks(self):
        patterns = load_patterns()
        fields = {field.name: field for field in patterns["rural_rape"].fields}

        for name in ("patient_name", "age", "hn", "hospital", "collection_date", "collection_time"):
            self.assertIsNotNone(fields[name].anchor, name)

    def test_rural_result_fields_include_all_three_specimen_sites(self):
        patterns = load_patterns()
        fields = {field.name: field for field in patterns["rural_rape"].fields}

        for name in ("vulvar_result", "vaginal_result", "endocervical_result"):
            self.assertIn(name, fields)
            self.assertEqual(fields[name].kind, "result_choice")
