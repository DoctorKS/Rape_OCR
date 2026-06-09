from __future__ import annotations

import html
import re
import shutil
import zipfile
from collections.abc import Sequence
from pathlib import Path


class DocxTemplateService:
    def fill(
        self,
        template_path: Path,
        output_path: Path,
        values: dict[str, str],
        date_values: Sequence[str] | None = None,
    ) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_path, output_path)
        self._replace_document_xml(output_path, values, date_values or [])
        return output_path

    def _replace_document_xml(
        self,
        docx_path: Path,
        values: dict[str, str],
        date_values: Sequence[str],
    ) -> None:
        with zipfile.ZipFile(docx_path, "r") as source:
            entries = {name: source.read(name) for name in source.namelist()}

        document_name = "word/document.xml"
        document_xml = entries[document_name].decode("utf-8")
        document_xml = self._replace_placeholders(document_xml, values)
        document_xml = self._replace_exact_text_fields(document_xml, values)
        document_xml = self._replace_tagged_content_controls(document_xml, values)
        document_xml = self._replace_date_content_controls(document_xml, date_values)
        entries[document_name] = document_xml.encode("utf-8")

        with zipfile.ZipFile(docx_path, "w", zipfile.ZIP_DEFLATED) as target:
            for name, content in entries.items():
                target.writestr(name, content)

    @staticmethod
    def _replace_placeholders(document_xml: str, values: dict[str, str]) -> str:
        for key, value in values.items():
            escaped_value = html.escape(value)
            document_xml = document_xml.replace(f"{{{{{key}}}}}", escaped_value)
        return document_xml

    @staticmethod
    def _replace_exact_text_fields(document_xml: str, values: dict[str, str]) -> str:
        def replace(match: re.Match[str]) -> str:
            start, text, end = match.groups()
            key = html.unescape(text)
            if not re.fullmatch(r"(?:i\d+|R\d+)", key):
                return match.group(0)
            value = values.get(key)
            if value is None:
                return match.group(0)
            return f"{start}{html.escape(value)}{end}"

        return re.sub(
            r"(<w:t(?:\s+[^>]*)?>)(.*?)(</w:t>)",
            replace,
            document_xml,
            flags=re.DOTALL,
        )

    @staticmethod
    def _replace_tagged_content_controls(document_xml: str, values: dict[str, str]) -> str:
        for key, value in values.items():
            escaped_key = re.escape(key)
            escaped_value = html.escape(value)
            pattern = re.compile(
                rf"(<w:sdt\b(?:(?!</w:sdt>).)*?<w:tag\s+w:val=\"{escaped_key}\"(?:(?!</w:sdt>).)*?<w:sdtContent\b[^>]*>)(.*?)(</w:sdtContent>.*?</w:sdt>)",
                re.DOTALL,
            )

            def replace(match: re.Match[str]) -> str:
                content = match.group(2)
                content = re.sub(
                    r"<w:t(?:\s+[^>]*)?>.*?</w:t>",
                    f"<w:t>{escaped_value}</w:t>",
                    content,
                    count=1,
                    flags=re.DOTALL,
                )
                return match.group(1) + content + match.group(3)

            document_xml = pattern.sub(replace, document_xml)
        return document_xml

    @staticmethod
    def _replace_date_content_controls(document_xml: str, date_values: Sequence[str]) -> str:
        if not date_values:
            return document_xml

        date_index = 0
        pattern = re.compile(
            r"(<w:sdt\b(?:(?!</w:sdt>).)*?<w:date\b(?:(?!</w:sdt>).)*?</w:sdt>)",
            re.DOTALL,
        )

        def replace(match: re.Match[str]) -> str:
            nonlocal date_index
            if date_index >= len(date_values):
                return match.group(0)

            value = date_values[date_index]
            date_index += 1
            if not value:
                return match.group(0)

            return re.sub(
                r"<w:t(?:\s+[^>]*)?>.*?</w:t>",
                f"<w:t>{html.escape(value)}</w:t>",
                match.group(0),
                count=1,
                flags=re.DOTALL,
            )

        return pattern.sub(replace, document_xml)
