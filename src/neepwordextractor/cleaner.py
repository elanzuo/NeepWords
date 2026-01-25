"""Text cleanup helpers."""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")
_SLASH_RE = re.compile(r"\s*/\s*")
_ALLOWED_RE = re.compile(r"[^a-zA-Z()/\\ -]+")


def _merge_hyphenated_lines(lines: list[str]) -> list[str]:
    merged: list[str] = []
    idx = 0
    while idx < len(lines):
        line = lines[idx]
        if line.endswith("-") and idx + 1 < len(lines):
            next_line = lines[idx + 1].lstrip()
            if next_line and next_line[0].isalpha():
                merged.append(line[:-1] + next_line)
                idx += 2
                continue
        merged.append(line)
        idx += 1
    return merged


def _normalize_line(line: str) -> str:
    line = _ALLOWED_RE.sub(" ", line)
    line = _SLASH_RE.sub(" / ", line)
    line = _WHITESPACE_RE.sub(" ", line)
    return line.strip()


def _is_noise(line: str) -> bool:
    if len(line) < 2:
        return True
    alpha_count = sum(1 for char in line if char.isalpha())
    total_count = len(line)
    if total_count == 0:
        return True
    return (alpha_count / total_count) < 0.5


def normalize_text(text: str) -> list[str]:
    """Normalize raw OCR text into cleaned, non-noise lines."""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lines = _merge_hyphenated_lines(lines)
    cleaned: list[str] = []
    for line in lines:
        normalized = _normalize_line(line)
        if normalized and not _is_noise(normalized):
            cleaned.append(normalized)
    return cleaned


def expand_variants(line: str) -> list[str]:
    """Expand slash and parentheses variants into individual word entries."""
    parts = [part.strip() for part in line.split(" / ") if part.strip()]
    variants: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for expanded in _expand_parentheses(part):
            if expanded and expanded not in seen:
                variants.append(expanded)
                seen.add(expanded)
    if not variants:
        return variants
    variant_set = set(variants)
    return [
        variant
        for variant in variants
        if not (variant.endswith("ou") and f"{variant}r" in variant_set)
    ]


def _expand_parentheses(word: str) -> list[str]:
    start = word.find("(")
    if start == -1:
        return [word]
    end = word.find(")", start + 1)
    if end == -1:
        return [word.replace("(", "").replace(")", "")]
    prefix = word[:start]
    optional = word[start + 1 : end]
    suffix = word[end + 1 :]
    without_optional = f"{prefix}{suffix}"
    if not optional:
        return [without_optional]
    with_optional = f"{prefix}{optional}{suffix}"
    expanded: list[str] = []
    for candidate in (without_optional, with_optional):
        expanded.extend(_expand_parentheses(candidate))
    return expanded
