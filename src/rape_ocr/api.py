from __future__ import annotations

from pathlib import Path

from .config import load_patterns
from .ocr_service import OcrService, create_ocr_engine
from .recycling import RecyclingDataset
from .storage import AppStorage
from .template_service import DocxTemplateService


def create_app(data_dir: Path | None = None, prefer_paddle: bool = True, verbose_ocr: bool = False):
    try:
        from fastapi import FastAPI
        from pydantic import BaseModel
    except ImportError as exc:
        raise RuntimeError("FastAPI is not installed. Install optional dependencies first.") from exc

    root = data_dir or Path("data")
    storage = AppStorage(root / "app.db")
    recycling = RecyclingDataset(root / "recycling")
    ocr = OcrService(load_patterns(), create_ocr_engine(prefer_paddle=prefer_paddle, verbose=verbose_ocr))
    templates = DocxTemplateService()
    app = FastAPI(title="Rape OCR Local API", version="0.1.0")
    jobs = {}

    class ImportRequest(BaseModel):
        image_path: str
        pattern_name: str | None = None

    class ReviewFieldRequest(BaseModel):
        name: str
        reviewed_value: str

    class ReviewRequest(BaseModel):
        fields: list[ReviewFieldRequest]

    class ExportRequest(BaseModel):
        template_path: str
        output_path: str

    @app.get("/health")
    def health():
        return {"status": "ok", "offline": True, "ocr_engine": ocr.engine.name}

    @app.get("/patterns")
    def patterns():
        return [{"name": item.name, "display_name": item.display_name} for item in ocr.patterns.values()]

    @app.post("/jobs")
    def create_job(request: ImportRequest):
        image_path = Path(request.image_path)
        pattern_name = request.pattern_name or ocr.detect_pattern(image_path)
        job = ocr.process(
            image_path,
            pattern_name=pattern_name,
            skipped_fields=storage.get_skipped_fields(pattern_name),
        )
        jobs[job.id] = job
        storage.save_job(job)
        return job.reviewed_payload()

    @app.post("/jobs/{job_id}/review")
    def review_job(job_id: str, request: ReviewRequest):
        job = jobs[job_id]
        values = {item.name: item.reviewed_value for item in request.fields}
        for field in job.fields:
            if field.name in values:
                field.reviewed_value = values[field.name]
                field.status = "reviewed"
        storage.save_job(job, status="reviewed")
        metadata_path = recycling.save_reviewed_job(job)
        return {"job_id": job.id, "metadata_path": str(metadata_path)}

    @app.post("/jobs/{job_id}/export")
    def export_job(job_id: str, request: ExportRequest):
        job = jobs[job_id]
        values = {
            field.docx_tag or field.name: field.final_value
            for field in job.fields
            if field.final_value
        }
        output_path = templates.fill(Path(request.template_path), Path(request.output_path), values)
        return {"job_id": job.id, "output_path": str(output_path)}

    return app
