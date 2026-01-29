import pytest
from PIL import Image

from word_extractor.image_proc import preprocess_page


def test_preprocess_page_crops_and_splits():
    image = Image.new("RGB", (1000, 2000), "white")
    left, right = preprocess_page(
        image, crop_ratio_top=0.1, crop_ratio_bottom=0.1, split_offset=0.0
    )
    assert left.size == (500, 1600)
    assert right.size == (500, 1600)


def test_preprocess_page_split_offset_adjusts_widths():
    image = Image.new("RGB", (1000, 2000), "white")
    left, right = preprocess_page(
        image, crop_ratio_top=0.0, crop_ratio_bottom=0.0, split_offset=0.02
    )
    assert left.size == (520, 2000)
    assert right.size == (480, 2000)


def test_preprocess_page_rejects_invalid_ratios():
    image = Image.new("RGB", (100, 100), "white")
    with pytest.raises(ValueError, match="Combined crop ratios"):
        preprocess_page(image, crop_ratio_top=0.6, crop_ratio_bottom=0.5)


def test_preprocess_page_binarize():
    image = Image.new("L", (2, 1))
    image.putdata([0, 200])
    left, right = preprocess_page(
        image,
        crop_ratio_top=0.0,
        crop_ratio_bottom=0.0,
        split_offset=0.0,
        binarize=True,
        binarize_threshold=128,
    )
    assert left.mode == "L"
    assert right.mode == "L"
    assert left.getpixel((0, 0)) == 0
    assert right.getpixel((0, 0)) == 255
