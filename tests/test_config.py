import unittest

from rape_ocr.config import load_patterns


class ConfigTest(unittest.TestCase):
    def test_load_patterns_contains_expected_patterns(self):
        patterns = load_patterns()

        self.assertIn("ppk_rape", patterns)
        self.assertIn("rural_rape", patterns)
        self.assertTrue(patterns["ppk_rape"].fields)
        self.assertTrue(patterns["rural_rape"].fields)
