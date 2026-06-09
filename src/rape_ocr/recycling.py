from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .domain import OcrJob


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

