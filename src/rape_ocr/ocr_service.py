from __future__ import annotations

import contextlib
import io
import os
import sys
from pathlib import Path
from typing import Any

from .domain import FieldResult, OcrJob, PatternConfig


def _load_cv2():
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            import cv2
    except Exception:
        return None
    return cv2


class OcrEngine:
    name = "base"

    def recognize(self, image) -> tuple[str, float]:
        raise NotImplementedError


class PlaceholderOcrEngine(OcrEngine):
    name = "placeholder"

    def recognize(self, image) -> tuple[str, float]:
        return "", 0.0


class PaddleOcrEngine(OcrEngine):
    name = "paddleocr"

    def __init__(self, lang: str = "th", verbose: bool = False) -> None:
        self.verbose = verbose
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        os.environ.setdefault("GLOG_minloglevel", "2")
        with _quiet_external_output(enabled=not verbose):
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise RuntimeError(
                    "PaddleOCR is not installed. Install optional dependencies first."
                ) from exc
            self._ocr = PaddleOCR(use_angle_cls=True, lang=lang)

    def recognize(self, image) -> tuple[str, float]:
        with _quiet_external_output(enabled=not self.verbose):
            try:
                result = self._ocr.predict(image)
            except AttributeError:
                result = self._ocr.ocr(image, cls=True)
        texts, scores = _extract_ocr_text_scores(result)
        if not texts:
            return "", 0.0
        return " ".join(texts), sum(scores) / len(scores)


@contextlib.contextmanager
def _quiet_external_output(enabled: bool = True):
    if not enabled:
        yield
        return
    stdout_fd = sys.stdout.fileno()
    stderr_fd = sys.stderr.fileno()
    saved_stdout_fd = os.dup(stdout_fd)
    saved_stderr_fd = os.dup(stderr_fd)
    try:
        with open(os.devnull, "w", encoding="utf-8") as devnull:
            sys.stdout.flush()
            sys.stderr.flush()
            os.dup2(devnull.fileno(), stdout_fd)
            os.dup2(devnull.fileno(), stderr_fd)
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                yield
    finally:
        sys.stdout.flush()
        sys.stderr.flush()
        os.dup2(saved_stdout_fd, stdout_fd)
        os.dup2(saved_stderr_fd, stderr_fd)
        os.close(saved_stdout_fd)
        os.close(saved_stderr_fd)


