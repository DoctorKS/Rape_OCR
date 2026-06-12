from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from .domain import BBox
from .recycling import RecyclingDataset, RecyclingEntry


TRAINABLE_KINDS = {"text", "hospital_name", "result_choice", "case_code"}


@dataclass(frozen=True)
class FineTuneDatasetResult:
    output_dir: Path
    train_label_path: Path
    val_label_path: Path
    summary_path: Path
    train_count: int
    val_count: int
    skipped_count: int


@dataclass(frozen=True)
class FineTuneRunResult:
    dataset: FineTuneDatasetResult
    command: tuple[str, ...] | None
    export_command: tuple[str, ...] | None = None
    returncode: int | None = None
    export_returncode: int | None = None
    model_config_path: Path | None = None
    model_config_updated: bool = False


def prepare_finetune_dataset(
    recycling: RecyclingDataset,
    output_dir: Path,
    pattern_name: str | None = None,
    field_names: set[str] | None = None,
    validation_every: int = 5,
) -> FineTuneDatasetResult:
    if validation_every < 2:
        raise ValueError("validation_every must be at least 2")
    output_dir.mkdir(parents=True, exist_ok=True)
    crop_dir = output_dir / "crops"
    crop_dir.mkdir(parents=True, exist_ok=True)

    train_lines: list[str] = []
    val_lines: list[str] = []
    skipped = 0
    sample_index = 0
    for entry in recycling.iter_entries(pattern_name=pattern_name):
        for crop_path, label in _iter_labeled_crops(entry, crop_dir, field_names=field_names):
            sample_index += 1
            line = f"{crop_path.resolve().as_posix()}\t{label}"
            if sample_index % validation_every == 0:
                val_lines.append(line)
            else:
                train_lines.append(line)
        skipped += int(entry.payload.get("_finetune_skipped", 0))
        entry.payload.pop("_finetune_skipped", None)

    train_label_path = output_dir / "train_label.txt"
    val_label_path = output_dir / "val_label.txt"
    train_label_path.write_text("\n".join(train_lines) + ("\n" if train_lines else ""), encoding="utf-8")
    val_label_path.write_text("\n".join(val_lines) + ("\n" if val_lines else ""), encoding="utf-8")

    summary = {
        "pattern_name": pattern_name,
        "field_names": sorted(field_names) if field_names else None,
        "train_count": len(train_lines),
        "val_count": len(val_lines),
        "skipped_count": skipped,
        "train_label_path": str(train_label_path),
        "val_label_path": str(val_label_path),
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return FineTuneDatasetResult(
        output_dir=output_dir,
        train_label_path=train_label_path,
        val_label_path=val_label_path,
        summary_path=summary_path,
        train_count=len(train_lines),
        val_count=len(val_lines),
        skipped_count=skipped,
    )


def build_paddleocr_finetune_command(
    config_path: Path,
    source_dir: Path | None = None,
    overrides: Iterable[str] = (),
    gpus: str = "-1",
) -> tuple[str, ...]:
    root = _resolve_paddleocr_source_dir(source_dir)
    train_script = root / "tools" / "train.py"
    if not train_script.exists():
        raise FileNotFoundError(f"PaddleOCR train script not found: {train_script}")
    override_values = _resolve_training_path_overrides(tuple(overrides))
    cpu_training = _is_cpu_training(gpus)
    if cpu_training and not _has_override(override_values, "Global.use_gpu"):
        override_values = ("Global.use_gpu=False", *override_values)
    override_args = ("-o", *override_values) if override_values else ()
    if cpu_training:
        return (
            sys.executable,
            str(train_script),
            "-c",
            str(config_path),
            *override_args,
        )
    return (
        sys.executable,
        "-m",
        "paddle.distributed.launch",
        "--gpus",
        gpus,
        str(train_script),
        "-c",
        str(config_path),
        *override_args,
    )


def build_paddleocr_export_command(
    config_path: Path,
    checkpoint_path: Path,
    output_dir: Path,
    source_dir: Path | None = None,
    overrides: Iterable[str] = (),
) -> tuple[str, ...]:
    root = _resolve_paddleocr_source_dir(source_dir)
    export_script = root / "tools" / "export_model.py"
    if not export_script.exists():
        raise FileNotFoundError(f"PaddleOCR export script not found: {export_script}")
    return (
        sys.executable,
        str(export_script),
        "-c",
        str(config_path),
        "-o",
        f"Global.checkpoints={_project_path(checkpoint_path)}",
        f"Global.save_inference_dir={_project_path(output_dir)}",
        *tuple(overrides),
    )


def fine_tune_from_dataset(
    recycling: RecyclingDataset,
    output_dir: Path,
    pattern_name: str | None = None,
    field_names: set[str] | None = None,
    validation_every: int = 5,
    config_path: Path | None = None,
    run: bool = False,
    overrides: Iterable[str] = (),
    source_dir: Path | None = None,
    gpus: str = "-1",
    export_checkpoint_path: Path | None = None,
    export_output_dir: Path | None = None,
    export_overrides: Iterable[str] = (),
    run_export: bool = False,
    model_config_path: Path | None = None,
    update_model_config: bool = False,
) -> FineTuneRunResult:
    dataset = prepare_finetune_dataset(
        recycling,
        output_dir,
        pattern_name=pattern_name,
        field_names=field_names,
        validation_every=validation_every,
    )
    train_overrides = (*_dataset_config_overrides(dataset), *tuple(overrides))
    command = (
        build_paddleocr_finetune_command(config_path, source_dir=source_dir, overrides=train_overrides, gpus=gpus)
        if config_path
        else None
    )
    export_command = (
        build_paddleocr_export_command(
            config_path,
            export_checkpoint_path,
            export_output_dir,
            source_dir=source_dir,
            overrides=export_overrides,
        )
        if config_path and export_checkpoint_path and export_output_dir
        else None
    )
    returncode = None
    export_returncode = None
    if run and command is not None:
        completed = subprocess.run(command, cwd=_resolve_paddleocr_source_dir(source_dir), check=False)
        returncode = completed.returncode
    if run_export and export_command is not None:
        completed = subprocess.run(export_command, cwd=_resolve_paddleocr_source_dir(source_dir), check=False)
        export_returncode = completed.returncode
    model_config_updated = False
    if update_model_config and export_output_dir is not None:
        if run_export and export_returncode not in (0, None):
            model_config_updated = False
        else:
            update_ocr_model_config(model_config_path or Path("configs/ocr_models.json"), _project_path(export_output_dir))
            model_config_updated = True
    return FineTuneRunResult(
        dataset=dataset,
        command=command,
        export_command=export_command,
        returncode=returncode,
        export_returncode=export_returncode,
        model_config_path=model_config_path or Path("configs/ocr_models.json") if model_config_updated else None,
        model_config_updated=model_config_updated,
    )


def reviewed_dataset_output_dir(base_dir: Path = Path("data/finetune")) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return base_dir / f"reviewed_{timestamp}"


def update_ocr_model_config(config_path: Path, text_recognition_model_dir: Path) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, str] = {}
    if config_path.exists():
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                payload = {str(key): str(value) for key, value in data.items() if value is not None}
        except json.JSONDecodeError:
            payload = {}
    payload["text_recognition_model_dir"] = _model_config_path_value(text_recognition_model_dir)
    config_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _resolve_paddleocr_source_dir(source_dir: Path | None = None) -> Path:
    raw = source_dir or os.environ.get("PADDLEOCR_SOURCE_DIR")
    if not raw:
        raise ValueError(
            "PaddleOCR source dir is required for training/export. "
            "Set PADDLEOCR_SOURCE_DIR or pass --paddleocr-source-dir."
        )
    root = Path(raw).expanduser().resolve()
    if not root.exists():
        raise FileNotFoundError(f"PaddleOCR source dir not found: {root}")
    return root


