import tempfile
import unittest
import zipfile
from pathlib import Path

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
