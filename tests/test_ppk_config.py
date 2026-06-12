import unittest

from rape_ocr.config import load_patterns


class PpkConfigTest(unittest.TestCase):
    def test_ppk_hospital_is_constant(self):
        patterns = load_patterns()
        hospital = next(field for field in patterns["ppk_rape"].fields if field.name == "hospital")

        self.assertEqual(hospital.kind, "constant")
        self.assertEqual(hospital.default_value, "โรงพยาบาลพระปกเกล้า")

    def test_ppk_result_fields_crop_sperm_column(self):
        patterns = load_patterns()
        fields = {field.name: field for field in patterns["ppk_rape"].fields}

        for name in ("vulvar_result", "vaginal_result", "endocervical_result"):
            self.assertGreaterEqual(fields[name].bbox[0], 0.65)
            self.assertLessEqual(fields[name].bbox[2], 0.82)