def _dataset_config_overrides(dataset: FineTuneDatasetResult) -> tuple[str, ...]:
    train_label = dataset.train_label_path.resolve().as_posix()
    val_label = dataset.val_label_path.resolve().as_posix()
    return (
        "Train.dataset.data_dir=.",
        f"Train.dataset.label_file_list={json.dumps([train_label])}",
        "Eval.dataset.data_dir=.",
        f"Eval.dataset.label_file_list={json.dumps([val_label])}",
    )


def _is_cpu_training(gpus: str | None) -> bool:
    if gpus is None:
        return True
    return str(gpus).strip().lower() in {"", "-1", "cpu", "none"}


def _has_override(overrides: Iterable[str], dotted_key: str) -> bool:
    prefix = f"{dotted_key}="
    return any(str(item).strip().startswith(prefix) for item in overrides)


def _resolve_training_path_overrides(overrides: Iterable[str]) -> tuple[str, ...]:
    path_keys = {"Global.save_model_dir", "Global.pretrained_model"}
    resolved: list[str] = []
    for item in overrides:
        text = str(item)
        key, separator, value = text.partition("=")
        if separator and key in path_keys:
            resolved.append(f"{key}={_project_path(Path(value))}")
        else:
            resolved.append(text)
    return tuple(resolved)


