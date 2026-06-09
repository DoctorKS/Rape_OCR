import zipfile
import unittest

from rape_ocr.template_service import DocxTemplateService


class TemplateServiceTest(unittest.TestCase):
    def test_docx_placeholder_fill(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            from pathlib import Path

            tmp_path = Path(tmp)
            template_path = tmp_path / "template.docx"
            output_path = tmp_path / "output.docx"
            document_xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>{{patient_name}}</w:t></w:r></w:p></w:body></w:document>"
            )
            with zipfile.ZipFile(template_path, "w") as archive:
                archive.writestr("[Content_Types].xml", "")
                archive.writestr("word/document.xml", document_xml)

            DocxTemplateService().fill(template_path, output_path, {"patient_name": "ทดสอบ"})

            with zipfile.ZipFile(output_path, "r") as archive:
                filled = archive.read("word/document.xml").decode("utf-8")
            self.assertIn("ทดสอบ", filled)
            self.assertNotIn("{{patient_name}}", filled)
