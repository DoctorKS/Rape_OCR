from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .domain import OcrJob


class AppStorage:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                create table if not exists jobs (
                    id text primary key,
                    image_path text not null,
                    pattern_name text not null,
                    created_at text not null,
                    status text not null
                );

                create table if not exists fields (
                    job_id text not null,
                    name text not null,
                    label text not null,
                    prediction text not null,
                    raw_prediction text,
                    reviewed_value text,
                    confidence real not null,
                    bbox_json text not null,
                    kind text not null,
                    docx_tag text,
                    status text not null,
                    primary key (job_id, name)
                );
                """
            )
            columns = {
                row[1]
                for row in conn.execute("pragma table_info(fields)").fetchall()
            }
            if "raw_prediction" not in columns:
                conn.execute("alter table fields add column raw_prediction text")

    def save_job(self, job: OcrJob, status: str = "pending_review") -> None:
        with self._connect() as conn:
            conn.execute(
                """
                insert or replace into jobs (id, image_path, pattern_name, created_at, status)
                values (?, ?, ?, ?, ?)
                """,
                (
                    job.id,
                    str(job.image_path),
                    job.pattern_name,
                    job.created_at.isoformat() + "Z",
                    status,
                ),
            )
            for item in job.fields:
                conn.execute(
                    """
                    insert or replace into fields
                    (job_id, name, label, prediction, raw_prediction, reviewed_value, confidence, bbox_json, kind, docx_tag, status)
                    values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        job.id,
                        item.name,
                        item.label,
                        item.prediction,
                        item.raw_prediction,
                        item.reviewed_value,
                        item.confidence,
                        json.dumps(item.bbox),
                        item.kind,
                        item.docx_tag,
                        item.status,
                    ),
                )

    def count_jobs(self) -> int:
        with self._connect() as conn:
            return int(conn.execute("select count(*) from jobs").fetchone()[0])