def _extract_ocr_text_scores(result: Any) -> tuple[list[str], list[float]]:
    texts: list[str] = []
    scores: list[float] = []

    def visit(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            for key in ("rec_texts", "texts"):
                if key in value and isinstance(value[key], list):
                    texts.extend(str(item) for item in value[key] if item)
            for key in ("rec_scores", "scores"):
                if key in value and isinstance(value[key], list):
                    scores.extend(float(item) for item in value[key] if item is not None)
            if "text" in value:
                texts.append(str(value["text"]))
            if "score" in value:
                scores.append(float(value["score"]))
            for item in value.values():
                if isinstance(item, (dict, list, tuple)):
                    visit(item)
            return
        if hasattr(value, "json"):
            try:
                visit(value.json)
            except Exception:
                pass
        if hasattr(value, "res"):
            try:
                visit(value.res)
            except Exception:
                pass
        if isinstance(value, (list, tuple)):
            if len(value) == 2 and isinstance(value[1], (list, tuple)) and len(value[1]) == 2:
                text, score = value[1]
                texts.append(str(text))
                scores.append(float(score))
                return
            for item in value:
                visit(item)

    visit(result)
    if texts and not scores:
        scores = [0.0 for _ in texts]
    return texts, scores


def create_ocr_engine(prefer_paddle: bool = True, verbose: bool = False) -> OcrEngine:
    if not prefer_paddle:
        return PlaceholderOcrEngine()
    try:
        return PaddleOcrEngine(verbose=verbose)
    except RuntimeError:
        return PlaceholderOcrEngine()


class OcrService:
    def __init__(self, patterns: dict[str, PatternConfig], engine: OcrEngine | None = None) -> None:
        self.patterns = patterns
        self.engine = engine or PlaceholderOcrEngine()

    def detect_pattern(self, image_path: Path) -> str:
        name = image_path.name.lower()
        if "29351955" in name:
            return "rural_rape"
        if "29351956" in name or "29351957" in name:
            return "ppk_rape"
        return "ppk_rape"

    def process(
        self,
        image_path: Path,
        pattern_name: str | None = None,
        skipped_fields: set[str] | None = None,
    ) -> OcrJob:
        cv2 = _load_cv2()
        image = cv2.imread(str(image_path)) if cv2 is not None else None
        if image is None:
            width, height = 1, 1
        else:
            height, width = image.shape[:2]
        selected_pattern = pattern_name or self.detect_pattern(image_path)
        pattern = self.patterns[selected_pattern]
        skip = skipped_fields or set()

        fields: list[FieldResult] = []
        for config in pattern.fields:
            if config.name in skip:
                fields.append(
                    FieldResult(
                        name=config.name,
                        label=config.label,
                        prediction="-",
                        confidence=1.0,
                        bbox=config.bbox,
                        kind=config.kind,
                        docx_tag=config.docx_tag,
                        raw_prediction="",
                        reviewed_value="-",
                        status="skipped",
                    )
                )
                continue
            crop = self._crop_relative(image, config.bbox, width, height) if image is not None else None
            if config.kind == "checkbox":
                prediction, confidence = self._detect_checkbox(crop)
                raw_prediction = prediction
            else:
                ocr_image = self._prepare_ocr_crop(crop, config.preprocess or config.kind)
                raw_prediction, confidence = self.engine.recognize(ocr_image if ocr_image is not None else image)
                prediction = (
                    _normalize_result_choice(raw_prediction)
                    if config.kind == "result_choice"
                    else raw_prediction
                )
            fields.append(
                FieldResult(
                    name=config.name,
                    label=config.label,
                    prediction=prediction,
                    confidence=confidence,
                    bbox=config.bbox,
                    kind=config.kind,
                    docx_tag=config.docx_tag,
                    raw_prediction=raw_prediction,
                )
            )
        return OcrJob(image_path=image_path, pattern_name=pattern.name, fields=fields)

    @staticmethod
    def _crop_relative(image, bbox, width: int, height: int):
        left, top, right, bottom = bbox
        x1 = max(0, min(width, round(left * width)))
        y1 = max(0, min(height, round(top * height)))
        x2 = max(x1 + 1, min(width, round(right * width)))
        y2 = max(y1 + 1, min(height, round(bottom * height)))
        return image[y1:y2, x1:x2]

    @staticmethod
    def _detect_checkbox(crop) -> tuple[str, float]:
        if crop is None:
            return "unchecked", 0.0
        cv2 = _load_cv2()
        if cv2 is None:
            return "unchecked", 0.0
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        dark_ratio = float((gray < 128).mean())
        return ("checked" if dark_ratio > 0.08 else "unchecked"), min(1.0, dark_ratio * 8)

    @staticmethod
    def _prepare_ocr_crop(crop, mode: str | None):
        if crop is None:
            return None
        cv2 = _load_cv2()
        if cv2 is None:
            return crop
        if mode in {"handwriting", "result_choice", "table_date"}:
            scale = 3 if mode == "result_choice" else 4
            enlarged = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(enlarged, cv2.COLOR_BGR2GRAY)
            threshold = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                9,
            )
            return cv2.cvtColor(threshold, cv2.COLOR_GRAY2BGR)
        return crop


def _normalize_result_choice(text: str) -> str:
    normalized = text.strip().lower()
    compact = normalized.replace(" ", "").replace(".", "")
    positive_tokens = ("positive", "pos", "present", "pres", "+", "พบ")
    negative_tokens = ("negative", "neg", "nega", "negati", "absent", "abs", "-", "ไม่พบ")
    if any(token in compact for token in negative_tokens):
        return "negative"
    if any(token in compact for token in positive_tokens):
        return "positive"
    return text.strip()
