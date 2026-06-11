from __future__ import annotations

import contextlib
import io
import os
import re
import sys
from pathlib import Path
from typing import Any

from .domain import AnchorConfig, BBox, FieldResult, OcrJob, PatternConfig


PageText = tuple[str, BBox, float]


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

    def recognize_layout(self, image) -> list[PageText]:
        text, confidence = self.recognize(image)
        return [(text, (0.0, 0.0, 1.0, 1.0), confidence)] if text else []


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

    def recognize_layout(self, image) -> list[PageText]:
        with _quiet_external_output(enabled=not self.verbose):
            try:
                result = self._ocr.predict(image)
            except AttributeError:
                result = self._ocr.ocr(image, cls=True)
        height, width = image.shape[:2] if image is not None else (1, 1)
        return _extract_page_text_items(result, width, height)


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


def _extract_page_text_items(result: Any, width: int, height: int) -> list[PageText]:
    items: list[PageText] = []

    def normalize_box(box: Any) -> BBox | None:
        if not isinstance(box, (list, tuple)) or not box:
            return None
        try:
            if len(box) == 4 and all(isinstance(item, (int, float)) for item in box):
                x1, y1, x2, y2 = (float(item) for item in box)
            else:
                xs = [float(point[0]) for point in box]
                ys = [float(point[1]) for point in box]
                x1, y1, x2, y2 = min(xs), min(ys), max(xs), max(ys)
        except Exception:
            return None
        return (
            max(0.0, min(1.0, x1 / width)),
            max(0.0, min(1.0, y1 / height)),
            max(0.0, min(1.0, x2 / width)),
            max(0.0, min(1.0, y2 / height)),
        )

    def add_item(text: Any, box: Any, score: Any = 0.0) -> None:
        value = str(text).strip()
        bbox = normalize_box(box)
        if value and bbox:
            try:
                confidence = float(score)
            except Exception:
                confidence = 0.0
            items.append((value, bbox, confidence))

    def visit(value: Any) -> None:
        if value is None:
            return
        if isinstance(value, dict):
            texts = value.get("rec_texts") or value.get("texts")
            boxes = value.get("rec_boxes") or value.get("dt_polys") or value.get("boxes")
            scores = value.get("rec_scores") or value.get("scores") or []
            if isinstance(texts, list) and isinstance(boxes, list):
                for index, text in enumerate(texts):
                    score = scores[index] if isinstance(scores, list) and index < len(scores) else 0.0
                    add_item(text, boxes[index], score)
            if "text" in value and any(key in value for key in ("box", "bbox", "points")):
                add_item(value["text"], value.get("box") or value.get("bbox") or value.get("points"), value.get("score", 0.0))
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
            if len(value) == 2 and isinstance(value[0], (list, tuple)) and isinstance(value[1], (list, tuple)) and len(value[1]) == 2:
                text, score = value[1]
                add_item(text, value[0], score)
                return
            for item in value:
                visit(item)

    visit(result)
    return items


def create_ocr_engine(prefer_paddle: bool = True, verbose: bool = False) -> OcrEngine:
    if not prefer_paddle:
        return PlaceholderOcrEngine()
    try:
        return PaddleOcrEngine(verbose=verbose)
    except RuntimeError:
        return PlaceholderOcrEngine()


def _find_anchor_item(page_items: list[PageText], anchor: AnchorConfig) -> PageText | None:
    wanted = [_normalize_anchor_text(text) for text in anchor.texts]
    for item in page_items:
        normalized = _normalize_anchor_text(item[0])
        if any(token and token in normalized for token in wanted):
            return item
    return None


def _normalize_anchor_text(text: str) -> str:
    return re.sub(r"[\s:\-_.]+", "", text.strip().lower())


