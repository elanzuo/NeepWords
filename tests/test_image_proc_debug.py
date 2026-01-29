from PIL import Image

from word_extractor.image_proc import save_debug_images


def test_save_debug_images_writes_files(tmp_path):
    original = Image.new("RGB", (10, 10), "white")
    cropped = Image.new("RGB", (10, 8), "white")
    left = Image.new("RGB", (5, 8), "white")
    right = Image.new("RGB", (5, 8), "white")

    save_debug_images(tmp_path, 1, original, cropped, left, right)

    assert (tmp_path / "page_001_original.png").exists()
    assert (tmp_path / "page_001_cropped.png").exists()
    assert (tmp_path / "page_001_split_L.png").exists()
    assert (tmp_path / "page_001_split_R.png").exists()
