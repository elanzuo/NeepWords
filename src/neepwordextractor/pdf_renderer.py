"""PDF rendering helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import pypdfium2 as pdfium
from PIL import Image


def render_pdf_pages(
    pdf_path: Path, start_page: int, end_page: int, dpi: int = 300
) -> List[Image.Image]:
    """Render a 1-based inclusive page range to PIL images."""
    if start_page < 1 or end_page < 1:
        raise ValueError("Page numbers must be 1-based positive integers.")
    if end_page < start_page:
        raise ValueError("end_page must be greater than or equal to start_page.")

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        page_indices = range(start_page - 1, end_page)
        images: List[Image.Image] = []
        for index in page_indices:
            if index < 0 or index >= len(pdf):
                raise ValueError(f"Page index out of range: {index + 1}")
            page = pdf[index]
            try:
                # scale can be float in pypdfium2, suppressing strict int check
                pil_image = page.render(scale=dpi / 72).to_pil()  # type: ignore[arg-type]
            finally:
                page.close()
            images.append(pil_image)
        return images
    finally:
        pdf.close()


def iter_pdf_pages(
    pdf_path: Path, start_page: int, end_page: int, dpi: int = 300
) -> Iterable[Image.Image]:
    """Yield PIL images for a 1-based inclusive page range."""
    for image in render_pdf_pages(pdf_path, start_page, end_page, dpi=dpi):
        yield image
