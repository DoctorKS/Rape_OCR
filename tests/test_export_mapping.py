import unittest

from rape_ocr.domain import FieldResult
from rape_ocr.export_mapping import (
    build_docx_export_payload,
    format_date_for_docx,
    normalize_export_value,
)


class ExportMappingTest(unittest.TestCase):
    def test_maps_rural_fields_to_prototype_docx_fields(self):
        fields = [
            self.field("patient_name", "Patient A"),
            self.field("hospital", "Hospital A"),
            self.field("age", "11"),
            self.field("hn", "171338"),
            self.field("lower_right_handwritten_note", "note"),
            self.field("vaginal_result", "negative"),
            self.field("endocervical_result", "positive"),
            self.field("r3_result", "negative"),
        ]

        payload = build_docx_export_payload(fields)

        self.assertEqual(payload.values["i2"], "Patient A")
        self.assertEqual(payload.values["i5"], "Hospital A")
        self.assertEqual(payload.values["i3"], "11")
        self.assertEqual(payload.values["i4"], "171338")
        self.assertEqual(payload.values["i1"], "note")
        self.assertEqual(payload.values["R1"], "Absence of spermatozoa")
        self.assertEqual(payload.values["R2"], "Presence of spermatozoa")
        self.assertEqual(payload.values["R3"], "Absence of spermatozoa")

    def test_builds_calendar_values_in_prototype_order(self):
        fields = [
            self.field("collection_date", "15 พ.ค. 2569"),
            self.field("specimen_regis_date", "16/05/2569"),
            self.field("lower_right_handwritten_date", "17/05/69"),
        ]

        payload = build_docx_export_payload(fields)

        self.assertEqual(payload.date_values, ["15/05/69", "16/05/69", "17/05/69"])

    def test_maps_ppk_fields_to_prototype_docx_fields(self):
        fields = [
            self.field("patient_name", "Patient B"),
            self.field("age", "16"),
            self.field("hn", "4807790"),
            self.field("collection_date", "18/05/2569"),
            self.field("handwritten_date", "04/06/69"),
            self.field("handwritten_number", "5043/69"),
            self.field("vulvar_result", "negative"),
            self.field("vaginal_result", "negative"),
            self.field("endocervical_result", "negative"),
        ]

        payload = build_docx_export_payload(fields)

        self.assertEqual(payload.values["i1"], "5043/69")
        self.assertEqual(payload.values["i2"], "Patient B")
        self.assertEqual(payload.values["i3"], "16")
        self.assertEqual(payload.values["i4"], "4807790")
        self.assertEqual(payload.values["R1"], "Absence of spermatozoa")
        self.assertEqual(payload.values["R2"], "Absence of spermatozoa")
        self.assertEqual(payload.values["R3"], "Absence of spermatozoa")
        self.assertEqual(payload.date_values, ["18/05/69", "18/05/69", "04/06/69"])

    def test_formats_common_ocr_date_variants(self):
        self.assertEqual(format_date_for_docx("15 พ.ค. 2569"), "15/05/69")
        self.assertEqual(format_date_for_docx("15 พ.0 2569"), "15/05/69")
        self.assertEqual(format_date_for_docx("1/5/2569"), "01/05/69")
        self.assertEqual(format_date_for_docx("5042/69"), "5042/69")

    def test_result_fields_export_as_spermatozoa_phrase(self):
        self.assertEqual(normalize_export_value("vulvar_result", "Negative"), "Absence of spermatozoa")
        self.assertEqual(normalize_export_value("vaginal_result", "Positive"), "Presence of spermatozoa")
        self.assertEqual(normalize_export_value("endocervical_result", "present"), "Presence of spermatozoa")
        self.assertEqual(normalize_export_value("vulvar_result", "unclear"), "")

    @staticmethod
    def field(name: str, value: str) -> FieldResult:
        return FieldResult(
            name=name,
            label=name,
            prediction=value,
            confidence=1.0,
            bbox=(0, 0, 1, 1),
        )
