from __future__ import annotations

import json
from pathlib import Path

from .domain import AnchorConfig, FieldConfig, PatternConfig


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PATTERN_DIR = PROJECT_ROOT / "configs" / "patterns"


def load_pattern(path: Path) -> PatternConfig:
    data = json.loads(path.read_text(encoding="utf-8"))
    fields = tuple(
        FieldConfig(
            name=item["name"],
            label=item.get("label", item["name"]),
            bbox=tuple(item["bbox"]),  # type: ignore[arg-type]
            kind=item.get("kind", "text"),
            docx_tag=item.get("docx_tag"),
            required=item.get("required", False),
            expected_pattern=item.get("expected_pattern"),
            preprocess=item.get("preprocess"),
            default_value=item.get("default_value"),
            anchor=_load_anchor(item.get("anchor")),
        )
        for item in data["fields"]
    )
    return PatternConfig(
        name=data["name"],
        display_name=data.get("display_name", data["name"]),
        version=data.get("version", "1"),
        fields=fields,
    )


def _load_anchor(data: dict | None) -> AnchorConfig | None:
    if not data:
        return None
    return AnchorConfig(
        texts=tuple(data.get("texts", ())),
        side=data.get("side", "right"),
        width=float(data.get("width", 0.2)),
        height=float(data["height"]) if data.get("height") is not None else None,
        offset_x=float(data.get("offset_x", 0.0)),
        offset_y=float(data.get("offset_y", 0.0)),
        pad_x=float(data.get("pad_x", 0.0)),
        pad_y=float(data.get("pad_y", 0.0)),
    )


def load_patterns(pattern_dir: Path = DEFAULT_PATTERN_DIR) -> dict[str, PatternConfig]:
    patterns = {}
    for path in sorted(pattern_dir.glob("*.json")):
        pattern = load_pattern(path)
        patterns[pattern.name] = pattern
    return patterns