def _bbox_from_anchor(anchor_bbox: BBox, anchor: AnchorConfig) -> BBox:
    left, top, right, bottom = anchor_bbox
    field_height = anchor.height if anchor.height is not None else max(0.01, bottom - top)
    if anchor.side == "left":
        new_right = left - anchor.offset_x + anchor.pad_x
        new_left = new_right - anchor.width
    elif anchor.side == "below":
        new_left = left + anchor.offset_x - anchor.pad_x
        new_right = new_left + anchor.width + (anchor.pad_x * 2)
        top = bottom + anchor.offset_y
        bottom = top + field_height
        return _clamp_bbox((new_left, top - anchor.pad_y, new_right, bottom + anchor.pad_y))
    elif anchor.side == "above":
        new_left = left + anchor.offset_x - anchor.pad_x
        new_right = new_left + anchor.width + (anchor.pad_x * 2)
        bottom = top - anchor.offset_y
        top = bottom - field_height
        return _clamp_bbox((new_left, top - anchor.pad_y, new_right, bottom + anchor.pad_y))
    else:
        new_left = right + anchor.offset_x - anchor.pad_x
        new_right = new_left + anchor.width + (anchor.pad_x * 2)
    new_top = top + anchor.offset_y - anchor.pad_y
    new_bottom = new_top + field_height + (anchor.pad_y * 2)
    return _clamp_bbox((new_left, new_top, new_right, new_bottom))


def _clamp_bbox(bbox: BBox) -> BBox:
    left, top, right, bottom = bbox
    left = max(0.0, min(1.0, left))
    top = max(0.0, min(1.0, top))
    right = max(left + 0.001, min(1.0, right))
    bottom = max(top + 0.001, min(1.0, bottom))
    return left, top, right, bottom


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
        page_items = self._recognize_page_layout(image, pattern) if image is not None else []

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
            if config.kind == "constant":
                fields.append(
                    FieldResult(
                        name=config.name,
                        label=config.label,
                        prediction=config.default_value or "",
                        confidence=1.0,
                        bbox=config.bbox,
                        kind=config.kind,
                        docx_tag=config.docx_tag,
                        raw_prediction="",
                    )
                )
                continue
            crop = (
                self._crop_from_anchor(image, config.anchor, page_items, width, height)
                if image is not None and config.anchor is not None
                else None
            )
            if crop is None:
                crop = self._crop_relative(image, config.bbox, width, height) if image is not None else None
            if config.kind == "checkbox":
                prediction, confidence = self._detect_checkbox(crop)
                raw_prediction = prediction
            else:
                ocr_image = self._prepare_ocr_crop(crop, config.preprocess or config.kind)
                raw_prediction, confidence = self.engine.recognize(ocr_image if ocr_image is not None else image)
                prediction = _normalize_field_prediction(config.kind, raw_prediction)
                if config.default_value and (not prediction.strip() or confidence < 0.6):
                    prediction = config.default_value
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
        self._postprocess_fields(fields)
        return OcrJob(image_path=image_path, pattern_name=pattern.name, fields=fields)

    @staticmethod
    def _crop_relative(image, bbox, width: int, height: int):
        left, top, right, bottom = bbox
        x1 = max(0, min(width, round(left * width)))
        y1 = max(0, min(height, round(top * height)))
        x2 = max(x1 + 1, min(width, round(right * width)))
        y2 = max(y1 + 1, min(height, round(bottom * height)))
        return image[y1:y2, x1:x2]

    def _recognize_page_layout(self, image, pattern: PatternConfig) -> list[PageText]:
        if not any(field.anchor is not None for field in pattern.fields):
            return []
        try:
            return self.engine.recognize_layout(image)
        except Exception:
            return []

    @staticmethod
    def _crop_from_anchor(
        image,
        anchor: AnchorConfig,
        page_items: list[PageText],
        width: int,
        height: int,
    ):
        item = _find_anchor_item(page_items, anchor)
        if item is None:
            return None
        bbox = _bbox_from_anchor(item[1], anchor)
        return OcrService._crop_relative(image, bbox, width, height)

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
        if mode in {"handwriting", "result_choice", "table_date", "case_code"}:
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

    @staticmethod
    def _postprocess_fields(fields: list[FieldResult]) -> None:
        _postprocess_case_code_fields(fields)


