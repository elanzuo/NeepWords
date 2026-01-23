"""OCR helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from PIL import Image


@dataclass(frozen=True)
class OCRAnnotation:
    """Single OCR result with optional confidence and bounding box."""

    text: str
    confidence: float | None
    bbox: Sequence[float] | None


def _load_ocrmac():
    try:
        from ocrmac import ocrmac as ocrmac_module
    except ImportError as exc:
        raise RuntimeError(
            "ocrmac is not installed. Install with `uv add ocrmac` or `pip install ocrmac`."
        ) from exc
    return ocrmac_module


def _normalize_annotations(raw_annotations: Iterable[Sequence]) -> list[OCRAnnotation]:
    annotations: list[OCRAnnotation] = []
    for item in raw_annotations:
        if len(item) == 3:
            text, confidence, bbox = item
            annotations.append(OCRAnnotation(str(text), float(confidence), bbox))
        elif len(item) == 2:
            text, bbox = item
            annotations.append(OCRAnnotation(str(text), None, bbox))
        else:
            annotations.append(OCRAnnotation(str(item[0]) if item else "", None, None))
    return annotations


def run_ocr(
    image: Image.Image,
    *,
    recognition_level: str = "accurate",
    language_preference: Sequence[str] | None = None,
    framework: str = "vision",
    unit: str | None = None,
) -> list[OCRAnnotation]:
    """Run OCR on a PIL image and return normalized annotations."""
    ocrmac_module = _load_ocrmac()
    ocr_kwargs: dict[str, Any] = {"framework": framework}
    if language_preference is not None:
        ocr_kwargs["language_preference"] = list(language_preference)
    if framework != "livetext":
        ocr_kwargs["recognition_level"] = recognition_level

    ocr_instance = ocrmac_module.OCR(image, **ocr_kwargs)
    if unit is None:
        raw_annotations = ocr_instance.recognize()
    else:
        try:
            raw_annotations = ocr_instance.recognize(unit=unit)  # type: ignore[call-arg]
        except TypeError:
            raw_annotations = ocr_instance.recognize()
    return _normalize_annotations(raw_annotations)
