import unittest

from rape_ocr.config import load_patterns


RURAL_HOSPITAL = "\u0e42\u0e23\u0e07\u0e1e\u0e22\u0e32\u0e1a\u0e32\u0e25\u0e19\u0e32\u0e22\u0e32\u0e22\u0e2d\u0e32\u0e21"


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

    def test_rural_hospital_is_ocr_field_with_rural_default(self):
        patterns = load_patterns()
        hospital = next(field for field in patterns["rural_rape"].fields if field.name == "hospital")

        self.assertEqual(hospital.kind, "hospital_name")
        self.assertEqual(hospital.preprocess, "handwriting")
        self.assertEqual(hospital.default_value, RURAL_HOSPITAL)