def _normalize_result_choice(text: str) -> str:
    normalized = text.strip().lower()
    compact = normalized.replace(" ", "").replace(".", "")
    positive_tokens = ("positive", "pos", "present", "pres", "+", "พบ")
    negative_tokens = ("negative", "neg", "nega", "negati", "absent", "abs", "-", "ไม่พบ")
    if any(token in compact for token in negative_tokens):
        return "negative"
    if any(token in compact for token in positive_tokens):
        return "positive"
    return ""


def _normalize_field_prediction(kind: str, raw_prediction: str) -> str:
    if kind == "result_choice":
        return _normalize_result_choice(raw_prediction)
    if kind == "case_code":
        return _normalize_case_code(raw_prediction)
    if kind == "hospital_name":
        return _normalize_hospital_name(raw_prediction)
    return raw_prediction


def _normalize_case_code(text: str, default_year: str | None = None) -> str:
    raw = text.strip().upper()
    raw = raw.replace(" ", "")
    raw = raw.replace("\\", "/").replace("|", "/")
    raw = raw.replace("O", "0").replace("Q", "0")
    raw = raw.replace("I", "1").replace("L", "1")
    raw = raw.replace("Z", "2")
    raw = raw.replace("S", "5")
    match = re.search(r"([A-Z]?\d{2,4})/(\d{2})", raw)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    prefix_match = re.search(r"([A-Z]?\d{2,4})/?$", raw)
    if prefix_match and default_year:
        return f"{prefix_match.group(1)}/{default_year}"
    digits = re.findall(r"\d", raw)
    if len(digits) >= 5:
        prefix = "".join(digits[:-2])
        year = "".join(digits[-2:])
        return f"{prefix}/{year}"
    if 3 <= len(digits) <= 4 and default_year:
        return f"{''.join(digits)}/{default_year}"
    return text.strip()


def _normalize_hospital_name(text: str) -> str:
    compact = re.sub(r"\s+", "", text.strip())
    if not compact:
        return ""
    known_values = {
        "พระปกเกล้า": "โรงพยาบาลพระปกเกล้า",
        "ปกเกล้า": "โรงพยาบาลพระปกเกล้า",
        "รพ.พระปกเกล้า": "โรงพยาบาลพระปกเกล้า",
        "รพพระปกเกล้า": "โรงพยาบาลพระปกเกล้า",
        "นายายอาม": "โรงพยาบาลนายายอาม",
        "นายาอาม": "โรงพยาบาลนายายอาม",
        "นยายอาม": "โรงพยาบาลนายายอาม",
        "นายยอาม": "โรงพยาบาลนายายอาม",
        "ชายอาม": "โรงพยาบาลนายายอาม",
        "ยอาม": "โรงพยาบาลนายายอาม",
    }
    for token, value in known_values.items():
        if token in compact:
            return value
    if compact.startswith("โรงพยาบาล"):
        return compact
    return text.strip()


def _infer_buddhist_year_suffix(fields: list[FieldResult]) -> str | None:
    for field in fields:
        candidates = [field.prediction, field.raw_prediction or ""]
        for value in candidates:
            match = re.search(r"25(\d{2})", value)
            if match:
                return match.group(1)
    return None


def _looks_like_incomplete_case_code(value: str) -> bool:
    compact = value.strip().upper().replace(" ", "")
    if re.search(r"/\d{2}$", compact):
        return False
    return bool(re.search(r"[A-Z]?\d{2,4}/?$", compact))


def _postprocess_case_code_fields(fields: list[FieldResult]) -> None:
    year = _infer_buddhist_year_suffix(fields)
    if not year:
        return
    for field in fields:
        if field.kind == "case_code" and _looks_like_incomplete_case_code(field.prediction):
            field.prediction = _normalize_case_code(field.raw_prediction or field.prediction, default_year=year)
            if field.reviewed_value is None:
                field.reviewed_value = None
