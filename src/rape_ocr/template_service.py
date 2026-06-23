from __future__ import annotations

import html
import re
import shutil
import zipfile
from collections.abc import Sequence
from pathlib import Path


class DocxTemplateService:
    def has_fill_targets(
        self,
        template_path: Path,
        values: dict[str, str],
        date_values: Sequence[str] | None = None,
    ) -> bool:
        document_xml = self._read_document_xml(template_path)
        return self._has_placeholder_targets(document_xml, values) or self._has_date_targets(
            document_xml,
            date_values or [],
        )

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
        document_name = "word/document.xml"
        with zipfile.ZipFile(docx_path, "r") as source:
            entries = {name: source.read(name) for name in source.namelist()}

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
    def _read_document_xml(docx_path: Path) -> str:
        with zipfile.ZipFile(docx_path, "r") as source:
            return source.read("word/document.xml").decode("utf-8")

    @staticmethod
    def _has_placeholder_targets(document_xml: str, values: dict[str, str]) -> bool:
        for key in values:
            for candidate in DocxTemplateService._target_key_variants(key):
                escaped_key = re.escape(candidate)
                if f"{{{{{candidate}}}}}" in document_xml:
                    return True
                if re.search(rf"<w:t(?:\s+[^>]*)?>{escaped_key}</w:t>", document_xml):
                    return True
                if re.search(rf"<w:tag\s+w:val=\"{escaped_key}\"", document_xml):
                    return True
        return False

    @staticmethod
    def _target_key_variants(key: str) -> set[str]:
        variants = {key}
        if re.fullmatch(r"i\d+", key, flags=re.IGNORECASE):
            variants.add(key.lower())
            variants.add(key.upper())
        return variants

    @staticmethod
    def _value_for_target_key(values: dict[str, str], key: str) -> str | None:
        if key in values:
            return values[key]
        if re.fullmatch(r"i\d+", key, flags=re.IGNORECASE):
            lower_key = key.lower()
            upper_key = key.upper()
            if lower_key in values:
                return values[lower_key]
            if upper_key in values:
                return values[upper_key]
        return None

    @staticmethod
    def _has_date_targets(document_xml: str, date_values: Sequence[str]) -> bool:
        if not any(date_values):
            return False
        return "<w:date" in document_xml

    @staticmethod
    def _replace_placeholders(document_xml: str, values: dict[str, str]) -> str:
        for key, value in values.items():
            escaped_value = html.escape(value)
            for candidate in DocxTemplateService._target_key_variants(key):
                document_xml = document_xml.replace(f"{{{{{candidate}}}}}", escaped_value)
        return document_xml

    @staticmethod
    def _replace_exact_text_fields(document_xml: str, values: dict[str, str]) -> str:
        def replace(match: re.Match[str]) -> str:
            start, text, end = match.groups()
            key = html.unescape(text).strip()
            if not re.fullmatch(r"(?:[iI]\d+|R\d+)", key):
                return match.group(0)
            value = DocxTemplateService._value_for_target_key(values, key)
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
            for candidate in DocxTemplateService._target_key_variants(key):
                escaped_key = re.escape(candidate)
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
