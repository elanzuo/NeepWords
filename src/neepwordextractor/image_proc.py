"""Image preprocessing helpers."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageEnhance


def _validate_crop_ratios(crop_ratio_top: float, crop_ratio_bottom: float) -> None:
    if crop_ratio_top < 0 or crop_ratio_bottom < 0:
        raise ValueError("Crop ratios must be non-negative.")
    if crop_ratio_top >= 1 or crop_ratio_bottom >= 1:
        raise ValueError("Crop ratios must be less than 1.")
    if crop_ratio_top + crop_ratio_bottom >= 1:
        raise ValueError("Combined crop ratios must be less than 1.")


def crop_image(
    image: Image.Image, crop_ratio_top: float = 0.07, crop_ratio_bottom: float = 0.06
) -> Image.Image:
    """Crop header/footer regions from a page image."""
    _validate_crop_ratios(crop_ratio_top, crop_ratio_bottom)
    width, height = image.size
    top_px = int(round(height * crop_ratio_top))
    bottom_px = int(round(height * crop_ratio_bottom))
    if top_px + bottom_px >= height:
        raise ValueError("Crop ratios remove the entire image height.")
    return image.crop((0, top_px, width, height - bottom_px))


def split_columns(image: Image.Image, split_offset: float = 0.0) -> tuple[Image.Image, Image.Image]:
    """Split a page image into left/right columns."""
    width, height = image.size
    mid = int(round((width / 2) + (width * split_offset)))
    if mid <= 0 or mid >= width:
        raise ValueError("split_offset results in an invalid split position.")
    left = image.crop((0, 0, mid, height))
    right = image.crop((mid, 0, width, height))
    return left, right


def _apply_contrast(image: Image.Image, contrast_factor: float) -> Image.Image:
    enhancer = ImageEnhance.Contrast(image)
    return enhancer.enhance(contrast_factor)


def _apply_binarize(image: Image.Image, threshold: int) -> Image.Image:
    if threshold < 0 or threshold > 255:
        raise ValueError("binarize_threshold must be between 0 and 255.")
    grayscale = image.convert("L")
    # Use a lookup table instead of a lambda for better performance and type safety
    lut = [255 if i > threshold else 0 for i in range(256)]
    return grayscale.point(lut)


def apply_enhancements(
    image: Image.Image,
    *,
    contrast_factor: float | None = None,
    binarize: bool = False,
    binarize_threshold: int = 128,
) -> Image.Image:
    """Apply optional contrast adjustment and binarization."""
    enhanced = image
    if contrast_factor is not None and contrast_factor != 1.0:
        enhanced = _apply_contrast(enhanced, contrast_factor)
    if binarize:
        enhanced = _apply_binarize(enhanced, binarize_threshold)
    return enhanced


def preprocess_page(
    image: Image.Image,
    crop_ratio_top: float = 0.07,
    crop_ratio_bottom: float = 0.06,
    split_offset: float = 0.0,
    contrast_factor: float | None = None,
    binarize: bool = False,
    binarize_threshold: int = 128,
) -> tuple[Image.Image, Image.Image]:
    """Crop headers/footers, optionally enhance, and split into columns."""
    cropped = crop_image(image, crop_ratio_top=crop_ratio_top, crop_ratio_bottom=crop_ratio_bottom)
    enhanced = apply_enhancements(
        cropped,
        contrast_factor=contrast_factor,
        binarize=binarize,
        binarize_threshold=binarize_threshold,
    )
    return split_columns(enhanced, split_offset=split_offset)


def save_debug_images(
    debug_dir: Path,
    page_number: int,
    original: Image.Image,
    cropped: Image.Image,
    left: Image.Image,
    right: Image.Image,
) -> None:
    """Save intermediate images for visual inspection."""
    output_dir = Path(debug_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    prefix = f"page_{page_number:03d}"
    original.save(output_dir / f"{prefix}_original.png")
    cropped.save(output_dir / f"{prefix}_cropped.png")
    left.save(output_dir / f"{prefix}_split_L.png")
    right.save(output_dir / f"{prefix}_split_R.png")
