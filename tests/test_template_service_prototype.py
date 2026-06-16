import tempfile
import unittest
import zipfile
from pathlib import Path

from rape_ocr.domain import FieldResult
from rape_ocr.export_mapping import build_docx_export_payload
from rape_ocr.template_service import DocxTemplateService


class TemplateServicePrototypeTest(unittest.TestCase):
    def test_docx_exact_text_fields_and_calendar_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            template_path = tmp_path / "template.docx"
            output_path = tmp_path / "output.docx"
            date_control = (
                "<w:sdt><w:sdtPr><w:date><w:dateFormat w:val=\"dd/MM/bb\"/>"
                "</w:date></w:sdtPr><w:sdtContent><w:p><w:r><w:t>{value}</w:t>"
                "</w:r></w:p></w:sdtContent></w:sdt>"
            )
            document_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body>"
                "<w:p><w:r><w:t>i2</w:t></w:r><w:r><w:t>R1</w:t></w:r></w:p>"
                f"{date_control.format(value='old1')}"
                f"{date_control.format(value='old2')}"
                f"{date_control.format(value='old3')}"
                "</w:body></w:document>"
            )
            with zipfile.ZipFile(template_path, "w") as archive:
                archive.writestr("[Content_Types].xml", "")
                archive.writestr("word/document.xml", document_xml)

            DocxTemplateService().fill(
                template_path,
                output_path,
                {"i2": "Patient A", "R1": "Absence of spermatozoa"},
                ["15/05/69", "16/05/69", "17/05/69"],
            )

            with zipfile.ZipFile(output_path, "r") as archive:
                filled = archive.read("word/document.xml").decode("utf-8")

            self.assertIn("Patient A", filled)
            self.assertIn("Absence of spermatozoa", filled)
            self.assertIn("15/05/69", filled)
            self.assertIn("16/05/69", filled)
            self.assertIn("17/05/69", filled)
            self.assertNotIn(">i2<", filled)
            self.assertNotIn(">R1<", filled)
            self.assertNotIn(">old1<", filled)

    def test_real_prototype_fills_ppk_date_tokens(self):
        template_path = Path("docs/example/prototype.docx")
        if not template_path.exists():
            self.skipTest("prototype.docx is required")
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "output.docx"
            payload = build_docx_export_payload(
                [
                    self.field("collection_date", "23/05/69"),
                    self.field("collection_time", "13.20"),
                    self.field("handwritten_number", "S046/69"),
                    self.field("handwritten_date", "12/06/69"),
                    self.field("vulvar_result", "Absence"),
                    self.field("vaginal_result", "Absence"),
                    self.field("endocervical_result", "'"),
                ]
            )

            DocxTemplateService().fill(
                template_path,
                output_path,
                payload.values,
                payload.date_values,
            )

            with zipfile.ZipFile(output_path, "r") as archive:
                filled = archive.read("word/document.xml").decode("utf-8")

            self.assertIn("23/05/69", filled)
            self.assertIn("13.20", filled)
            self.assertIn("12/06/69", filled)
            self.assertNotIn(">I6<", filled)
            self.assertNotIn(">I8<", filled)
            self.assertNotIn(">I9<", filled)
            self.assertNotIn(">R3<", filled)

    @staticmethod
    def field(name: str, value: str) -> FieldResult:
        return FieldResult(
            name=name,
            label=name,
            prediction=value,
            confidence=1.0,
            bbox=(0, 0, 1, 1),
        )
