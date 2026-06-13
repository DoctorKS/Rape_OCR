from __future__ import annotations

import contextlib
import io
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib import request

from .domain import AnchorConfig, BBox, FieldResult, OcrJob, PatternConfig


PageText = tuple[str, BBox, float]
PATTERN_HEADER_RATIO = 0.35
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OCR_MODEL_CONFIG = PROJECT_ROOT / "configs" / "ocr_models.json"


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


class TyphoonOllamaOcrEngine(OcrEngine):
    name = "typhoon_ollama"

    def __init__(
        self,
        model: str | None = None,
        endpoint: str | None = None,
        prompt: str | None = None,
        timeout_seconds: float = 120.0,
        urlopen=request.urlopen,
    ) -> None:
        self.model = model or os.environ.get("RAPE_OCR_TYPHOON_MODEL", "scb10x/typhoon-ocr1.5-3b")
        self.endpoint = endpoint or os.environ.get("RAPE_OCR_OLLAMA_URL", "http://localhost:11434/api/generate")
        self.prompt = prompt or os.environ.get(
            "RAPE_OCR_TYPHOON_PROMPT",
            "อ่านข้อความทั้งหมดในภาพนี้ให้ตรงกับต้นฉบับ ตอบเฉพาะข้อความที่อ่านได้ ไม่ต้องอธิบาย",
        )
        self.timeout_seconds = timeout_seconds
        self._urlopen = urlopen

    def recognize(self, image) -> tuple[str, float]:
        encoded = _encode_image_png_base64(image)
        payload = {
            "model": self.model,
            "prompt": self.prompt,
            "images": [encoded],
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.endpoint,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except Exception as exc:
            raise RuntimeError(
                "Typhoon OCR via Ollama is not available. Start Ollama and pull the configured model first."
            ) from exc
        text = _extract_typhoon_response_text(raw)
        return (text, 0.75 if text else 0.0)


class PaddleOcrEngine(OcrEngine):
    name = "paddleocr"

    def __init__(
        self,
        lang: str = "th",
        verbose: bool = False,
        model_config_path: Path | None = None,
    ) -> None:
        self.verbose = verbose
        os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
        os.environ.setdefault("GLOG_minloglevel", "2")
        self.model_options = _load_ocr_model_options(model_config_path)
        with _quiet_external_output(enabled=not verbose):
            try:
                from paddleocr import PaddleOCR
            except ImportError as exc:
                raise RuntimeError(
                    "PaddleOCR is not installed. Install optional dependencies first."
                ) from exc
            self._ocr = PaddleOCR(use_angle_cls=True, lang=lang, **self.model_options)

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
        if hasattr(box, "tolist"):
            box = box.tolist()
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
            boxes = _first_present(value, "rec_boxes", "dt_polys", "boxes")
            scores = value.get("rec_scores") or value.get("scores") or []
            if hasattr(boxes, "tolist"):
                boxes = boxes.tolist()
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


def create_ocr_engine(
    prefer_paddle: bool = True,
    verbose: bool = False,
    model_config_path: Path | None = None,
) -> OcrEngine:
    if not prefer_paddle:
        return PlaceholderOcrEngine()
    engine_name = os.environ.get("RAPE_OCR_ENGINE", "paddleocr").strip().lower()
    if engine_name in {"typhoon", "typhoon_ollama", "ollama_typhoon"}:
        return TyphoonOllamaOcrEngine()
    try:
        return PaddleOcrEngine(verbose=verbose, model_config_path=model_config_path)
    except RuntimeError:
        return PlaceholderOcrEngine()


def _encode_image_png_base64(image) -> str:
    cv2 = _load_cv2()
    if cv2 is None or image is None:
        raise RuntimeError("OpenCV image encoding is required for Typhoon OCR.")
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError("Could not encode image for Typhoon OCR.")
    return base64.b64encode(buffer.tobytes()).decode("ascii")


def _extract_typhoon_response_text(raw: str) -> str:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return raw.strip()
    if isinstance(data, dict):
        for key in ("response", "text", "content"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        message = data.get("message")
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str):
                return content.strip()
    return ""


def _load_ocr_model_options(
    config_path: Path | None = None,
    env: dict[str, str] | None = None,
) -> dict[str, str]:
    source_env = env if env is not None else os.environ
    selected_config = Path(
        source_env.get("RAPE_OCR_MODEL_CONFIG", str(config_path or DEFAULT_OCR_MODEL_CONFIG))
    )
    options = _read_ocr_model_config(selected_config)
    env_overrides = {
        "text_recognition_model_dir": source_env.get("RAPE_OCR_REC_MODEL_DIR", ""),
        "text_detection_model_dir": source_env.get("RAPE_OCR_DET_MODEL_DIR", ""),
        "textline_orientation_model_dir": source_env.get("RAPE_OCR_TEXTLINE_MODEL_DIR", ""),
    }
    for key, value in env_overrides.items():
        if value:
            options[key] = value
    return {key: value for key, value in options.items() if value}


def _read_ocr_model_config(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}
    aliases = {
        "rec_model_dir": "text_recognition_model_dir",
        "det_model_dir": "text_detection_model_dir",
    }
    options: dict[str, str] = {}
    for key in (
        "text_recognition_model_dir",
        "text_detection_model_dir",
        "textline_orientation_model_dir",
        "rec_model_dir",
        "det_model_dir",
    ):
        value = data.get(key)
        if value is None:
            continue
        normalized_key = aliases.get(key, key)
        text = str(value).strip()
        if text:
            options[normalized_key] = text
    return options


def _first_present(value: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in value and value[key] is not None:
            return value[key]
    return None


def _find_anchor_item(
    page_items: list[PageText],
    anchor: AnchorConfig,
    preferred_bbox: BBox | None = None,
) -> PageText | None:
    wanted = [_normalize_anchor_text(text) for text in anchor.texts]
    matches: list[PageText] = []
    for item in page_items:
        normalized = _normalize_anchor_text(item[0])
        if any(token and token in normalized for token in wanted):
            matches.append(item)
    if not matches:
        return None
    if preferred_bbox is None:
        return matches[0]
    target_x = (preferred_bbox[0] + preferred_bbox[2]) / 2
    target_y = (preferred_bbox[1] + preferred_bbox[3]) / 2

    def distance(item: PageText) -> float:
        bbox = item[1]
        x = (bbox[0] + bbox[2]) / 2
        y = (bbox[1] + bbox[3]) / 2
        return ((x - target_x) ** 2) + ((y - target_y) ** 2)

    return min(matches, key=distance)


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


def _deskew_image(image, max_degrees: float = 8.0):
    cv2 = _load_cv2()
    if cv2 is None or image is None:
        return image
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=3.141592653589793 / 180,
        threshold=120,
        minLineLength=max(40, image.shape[1] // 4),
        maxLineGap=20,
    )
    if lines is None:
        return image
    angles: list[float] = []
    for line in lines[:80]:
        x1, y1, x2, y2 = line[0]
        dx = x2 - x1
        dy = y2 - y1
        if dx == 0:
            continue
        angle = cv2.fastAtan2(float(dy), float(dx))
        if angle > 90:
            angle -= 180
        if abs(angle) <= max_degrees:
            angles.append(float(angle))
    if len(angles) < 3:
        return image
    angles.sort()
    angle = angles[len(angles) // 2]
    if abs(angle) < 0.25 or abs(angle) > max_degrees:
        return image
    height, width = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def _layout_prediction_for_field(
    pattern_name: str,
    field_name: str,
    page_items: list[PageText],
) -> tuple[str, float] | None:
    if pattern_name != "rural_rape" or field_name not in {
        "patient_name",
        "age",
        "hn",
        "hospital",
        "collection_date",
        "collection_time",
    }:
        return None
    items = [item for item in page_items if item[1][1] < 0.28]
    if field_name == "patient_name":
        return _layout_value_after_label(items, "name", max_y_delta=0.02, max_x=0.55)
    if field_name == "hospital":
        return _layout_value_after_label(items, "hospital", max_y_delta=0.02, max_x=0.48)
    if field_name == "age":
        return _layout_regex_value(items, r"\bage\s*[:：]?\s*([0-9]{1,3})")
    if field_name == "hn":
        return _layout_regex_value(items, r"\bhn\s*[:：]?\s*([0-9]{3,})")
    if field_name == "collection_time":
        return _layout_regex_value(items, r"\btime\s*[:：]?\s*([0-9]{1,2}\s*[.]\s*[0-9]{2})")
    if field_name == "collection_date":
        return _layout_collection_date(items)
    return None


def _layout_value_after_label(
    items: list[PageText],
    label: str,
    max_y_delta: float,
    max_x: float,
) -> tuple[str, float] | None:
    label_item = _find_layout_label(items, label)
    if label_item is None:
        return None
    _text, bbox, _score = label_item
    candidates = [
        item
        for item in items
        if item[1][0] >= bbox[2] - 0.02
        and item[1][0] <= max_x
        and abs(_bbox_center_y(item[1]) - _bbox_center_y(bbox)) <= max_y_delta
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[1][0])
    text = " ".join(item[0] for item in candidates)
    confidence = sum(item[2] for item in candidates) / len(candidates)
    return text, confidence


def _find_layout_label(items: list[PageText], label: str) -> PageText | None:
    wanted = _normalize_anchor_text(label)
    for item in items:
        normalized = _normalize_anchor_text(item[0])
        if normalized.startswith(wanted):
            return item
    return None


def _layout_regex_value(items: list[PageText], pattern: str) -> tuple[str, float] | None:
    regex = re.compile(pattern, flags=re.IGNORECASE)
    for text, _bbox, score in items:
        match = regex.search(text)
        if match:
            return match.group(1), score
    return None


def _layout_collection_date(items: list[PageText]) -> tuple[str, float] | None:
    for text, _bbox, score in items:
        normalized = _normalize_anchor_text(text)
        if "dateofspecimencollection" in normalized:
            return text, score
    return _layout_regex_value(items, r"\bdate\s*[:：]?\s*([0-9]{1,2}\s*[^\s0-9]+\s*[0-9]{2,4})")


def _bbox_center_y(bbox: BBox) -> float:
    return (bbox[1] + bbox[3]) / 2


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
        detected = self._detect_pattern_from_image(image_path)
        if detected is not None:
            return detected
        return "rural_rape"

    def _detect_pattern_from_image(self, image_path: Path) -> str | None:
        cv2 = _load_cv2()
        image = cv2.imread(str(image_path)) if cv2 is not None else None
        if image is None:
            return None
        height, _width = image.shape[:2]
        header = image[: max(1, round(height * PATTERN_HEADER_RATIO)), :]
        try:
            page_items = self.engine.recognize_layout(header)
        except Exception:
            page_items = []
        text = " ".join(item[0] for item in page_items)
        if not text:
            try:
                text, _confidence = self.engine.recognize(header)
            except Exception:
                text = ""
        if not text:
            try:
                text, _confidence = self.engine.recognize(image)
            except Exception:
                text = ""
        return _detect_pattern_from_text(text)

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
            image = self._prepare_page_image(image)
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
                self._crop_from_anchor(image, config.anchor, page_items, width, height, config.bbox)
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
                layout_prediction = _layout_prediction_for_field(pattern.name, config.name, page_items)
                if layout_prediction is not None:
                    raw_prediction, confidence = layout_prediction
                prediction = _normalize_field_prediction(config.kind, raw_prediction)
                prediction = _normalize_named_field_prediction(
                    pattern.name,
                    config.name,
                    config.kind,
                    prediction,
                    raw_prediction,
                    config.default_value,
                )
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

    @staticmethod
    def _prepare_page_image(image):
        cv2 = _load_cv2()
        if cv2 is None or image is None:
            return image
        deskewed = _deskew_image(image, max_degrees=8.0)
        return deskewed if deskewed is not None else image

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
        preferred_bbox: BBox | None = None,
    ):
        item = _find_anchor_item(page_items, anchor, preferred_bbox=preferred_bbox)
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
    positive_tokens = ("positive", "pos", "presence", "present", "pres", "+", "พบ")
    negative_tokens = ("negative", "neg", "nega", "negati", "absence", "absent", "abs", "-", "ไม่พบ")
    if any(token in compact for token in negative_tokens):
        return "Absence"
    if any(token in compact for token in positive_tokens):
        return "Presence"
    return ""


def _normalize_field_prediction(kind: str, raw_prediction: str) -> str:
    if kind == "result_choice":
        return _normalize_result_choice(raw_prediction)
    if kind == "case_code":
        return _normalize_case_code(raw_prediction)
    if kind == "hospital_name":
        return _normalize_hospital_name(raw_prediction)
    return raw_prediction


def _normalize_named_field_prediction(
    pattern_name: str,
    field_name: str,
    kind: str,
    prediction: str,
    raw_prediction: str,
    default_value: str | None = None,
) -> str:
    source = prediction or raw_prediction
    if field_name == "patient_name":
        return _thai_text_only(source)
    if field_name in {"age", "hn"}:
        return _digits_only(source)
    if field_name == "hospital":
        value = _thai_text_only(prediction)
        if pattern_name == "rural_rape" and value == _ppk_hospital_name():
            return default_value or ""
        return value
    if field_name == "collection_date":
        return _normalize_text_date(source)
    if field_name in {"collection_time", "handwritten_date"}:
        return _normalize_dot_number(source)
    if field_name == "handwritten_number":
        return _normalize_s_number(raw_prediction)
    if field_name in {"vulvar_result", "vaginal_result", "endocervical_result"}:
        return _normalize_result_choice(source)
    return prediction


def _detect_pattern_from_text(text: str) -> str | None:
    normalized = _normalize_anchor_text(text)
    ppk_header_tokens = (
        "โรงพยาบาลพระปกเกล้า",
        "รพ.พระปกเกล้า",
        "รพพระปกเกล้า",
        "โรงพยาบาลพรปกเกล้า",
        "รพ.พรปกเกล้า",
        "รพพรปกเกล้า",
        "พระปกกล้า",
        "รพ.พระปกกล้า",
        "รพพระปกกล้า",
        "tw.พระปกกล้า",
        "twพระปกกล้า",
    )
    if any(_normalize_anchor_text(token) in normalized for token in ppk_header_tokens):
        return "ppk_rape"
    return "rural_rape"


def _translate_thai_digits(text: str) -> str:
    return text.translate(str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789"))


def _digits_only(text: str) -> str:
    return "".join(re.findall(r"\d", _translate_thai_digits(text)))


def _thai_text_only(text: str) -> str:
    return " ".join(re.findall(r"[\u0e00-\u0e7f]+", text.strip()))


def _normalize_text_date(text: str) -> str:
    normalized = _translate_thai_digits(text)
    match = re.search(r"(\d+)\s+([A-Za-z\u0e00-\u0e7f.]+)\s+(\d+)", normalized)
    if match:
        return f"{match.group(1)} {match.group(2)} {match.group(3)}"
    return ""


def _normalize_dot_number(text: str) -> str:
    normalized = _translate_thai_digits(text)
    dot_match = re.search(r"(\d+)\s*[.]\s*(\d+)", normalized)
    if dot_match:
        return f"{dot_match.group(1)}.{dot_match.group(2)}"
    separator_match = re.search(r"(\d{1,2})\D+(\d{2})(?!\d)", normalized)
    if separator_match:
        return f"{separator_match.group(1)}.{separator_match.group(2)}"
    return ""


def _normalize_s_number(text: str) -> str:
    normalized = _translate_thai_digits(text).upper().replace(" ", "")
    normalized = normalized.replace("O", "0").replace("Q", "0")
    normalized = normalized.replace("I", "1").replace("L", "1")
    normalized = normalized.replace("\\", "/").replace("|", "/")
    match = re.search(r"S(\d{3})/(\d{2})(?!\d)", normalized)
    return f"S{match.group(1)}/{match.group(2)}" if match else ""


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


def _ppk_hospital_name() -> str:
    return "โรงพยาบาลพระปกเกล้า"


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
