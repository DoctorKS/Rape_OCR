from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from .domain import OcrJob


@dataclass(frozen=True)
class CleanupResult:
    cutoff: datetime
    dry_run: bool
    matched_dirs: tuple[Path, ...]
    deleted_dirs: tuple[Path, ...]


@dataclass(frozen=True)
class DeleteEntryResult:
    entry_dir: Path
    dry_run: bool
    deleted: bool


class RecyclingDataset:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def save_reviewed_job(self, job: OcrJob) -> Path:
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        target_dir = self.root / job.pattern_name / f"{timestamp}_{job.id}"
        target_dir.mkdir(parents=True, exist_ok=True)

        image_target = target_dir / job.image_path.name
        if job.image_path.exists():
            shutil.copy2(job.image_path, image_target)

        payload = job.reviewed_payload()
        payload["recycled_at"] = timestamp
        payload["copied_image"] = str(image_target)
        metadata_path = target_dir / "metadata.json"
        metadata_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return metadata_path

    def cleanup_old_entries(self, older_than_days: int, dry_run: bool = True) -> CleanupResult:
        if older_than_days < 1:
            raise ValueError("older_than_days must be at least 1")
        cutoff = datetime.utcnow() - timedelta(days=older_than_days)
        matched = tuple(self._iter_entry_dirs_before(cutoff))
        deleted: list[Path] = []
        if not dry_run:
            for entry_dir in matched:
                resolved = entry_dir.resolve()
                root = self.root.resolve()
                if root not in resolved.parents:
                    raise ValueError(f"Refusing to delete outside recycling root: {entry_dir}")
                shutil.rmtree(entry_dir)
                deleted.append(entry_dir)
        return CleanupResult(
            cutoff=cutoff,
            dry_run=dry_run,
            matched_dirs=matched,
            deleted_dirs=tuple(deleted),
        )

    def delete_entry(self, entry: str, dry_run: bool = True) -> DeleteEntryResult:
        entry_dir = self._resolve_entry(entry)
        if not entry_dir.exists():
            raise FileNotFoundError(f"Recycling entry not found: {entry_dir}")
        if not entry_dir.is_dir():
            raise ValueError(f"Recycling entry must be a directory: {entry_dir}")
        deleted = False
        if not dry_run:
            shutil.rmtree(entry_dir)
            deleted = True
        return DeleteEntryResult(entry_dir=entry_dir, dry_run=dry_run, deleted=deleted)

    def _resolve_entry(self, entry: str) -> Path:
        root = self.root.resolve()
        normalized = entry.replace("\\", "/").strip("/")
        entry_path = (self.root / normalized).resolve()
        if root != entry_path and root not in entry_path.parents:
            raise ValueError(f"Refusing to access outside recycling root: {entry}")
        return entry_path

    def _iter_entry_dirs_before(self, cutoff: datetime):
        if not self.root.exists():
            return
        for pattern_dir in self.root.iterdir():
            if not pattern_dir.is_dir():
                continue
            for entry_dir in pattern_dir.iterdir():
                if not entry_dir.is_dir():
                    continue
                entry_time = self._entry_timestamp(entry_dir)
                if entry_time is not None and entry_time < cutoff:
                    yield entry_dir

    @staticmethod
    def _entry_timestamp(entry_dir: Path) -> datetime | None:
        prefix = entry_dir.name.split("_", 1)[0]
        try:
            return datetime.strptime(prefix, "%Y%m%dT%H%M%SZ")
        except ValueError:
            metadata = entry_dir / "metadata.json"
            if not metadata.exists():
                return None
            try:
                payload = json.loads(metadata.read_text(encoding="utf-8"))
                recycled_at = str(payload.get("recycled_at", ""))
                return datetime.strptime(recycled_at, "%Y%m%dT%H%M%SZ")
            except (ValueError, json.JSONDecodeError):
                return None
