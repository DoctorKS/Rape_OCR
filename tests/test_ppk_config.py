import unittest

from rape_ocr.config import load_patterns


class PpkConfigTest(unittest.TestCase):
    def test_ppk_hospital_is_constant(self):
        patterns = load_patterns()
        hospital = next(field for field in patterns["ppk_rape"].fields if field.name == "hospital")

        self.assertEqual(hospital.kind, "constant")
        self.assertEqual(hospital.default_value, "โรงพยาบาลพระปกเกล้า")
