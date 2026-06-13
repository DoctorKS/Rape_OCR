from __future__ import annotations

import re
from dataclasses import dataclass

from .domain import FieldResult


PROTOTYPE_TEXT_FIELD_MAP = {
    "lower_right_handwritten_note": "i1",
    "handwritten_number": "i1",
    "patient_name": "i2",
    "age": "i3",
    "hn": "i4",
    "hospital": "i5",
    "collection_date": "i6",
    "collection_time": "i7",
    "specimen_regis_date": "i8",
    "lower_right_handwritten_date": "i9",
    "vaginal_result": "R1",
    "endocervical_result": "R2",
    "r3_result": "R3",
    "extra_result": "R3",
    "third_result": "R3",
}

PPK_RESULT_FIELD_MAP = {
    "vulvar_result": "R1",
    "vaginal_result": "R2",
    "endocervical_result": "R3",
}

RESULT_CHOICE_FIELDS = {
    "vulvar_result",
    "vaginal_result",
    "endocervical_result",
    "r3_result",
    "extra_result",
    "third_result",
}

DOCX_RESULT_VALUES = {
    "absence": "Absence of spermatozoa",
    "presence": "Presence of spermatozoa",
}

PROTOTYPE_DATE_FIELD_ORDER = (
    "collection_date",
    "specimen_regis_date",
    "lower_right_handwritten_date",
)

THAI_MONTHS = {
    "ม.ค": "01",
    "มค": "01",
    "ก.พ": "02",
    "กพ": "02",
    "มี.ค": "03",
    "มีค": "03",
    "เม.ย": "04",
    "เมย": "04",
    "พ.ค": "05",
    "พค": "05",
    "พ.0": "05",
    "มิ.ย": "06",
    "มิย": "06",
    "ก.ค": "07",
    "กค": "07",
    "ส.ค": "08",
    "สค": "08",
    "ก.ย": "09",
    "กย": "09",
    "ต.ค": "10",
    "ตค": "10",
    "พ.ย": "11",
    "พย": "11",
    "ธ.ค": "12",
    "ธค": "12",
}


@dataclass(frozen=True)
class DocxExportPayload:
    values: dict[str, str]
    date_values: list[str]


def build_docx_export_payload(fields: list[FieldResult]) -> DocxExportPayload:
    values: dict[str, str] = {}
    values_by_name: dict[str, str] = {}
    field_names = {field.name for field in fields}
    is_ppk = "vulvar_result" in field_names

    for field in fields:
        value = normalize_export_value(field.name, field.final_value)
        if not value or value == "-":
            continue

        values_by_name[field.name] = value
        values[field.name] = value
        if field.docx_tag:
            values[field.docx_tag] = value

        prototype_key = _prototype_text_key(field.name, is_ppk)
        if prototype_key:
            values[prototype_key] = value

    date_values = _prototype_date_values(values_by_name)
    return DocxExportPayload(values=values, date_values=date_values)


def normalize_export_value(field_name: str, value: str) -> str:
    text = value.strip()
    if text == "-":
        return text
    if field_name not in RESULT_CHOICE_FIELDS:
        return text
    compact = text.lower().replace(" ", "").replace(".", "")
    if compact in {"absence", "negative", "neg", "nega", "negati", "absent", "abs", "-"}:
        return DOCX_RESULT_VALUES["absence"]
    if compact in {"presence", "positive", "pos", "present", "pres", "+"}:
        return DOCX_RESULT_VALUES["presence"]
    return ""


def _prototype_text_key(field_name: str, is_ppk: bool) -> str | None:
    if is_ppk and field_name in PPK_RESULT_FIELD_MAP:
        return PPK_RESULT_FIELD_MAP[field_name]
    return PROTOTYPE_TEXT_FIELD_MAP.get(field_name)


def _prototype_date_values(values_by_name: dict[str, str]) -> list[str]:
    collection_date = values_by_name.get("collection_date", "")
    specimen_regis_date = values_by_name.get("specimen_regis_date") or collection_date
    reported_date = (
        values_by_name.get("lower_right_handwritten_date")
        or values_by_name.get("handwritten_date")
        or ""
    )
    return [
        format_date_for_docx(collection_date),
        format_date_for_docx(specimen_regis_date),
        format_date_for_docx(reported_date),
    ]


def format_date_for_docx(value: str) -> str:
    text = value.strip()
    if not text:
        return ""

    slash_match = re.search(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{2,4})", text)
    if slash_match:
        day, month, year = slash_match.groups()
        return f"{int(day):02d}/{int(month):02d}/{_short_buddhist_year(year)}"

    normalized = re.sub(r"\s+", "", text)
    for month_name, month_number in THAI_MONTHS.items():
        if month_name in normalized:
            day_match = re.search(r"\d{1,2}", normalized)
            year_match = re.search(r"(25\d{2}|\d{2})(?!.*\d)", normalized)
            if day_match and year_match:
                return f"{int(day_match.group()):02d}/{month_number}/{_short_buddhist_year(year_match.group())}"

    return text


def _short_buddhist_year(year: str) -> str:
    year_number = int(year)
    return f"{year_number % 100:02d}"
