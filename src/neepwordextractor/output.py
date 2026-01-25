"""Output writers and statistics."""

from __future__ import annotations

import re
import sqlite3
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


def _normalize_word_value(word: str) -> str:
    normalized = re.sub(r"\s+", " ", word.strip())
    return normalized.lower()


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
    """Write words to a sqlite database and return stats."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    normalized = _normalize_words(words)
    words_db = output_path / "words.sqlite3"

    with sqlite3.connect(words_db) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY,
                word TEXT NOT NULL,
                norm TEXT NOT NULL UNIQUE,
                source TEXT,
                ipa TEXT,
                frequency INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            )
            """
        )
        rows: list[tuple[str, str, str | None, str | None]] = []
        for item in normalized:
            word = str(item.get("word", "")).strip()
            if not word:
                continue
            norm = _normalize_word_value(word)
            source_value = item.get("source")
            source = str(source_value).strip() if source_value is not None else None
            ipa_value = item.get("ipa")
            ipa = str(ipa_value).strip() if ipa_value is not None else None
            rows.append((word, norm, source, ipa))

        conn.executemany(
            """
            INSERT INTO words (word, norm, source, ipa)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(norm) DO UPDATE SET
                source=excluded.source,
                ipa=excluded.ipa,
                frequency=words.frequency + 1,
                updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now')
            """,
            rows,
        )

    return _compute_stats(normalized)
