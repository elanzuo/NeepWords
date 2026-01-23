"""Output writers and statistics."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping


def _normalize_words(
    words: Iterable[str | Mapping[str, object]],
) -> list[dict[str, object]]:
    normalized: list[dict[str, object]] = []
    for item in words:
        if isinstance(item, str):
            normalized.append({"word": item})
        else:
            normalized.append(dict(item))
    return normalized


def _compute_stats(words: list[dict[str, object]]) -> dict[str, object]:
    word_values = [str(item.get("word", "")).strip() for item in words]
    total_count = len(word_values)
    unique_count = len(set(word_values))
    duplicate_count = total_count - unique_count

    page_counts: dict[int, int] = {}
    pages = [item.get("page") for item in words if item.get("page") is not None]
    if pages:
        counter = Counter(int(str(page)) for page in pages)
        page_counts = dict(sorted(counter.items()))

    return {
        "total_count": total_count,
        "unique_count": unique_count,
        "duplicate_count": duplicate_count,
        "per_page_counts": page_counts,
    }


def write_outputs(
    words: Iterable[str | Mapping[str, object]], output_dir: Path
) -> dict[str, object]:
    """Write words to output files and return stats."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    normalized = _normalize_words(words)
    words_txt = output_path / "words.txt"
    words_json = output_path / "words.json"

    with words_txt.open("w", encoding="utf-8") as handle:
        for item in normalized:
            word = str(item.get("word", "")).strip()
            if word:
                handle.write(f"{word}\n")

    with words_json.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, ensure_ascii=False, indent=2)

    return _compute_stats(normalized)