def _project_path(path: Path) -> Path:
    expanded = path.expanduser()
    return expanded if expanded.is_absolute() else (Path.cwd() / expanded).resolve()


def _model_config_path_value(path: Path) -> str:
    resolved = _project_path(path)
    try:
        return str(resolved.relative_to(Path.cwd()))
    except ValueError:
        return str(resolved)


def _iter_labeled_crops(
    entry: RecyclingEntry,
    crop_dir: Path,
    field_names: set[str] | None = None,
):
    cv2 = _load_cv2()
    image_path = _resolve_payload_image(entry.payload, entry.entry_dir)
    if cv2 is None or image_path is None:
        entry.payload["_finetune_skipped"] = len(entry.payload.get("fields", []))
        return
    image = cv2.imread(str(image_path))
    if image is None:
        entry.payload["_finetune_skipped"] = len(entry.payload.get("fields", []))
        return
    height, width = image.shape[:2]
    skipped = 0
    for field in entry.payload.get("fields", []):
        if not isinstance(field, dict):
            skipped += 1
            continue
        name = str(field.get("name", ""))
        if field_names and name not in field_names:
            continue
        if str(field.get("kind", "text")) not in TRAINABLE_KINDS:
            continue
        label = _label_from_field(field)
        bbox = _bbox_from_field(field)
        if not label or bbox is None:
            skipped += 1
            continue
        crop = _crop_relative(image, bbox, width, height)
        if crop is None:
            skipped += 1
            continue
        target = crop_dir / f"{entry.entry_dir.name}_{name}.png"
        cv2.imwrite(str(target), crop)
        yield target, label
    entry.payload["_finetune_skipped"] = skipped


def _label_from_field(field: dict) -> str:
    for key in ("reviewed_value", "final_value", "prediction"):
        value = field.get(key)
        if value is None:
            continue
        label = str(value).strip()
        if label and label != "-":
            return label
    return ""


def _bbox_from_field(field: dict) -> BBox | None:
    bbox = field.get("bbox")
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    try:
        left, top, right, bottom = (float(item) for item in bbox)
    except Exception:
        return None
    return left, top, right, bottom


def _crop_relative(image, bbox: BBox, width: int, height: int):
    left, top, right, bottom = bbox
    x1 = max(0, min(width, round(left * width)))
    y1 = max(0, min(height, round(top * height)))
    x2 = max(x1 + 1, min(width, round(right * width)))
    y2 = max(y1 + 1, min(height, round(bottom * height)))
    return image[y1:y2, x1:x2]


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


def _load_cv2():
    try:
        import cv2
    except Exception:
        return None
    return cv2
