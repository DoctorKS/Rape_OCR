from __future__ import annotations

import contextlib
import io
from pathlib import Path

from .domain import FieldResult, OcrJob, PatternConfig


def _load_cv2():
    try:
        with contextlib.redirect_stderr(io.StringIO()):
            import cv2
    except Exception:
        return None
    return cv2


class OcrEngine:
    def recognize(self, image) -> tuple[str, float]:
        raise NotImplementedError


class PlaceholderOcrEngine(OcrEngine):
    def recognize(self, image) -> tuple[str, float]:
        return "", 0.0


class PaddleOcrEngine(OcrEngine):
    def __init__(self, lang: str = "th") -> None:
        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError(
                "PaddleOCR is not installed. Install optional dependencies first."
            ) from exc
        self._ocr = PaddleOCR(use_angle_cls=True, lang=lang)

    def recognize(self, image) -> tuple[str, float]:
        result = self._ocr.ocr(image, cls=True)
        texts: list[str] = []
        scores: list[float] = []
        for page in result or []:
            for line in page or []:
                text, score = line[1]
                texts.append(str(text))
                scores.append(float(score))
        if not texts:
            return "", 0.0
        return " ".join(texts), sum(scores) / len(scores)


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

    def process(self, image_path: Path, pattern_name: str | None = None) -> OcrJob:
        cv2 = _load_cv2()
        image = cv2.imread(str(image_path)) if cv2 is not None else None
        if image is None:
            width, height = 1, 1
        else:
            height, width = image.shape[:2]
        selected_pattern = pattern_name or self.detect_pattern(image_path)
        pattern = self.patterns[selected_pattern]

        fields: list[FieldResult] = []
        for config in pattern.fields:
            crop = self._crop_relative(image, config.bbox, width, height) if image is not None else None
            if config.kind == "checkbox":
                prediction, confidence = self._detect_checkbox(crop)
            else:
                prediction, confidence = self.engine.recognize(crop)
            fields.append(
                FieldResult(
                    name=config.name,
                    label=config.label,
                    prediction=prediction,
                    confidence=confidence,
                    bbox=config.bbox,
                    kind=config.kind,
                    docx_tag=config.docx_tag,
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
