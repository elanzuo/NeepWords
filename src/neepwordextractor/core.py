"""Pipeline orchestration."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from .cleaner import expand_variants, normalize_text
from .image_proc import apply_enhancements, crop_image, save_debug_images, split_columns
from .ocr_engine import OCRAnnotation, run_ocr
from .output import write_outputs
from .pdf_renderer import iter_pdf_pages


def _annotations_to_text(annotations: Iterable[OCRAnnotation]) -> str:
    return "\n".join(annotation.text for annotation in annotations if annotation.text)


def extract_words(
    pdf_path: Path,
    start_page: int,
    end_page: int,
    output_dir: Path,
    debug_dir: Path | None = None,
    *,
    dpi: int = 300,
    crop_ratio_top: float = 0.07,
    crop_ratio_bottom: float = 0.06,
    split_offset: float = 0.0,
    contrast_factor: float | None = None,
    binarize: bool = False,
    binarize_threshold: int = 128,
    recognition_level: str = "accurate",
    language_preference: Sequence[str] | None = None,
    framework: str = "vision",
    ocr_unit: str = "line",
    spellcheck: bool = True,
    spellcheck_rejected: str = "csv",
) -> dict[str, object]:
    """Run the end-to-end extraction pipeline and return stats."""
    words: list[dict[str, object]] = []

    page_images = iter_pdf_pages(pdf_path, start_page, end_page, dpi=dpi)
    for page_number, image in enumerate(page_images, start=start_page):
        cropped = crop_image(
            image, crop_ratio_top=crop_ratio_top, crop_ratio_bottom=crop_ratio_bottom
        )
        processed = apply_enhancements(
            cropped,
            contrast_factor=contrast_factor,
            binarize=binarize,
            binarize_threshold=binarize_threshold,
        )
        left_image, right_image = split_columns(processed, split_offset=split_offset)

        if debug_dir is not None:
            save_debug_images(debug_dir, page_number, image, processed, left_image, right_image)

        for column_label, column_image in (("L", left_image), ("R", right_image)):
            annotations = run_ocr(
                column_image,
                recognition_level=recognition_level,
                language_preference=language_preference,
                framework=framework,
                unit=ocr_unit,
            )
            raw_text = _annotations_to_text(annotations)
            cleaned_lines = normalize_text(raw_text)
            for line_index, line in enumerate(cleaned_lines, start=1):
                source = f"{pdf_path.stem}-{page_number}-{column_label}-{line_index}-{line}"
                for word in expand_variants(line):
                    words.append(
                        {
                            "word": word,
                            "source": source,
                            "page": page_number,
                            "column": column_label,
                            "line": line_index,
                        }
                    )

    return write_outputs(
        words,
        output_dir,
        spellcheck=spellcheck,
        spellcheck_rejected=spellcheck_rejected,
    )
