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
