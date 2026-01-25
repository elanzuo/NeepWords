from pathlib import Path

from PIL import Image

from neepwordextractor import core
from neepwordextractor.ocr_engine import OCRAnnotation


def test_extract_words_wires_pipeline(tmp_path, monkeypatch):
    images = [Image.new("RGB", (100, 100), "white")]

    def fake_iter_pdf_pages(pdf_path, start_page, end_page, dpi=300):
        return iter(images)

    def fake_run_ocr(image, **kwargs):
        return [OCRAnnotation("alpha", 0.9, None), OCRAnnotation("beta", 0.8, None)]

    saved = {"called": False}

    def fake_save_debug_images(debug_dir, page_number, original, cropped, left, right):
        saved["called"] = True

    captured = {}

    def fake_write_outputs(words, output_dir):
        captured["words"] = words
        return {"total_count": len(words)}

    monkeypatch.setattr(core, "iter_pdf_pages", fake_iter_pdf_pages)
    monkeypatch.setattr(core, "run_ocr", fake_run_ocr)
    monkeypatch.setattr(core, "save_debug_images", fake_save_debug_images)
    monkeypatch.setattr(core, "write_outputs", fake_write_outputs)

    stats = core.extract_words(
        pdf_path=Path("dummy.pdf"),
        start_page=1,
        end_page=1,
        output_dir=tmp_path,
        debug_dir=tmp_path / "debug",
        crop_ratio_top=0.0,
        crop_ratio_bottom=0.0,
        split_offset=0.0,
    )

    assert stats == {"total_count": 4}
    assert saved["called"] is True
    assert captured["words"] == [
        {
            "word": "alpha",
            "source": "dummy-1-L-1-alpha",
            "page": 1,
            "column": "L",
            "line": 1,
        },
        {
            "word": "beta",
            "source": "dummy-1-L-2-beta",
            "page": 1,
            "column": "L",
            "line": 2,
        },
        {
            "word": "alpha",
            "source": "dummy-1-R-1-alpha",
            "page": 1,
            "column": "R",
            "line": 1,
        },
        {
            "word": "beta",
            "source": "dummy-1-R-2-beta",
            "page": 1,
            "column": "R",
            "line": 2,
        },
    ]
