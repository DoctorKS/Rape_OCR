import tempfile
import unittest
import zipfile
import re
from datetime import date
from pathlib import Path

from rape_ocr.data_entry_ui import (
    ENTRY_KEYS,
    FIELD_LABELS,
    HOSPITAL_OPTIONS,
    RESULT_OPTIONS,
    current_buddhist_year_short,
    format_24_hour_time,
    format_buddhist_date,
    format_lab_number,
    generate_entry_docx,
    lab_year_options,
    normalize_entry_values,
    suggested_output_path,
)


class DataEntryUiTest(unittest.TestCase):
    def test_entry_keys_follow_tab_order(self):
        self.assertEqual(
            ENTRY_KEYS,
            (
                "i1",
                "i2",
                "i3",
                "i4",
                "i5",
                "i6",
                "i7",
                "i8",
                "i9",
                "R1",
                "R2",
                "R3",
            ),
        )

    def test_normalize_entry_values_includes_blank_fields(self):
        values = normalize_entry_values({"i1": "  sample  ", "R1": "result"})

        self.assertEqual(values["i1"], "sample")
        self.assertEqual(values["R1"], "result")
        self.assertEqual(values["i9"], "")
        self.assertEqual(values["R3"], "")

    def test_field_labels_match_document_terms(self):
        self.assertEqual(FIELD_LABELS["i1"], "Lab No.")
        self.assertEqual(FIELD_LABELS["i5"], "Hospital")
        self.assertEqual(FIELD_LABELS["i8"], "Received date")
        self.assertEqual(FIELD_LABELS["i9"], "Reported Date")
        self.assertEqual(FIELD_LABELS["R1"], "Vulvar")
        self.assertEqual(FIELD_LABELS["R2"], "Vaginal")
        self.assertEqual(FIELD_LABELS["R3"], "Endocervical")

    def test_hospital_and_result_options(self):
        self.assertIn("โรงพยาบาลพระปกเกล้า", HOSPITAL_OPTIONS)
        self.assertIn("โรงพยาบาลท่าใหม่", HOSPITAL_OPTIONS)
        self.assertEqual(
            RESULT_OPTIONS,
            ("", "Absence of spermatozoa", "Presence of spermatozoa"),
        )

    def test_formats_buddhist_date_with_two_digit_year(self):
        self.assertEqual(format_buddhist_date(23, 6, 2026), "23/06/69")

    def test_formats_24_hour_time(self):
        self.assertEqual(format_24_hour_time(0, 5), "00.05")
        self.assertEqual(format_24_hour_time(23, 59), "23.59")
        self.assertEqual(format_24_hour_time(None, 30), "")
        with self.assertRaises(ValueError):
            format_24_hour_time(24, 0)

    def test_lab_number_uses_current_buddhist_year_first(self):
        self.assertEqual(current_buddhist_year_short(date(2026, 6, 23)), 69)
        options = lab_year_options(69)
        self.assertEqual(options[0], "69")
        self.assertEqual(options[-1], "99")
        self.assertEqual(len(options), 31)

    def test_formats_lab_number_and_suggested_filename(self):
        lab_number = format_lab_number("049", "69")

        self.assertEqual(lab_number, "S049/69")
        self.assertEqual(suggested_output_path({"i1": lab_number}).name, "S049-69.docx")

    def test_generates_real_prototype_with_all_tokens_replaced(self):
        template_path = Path("docs/example/prototype.docx")
        if not template_path.exists():
            self.skipTest("prototype.docx is required")
        values = {key: f"value-{key}" for key in ENTRY_KEYS}
        values["i8"] = ""

        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "generated.docx"
            saved_path = generate_entry_docx(output_path, values, template_path)

            self.assertEqual(saved_path, output_path)
            self.assertTrue(output_path.exists())
            with zipfile.ZipFile(output_path, "r") as archive:
                document_xml = archive.read("word/document.xml").decode("utf-8")

        for key in ENTRY_KEYS:
            self.assertNotIn(f">{key}<", document_xml)
            self.assertNotIn(f">{key.upper()}<", document_xml)
        self.assertIn("value-i1", document_xml)
        self.assertIn("value-R3", document_xml)
        for key in ("R1", "R2", "R3"):
            self.assertRegex(
                document_xml,
                re.compile(
                    rf"<w:r[^>]*>.*?<w:rPr>.*?<w:i/>.*?</w:rPr>.*?"
                    rf"<w:t>value-{key}</w:t>.*?</w:r>",
                    re.DOTALL,
                ),
            )


if __name__ == "__main__":
    unittest.main()
