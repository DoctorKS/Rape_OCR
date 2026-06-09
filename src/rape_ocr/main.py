from __future__ import annotations

import argparse
from pathlib import Path

from .api import create_app
from .config import load_patterns
from .dataset_reprocess import DatasetReprocessor
from .ocr_service import OcrService, create_ocr_engine
from .recycling import RecyclingDataset
from .storage import AppStorage
from .ui import run_gui


def main() -> int:
    parser = argparse.ArgumentParser(description="Rape OCR local application")
    parser.add_argument("--gui", action="store_true", help="start the native desktop app")
    parser.add_argument("--api", action="store_true", help="start the local FastAPI server")
    parser.add_argument("--sample", type=Path, help="process one image using the configured OCR engine")
    parser.add_argument(
        "--placeholder-ocr",
        action="store_true",
        help="force placeholder OCR for pipeline tests without PaddleOCR",
    )
    parser.add_argument(
        "--verbose-ocr",
        action="store_true",
        help="show PaddleOCR/Paddle model logs",
    )
    parser.add_argument(
        "--cleanup-recycling-days",
        type=int,
        help="list or delete recycling dataset entries older than this many days",
    )
    parser.add_argument(
        "--delete-recycling-entry",
        help="delete one recycling entry by relative path, e.g. rural_rape/20260609T000000Z_jobid",
    )
    parser.add_argument(
        "--confirm-delete",
        action="store_true",
        help="actually delete recycling entries; without this flag deletion commands are dry-run only",
    )
    parser.add_argument(
        "--reprocess-recycling",
        action="store_true",
        help="re-run OCR on existing recycling metadata to refresh anchor crop evidence",
    )
    parser.add_argument(
        "--reprocess-pattern",
        help="limit --reprocess-recycling to one pattern, e.g. ppk_rape",
    )
    parser.add_argument(
        "--reprocess-entry",
        help="limit --reprocess-recycling to one relative entry path",
    )
    parser.add_argument(
        "--confirm-reprocess",
        action="store_true",
        help="write new recycling entries during reprocess; without this flag it is dry-run only",
    )
    args = parser.parse_args()

    if args.cleanup_recycling_days is not None:
        result = RecyclingDataset(Path("data/recycling")).cleanup_old_entries(
            older_than_days=args.cleanup_recycling_days,
            dry_run=not args.confirm_delete,
        )
        action = "would_delete" if result.dry_run else "deleted"
        print(f"cutoff={result.cutoff.isoformat()}Z")
        print(f"mode={'dry-run' if result.dry_run else 'delete'}")
        print(f"matched={len(result.matched_dirs)}")
        print(f"{action}={len(result.deleted_dirs) if not result.dry_run else len(result.matched_dirs)}")
        for path in result.deleted_dirs if not result.dry_run else result.matched_dirs:
            print(path)
        return 0

    if args.delete_recycling_entry:
        result = RecyclingDataset(Path("data/recycling")).delete_entry(
            args.delete_recycling_entry,
            dry_run=not args.confirm_delete,
        )
        print(f"mode={'dry-run' if result.dry_run else 'delete'}")
        print(f"entry={result.entry_dir}")
        print(f"deleted={result.deleted}")
        return 0

    if args.reprocess_recycling:
        patterns = load_patterns()
        service = OcrService(
            patterns,
            create_ocr_engine(
                prefer_paddle=not args.placeholder_ocr,
                verbose=args.verbose_ocr,
            ),
        )
        storage = AppStorage(Path("data/app.db"))
        result = DatasetReprocessor(
            RecyclingDataset(Path("data/recycling")),
            service,
            storage=storage,
        ).reprocess(
            pattern_name=args.reprocess_pattern,
            entry=args.reprocess_entry,
            dry_run=not args.confirm_reprocess,
        )
        print(f"mode={'dry-run' if result.dry_run else 'write'}")
        print(f"items={len(result.items)}")
        print(f"processed={result.processed_count}")
        print(f"skipped={result.skipped_count}")
        print(f"errors={result.error_count}")
        for item in result.items:
            print(
                f"{item.status} pattern={item.pattern_name} "
                f"source={item.source_metadata} image={item.image_path} "
                f"output={item.output_metadata} message={item.message}"
            )
        return 0

    if args.gui:
        return run_gui()

    if args.api:
        try:
            import uvicorn
        except ImportError:
            print("uvicorn is not installed. Run: pip install -r requirements.txt")
            return 1
        uvicorn.run(create_app(verbose_ocr=args.verbose_ocr), host="127.0.0.1", port=8765)
        return 0

    if args.sample:
        patterns = load_patterns()
        service = OcrService(
            patterns,
            create_ocr_engine(
                prefer_paddle=not args.placeholder_ocr,
                verbose=args.verbose_ocr,
            ),
        )
        storage = AppStorage(Path("data/app.db"))
        pattern_name = service.detect_pattern(args.sample)
        job = service.process(
            args.sample,
            pattern_name=pattern_name,
            skipped_fields=storage.get_skipped_fields(pattern_name),
        )
        storage.save_job(job)
        metadata_path = RecyclingDataset(Path("data/recycling")).save_reviewed_job(job)
        print(f"job_id={job.id}")
        print(f"pattern={job.pattern_name}")
        print(f"ocr_engine={service.engine.name}")
        print(f"fields={len(job.fields)}")
        print(f"metadata={metadata_path}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
