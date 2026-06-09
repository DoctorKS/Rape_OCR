from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class FieldConfig:
    name: str
    label: str
    bbox: BBox
    kind: str = "text"
    docx_tag: str | None = None
    required: bool = False
    expected_pattern: str | None = None
    preprocess: str | None = None
    default_value: str | None = None


@dataclass(frozen=True)
class PatternConfig:
    name: str
    display_name: str
    version: str
    fields: tuple[FieldConfig, ...]


@dataclass
class FieldResult:
    name: str
    label: str
    prediction: str
    confidence: float
    bbox: BBox
    kind: str = "text"
    docx_tag: str | None = None
    raw_prediction: str | None = None
    reviewed_value: str | None = None
    status: str = "pending_review"

    @property
    def final_value(self) -> str:
        return self.reviewed_value if self.reviewed_value is not None else self.prediction


@dataclass
class OcrJob:
    image_path: Path
    pattern_name: str
    fields: list[FieldResult]
    id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=datetime.utcnow)

    def reviewed_payload(self) -> dict[str, Any]:
        return {
            "job_id": self.id,
            "image_path": str(self.image_path),
            "pattern_name": self.pattern_name,
            "created_at": self.created_at.isoformat() + "Z",
            "fields": [
                {
                    "name": item.name,
                    "label": item.label,
                    "prediction": item.prediction,
                    "raw_prediction": item.raw_prediction,
                    "reviewed_value": item.reviewed_value,
                    "final_value": item.final_value,
                    "confidence": item.confidence,
                    "bbox": item.bbox,
                    "kind": item.kind,
                    "docx_tag": item.docx_tag,
                    "status": item.status,
                }
                for item in self.fields
            ],
        }
