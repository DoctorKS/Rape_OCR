from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .domain import OcrJob
from .ocr_service import OcrService, _normalize_result_choice
from .recycling import RecyclingDataset, RecyclingEntry
from .storage import AppStorage


@dataclass(frozen=True)
class ReprocessItemResult:
    source_metadata: Path
    image_path: Path | None
    output_metadata: Path | None
    pattern_name: str | None
    dry_run: bool
    status: str
    message: str = ""


@dataclass(frozen=True)
class ReprocessResult:
    dry_run: bool
    items: tuple[ReprocessItemResult, ...]

    @property
    def processed_count(self) -> int:
        return sum(1 for item in self.items if item.status == "processed")

    @property
    def skipped_count(self) -> int:
        return sum(1 for item in self.items if item.status == "skipped")

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.items if item.status == "error")


class DatasetReprocessor:
    def __init__(
        self,
        recycling: RecyclingDataset,
        ocr: OcrService,
        storage: AppStorage | None = None,
    ) -> None:
        self.recycling = recycling
        self.ocr = ocr
        self.storage = storage

    def reprocess(
        self,
        pattern_name: str | None = None,
        entry: str | None = None,
        dry_run: bool = True,
    ) -> ReprocessResult:
        entries = self._select_entries(pattern_name=pattern_name, entry=entry)
        results = tuple(self._reprocess_entry(item, dry_run=dry_run) for item in entries)
        return ReprocessResult(dry_run=dry_run, items=results)

    def _select_entries(self, pattern_name: str | None, entry: str | None) -> tuple[RecyclingEntry, ...]:
        if entry:
            entry_dir = self.recycling._resolve_entry(entry)
            metadata_path = entry_dir / "metadata.json"
            if not metadata_path.exists():
                raise FileNotFoundError(f"Recycling metadata not found: {metadata_path}")
            import json

            return (
                RecyclingEntry(
                    entry_dir=entry_dir,
                    metadata_path=metadata_path,
                    payload=json.loads(metadata_path.read_text(encoding="utf-8")),
                ),
            )
        return self.recycling.iter_entries(pattern_name=pattern_name)

    def _reprocess_entry(self, entry: RecyclingEntry, dry_run: bool) -> ReprocessItemResult:
        pattern_name = _payload_text(entry.payload, "pattern_name")
        image_path = _resolve_payload_image(entry.payload, entry.entry_dir)
        if pattern_name is None:
            return ReprocessItemResult(
                source_metadata=entry.metadata_path,
                image_path=image_path,
                output_metadata=None,
                pattern_name=None,
                dry_run=dry_run,
                status="error",
                message="missing pattern_name",
            )
        if image_path is None or not image_path.exists():
            return ReprocessItemResult(
                source_metadata=entry.metadata_path,
                image_path=image_path,
                output_metadata=None,
                pattern_name=pattern_name,
                dry_run=dry_run,
                status="error",
                message="source image not found",
            )
        if dry_run:
            return ReprocessItemResult(
                source_metadata=entry.metadata_path,
                image_path=image_path,
                output_metadata=None,
                pattern_name=pattern_name,
                dry_run=True,
                status="processed",
                message="would reprocess",
            )

        skipped_fields = self.storage.get_skipped_fields(pattern_name) if self.storage else set()
        job = self.ocr.process(image_path, pattern_name=pattern_name, skipped_fields=skipped_fields)
        _carry_reviewed_values(job, entry.payload)
        if self.storage:
            self.storage.save_job(job, status="reviewed")
        output_metadata = self.recycling.save_reviewed_job(
            job,
            extra_metadata={
                "reprocess": {
                    "source_metadata": str(entry.metadata_path),
                    "source_entry": str(entry.entry_dir),
                    "source_job_id": entry.payload.get("job_id"),
                    "reason": "refresh anchor crop metadata from existing reviewed dataset",
                }
            },
        )
        return ReprocessItemResult(
            source_metadata=entry.metadata_path,
            image_path=image_path,
            output_metadata=output_metadata,
            pattern_name=pattern_name,
            dry_run=False,
            status="processed",
            message="reprocessed",
        )


def _payload_text(payload: dict, key: str) -> str | None:
    value = payload.get(key)
    if value is None:
        return None
    return str(value)


def _resolve_payload_image(payload: dict, entry_dir: Path) -> Path | None:
    for key in ("copied_image", "image_path"):
        value = payload.get(key)
        if not value:
            continue
        path = Path(str(value))
        candidates = [path] if path.is_absolute() else [path, entry_dir / path, entry_dir / path.name]
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()
    return None


def _carry_reviewed_values(job: OcrJob, payload: dict) -> None:
    reviewed = {
        str(item.get("name")): item.get("reviewed_value", item.get("final_value"))
        for item in payload.get("fields", [])
        if isinstance(item, dict) and item.get("name")
    }
    for field in job.fields:
        if field.name not in reviewed:
            continue
        value = reviewed[field.name]
        field.reviewed_value = None if value is None else str(value)
        if field.kind == "result_choice" and field.reviewed_value != "-":
            field.reviewed_value = _normalize_result_choice(field.reviewed_value)
        field.status = "reviewed"
