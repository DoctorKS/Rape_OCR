from __future__ import annotations

import argparse
from pathlib import Path

from .api import create_app
from .config import load_patterns
from .ocr_service import OcrService, PlaceholderOcrEngine
from .recycling import RecyclingDataset
from .storage import AppStorage
from .ui import run_gui


def main() -> int:
    parser = argparse.ArgumentParser(description="Rape OCR local application")
    parser.add_argument("--gui", action="store_true", help="start the native desktop app")
    parser.add_argument("--api", action="store_true", help="start the local FastAPI server")
    parser.add_argument("--sample", type=Path, help="process one image using placeholder OCR")
    args = parser.parse_args()

    if args.gui:
        return run_gui()

    if args.api:
        try:
            import uvicorn
        except ImportError:
            print("uvicorn is not installed. Run: pip install -r requirements.txt")
            return 1
        uvicorn.run(create_app(), host="127.0.0.1", port=8765)
        return 0

    if args.sample:
        patterns = load_patterns()
        service = OcrService(patterns, PlaceholderOcrEngine())
        job = service.process(args.sample)
        AppStorage(Path("data/app.db")).save_job(job)
        metadata_path = RecyclingDataset(Path("data/recycling")).save_reviewed_job(job)
        print(f"job_id={job.id}")
        print(f"pattern={job.pattern_name}")
        print(f"fields={len(job.fields)}")
        print(f"metadata={metadata_path}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

