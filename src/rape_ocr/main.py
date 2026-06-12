from __future__ import annotations

import argparse
from pathlib import Path

from .api import create_app
from .config import load_patterns
from .dataset_reprocess import DatasetReprocessor
from .ocr_service import OcrService, create_ocr_engine
from .recycling import RecyclingDataset
from .storage import AppStorage
from .training import fine_tune_from_dataset, reviewed_dataset_output_dir
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
    parser.add_argument(
        "--prepare-finetune-dataset",
        type=Path,
        help="export reviewed recycling crops and labels for PaddleOCR fine-tuning",
    )
    parser.add_argument(
        "--train-reviewed-dataset",
        action="store_true",
        help="prepare all reviewed recycling data for fine-tuning, then optionally train/export",
    )
    parser.add_argument(
        "--finetune-pattern",
        help="limit fine-tune dataset export to one pattern, e.g. rural_rape",
    )
    parser.add_argument(
        "--finetune-fields",
        help="comma-separated field names to include in fine-tune dataset",
    )
    parser.add_argument(
        "--finetune-validation-every",
        type=int,
        default=5,
        help="put every Nth labeled crop into validation set",
    )
    parser.add_argument(
        "--paddleocr-train-config",
        type=Path,
        help="PaddleOCR train config path; when provided, prints or runs the train command",
    )
    parser.add_argument(
        "--paddleocr-source-dir",
        type=Path,
        help="PaddleOCR source checkout containing tools/train.py and tools/export_model.py",
    )
    parser.add_argument(
        "--finetune-gpus",
        default="-1",
        help="GPU ids for paddle.distributed.launch, e.g. 0; use -1/cpu for single-process CPU training",
    )
    parser.add_argument(
        "--finetune-override",
        action="append",
        default=[],
        help="extra PaddleOCR -o override, repeatable",
    )
    parser.add_argument(
        "--run-finetune",
        action="store_true",
        help="actually run PaddleOCR training after preparing labels",
    )
    parser.add_argument(
        "--export-finetune-checkpoint",
        type=Path,
        help="checkpoint prefix/path to export after fine-tuning",
    )
    parser.add_argument(
        "--export-finetune-dir",
        type=Path,
        help="inference model output dir for exported fine-tuned model",
    )
    parser.add_argument(
        "--export-finetune-override",
        action="append",
        default=[],
        help="extra PaddleOCR export -o override, repeatable",
    )
    parser.add_argument(
        "--run-finetune-export",
        action="store_true",
        help="actually run PaddleOCR export_model.py after preparing labels",
    )
    parser.add_argument(
        "--update-ocr-model-config",
        action="store_true",
        help="write the exported recognition model dir into configs/ocr_models.json",
    )
    args = parser.parse_args()

    if args.prepare_finetune_dataset or args.train_reviewed_dataset:
        output_dir = args.prepare_finetune_dataset or reviewed_dataset_output_dir()
        field_names = (
            {item.strip() for item in args.finetune_fields.split(",") if item.strip()}
            if args.finetune_fields
            else None
        )
        try:
            result = fine_tune_from_dataset(
                RecyclingDataset(Path("data/recycling")),
                output_dir,
                pattern_name=args.finetune_pattern,
                field_names=field_names,
                validation_every=args.finetune_validation_every,
                config_path=args.paddleocr_train_config,
                run=args.run_finetune,
                overrides=args.finetune_override,
                source_dir=args.paddleocr_source_dir,
                gpus=args.finetune_gpus,
                export_checkpoint_path=args.export_finetune_checkpoint,
                export_output_dir=args.export_finetune_dir,
                export_overrides=args.export_finetune_override,
                run_export=args.run_finetune_export,
                update_model_config=args.update_ocr_model_config,
            )
        except (FileNotFoundError, ValueError) as exc:
            print(f"fine-tune setup error: {exc}")
            print("Install or clone PaddleOCR source first, for example:")
            print("git clone https://github.com/PaddlePaddle/PaddleOCR.git C:\\dev\\PaddleOCR")
            print("Then rerun with --paddleocr-source-dir C:\\dev\\PaddleOCR")
            return 2
        print(f"output_dir={result.dataset.output_dir}")
        print(f"train_label={result.dataset.train_label_path}")
        print(f"val_label={result.dataset.val_label_path}")
        print(f"summary={result.dataset.summary_path}")
        print(f"train_count={result.dataset.train_count}")
        print(f"val_count={result.dataset.val_count}")
        print(f"skipped_count={result.dataset.skipped_count}")
        if result.command:
            print("command=" + " ".join(result.command))
            print(f"ran={args.run_finetune}")
            if result.returncode is not None:
                print(f"returncode={result.returncode}")
        if result.export_command:
            print("export_command=" + " ".join(result.export_command))
            print(f"export_ran={args.run_finetune_export}")
            if result.export_returncode is not None:
                print(f"export_returncode={result.export_returncode}")
        if result.model_config_updated:
            print(f"model_config_updated={result.model_config_path}")
        return result.returncode or result.export_returncode or 0

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
