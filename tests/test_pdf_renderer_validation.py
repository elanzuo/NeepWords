from pathlib import Path

import pytest

from word_extractor.pdf_renderer import render_pdf_pages


def test_render_pdf_pages_rejects_non_positive_pages():
    with pytest.raises(ValueError, match="1-based"):
        render_pdf_pages(Path("/tmp/does_not_exist.pdf"), 0, 1)

    with pytest.raises(ValueError, match="1-based"):
        render_pdf_pages(Path("/tmp/does_not_exist.pdf"), 1, 0)


def test_render_pdf_pages_rejects_end_before_start():
    with pytest.raises(ValueError, match="end_page"):
        render_pdf_pages(Path("/tmp/does_not_exist.pdf"), 3, 2)
