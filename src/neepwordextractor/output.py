"""Output writers and statistics."""

from __future__ import annotations

import csv
import importlib
import re
import sqlite3
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, cast

try:
    Cocoa: Any | None = importlib.import_module("Cocoa")
except Exception as exc:  # pragma: no cover - platform import guard
    Cocoa = None
    _NSSPELLCHECKER_IMPORT_ERROR = exc
else:
    _NSSPELLCHECKER_IMPORT_ERROR = None


def _ensure_spellchecker_available() -> Any:
    if Cocoa is None:
        raise RuntimeError(
            "NSSpellChecker is unavailable. Install PyObjC (pyobjc-framework-Cocoa) "
            "and run on macOS."
        ) from _NSSPELLCHECKER_IMPORT_ERROR
    return cast(Any, Cocoa)


def _is_word_spelled_correctly(word: str, *, language: str = "en_US") -> bool:
    cocoa = _ensure_spellchecker_available()
    checker = cocoa.NSSpellChecker.sharedSpellChecker()
    range_result = checker.checkSpellingOfString_startingAt_(word, 0)
    return range_result[0] == cocoa.NSNotFound


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
    words: Iterable[str | Mapping[str, object]],
    output_dir: Path,
    *,
    spellcheck: bool = True,
    spellcheck_rejected: str = "csv",
) -> dict[str, object]:
    """Write words to a sqlite database and return stats."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    normalized = _normalize_words(words)
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []

    if spellcheck:
        _ensure_spellchecker_available()
        for item in normalized:
            word = str(item.get("word", "")).strip()
            if not word:
                continue
            if _is_word_spelled_correctly(word):
                accepted.append(item)
            else:
                rejected.append(item)
        if spellcheck_rejected == "db":
            accepted = [item for item in normalized if str(item.get("word", "")).strip()]
    else:
        accepted = [item for item in normalized if str(item.get("word", "")).strip()]

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
        for item in accepted:
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

    rejected_csv = None
    if spellcheck and spellcheck_rejected == "csv":
        rejected_csv = output_path / "rejected_words.csv"
        with rejected_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["word", "reason", "source", "page", "column", "line"],
            )
            writer.writeheader()
            for item in rejected:
                writer.writerow(
                    {
                        "word": str(item.get("word", "")).strip(),
                        "reason": "misspelled",
                        "source": item.get("source"),
                        "page": item.get("page"),
                        "column": item.get("column"),
                        "line": item.get("line"),
                    }
                )

    stats = _compute_stats(accepted)
    stats["rejected_count"] = len(rejected)
    if rejected_csv is not None:
        stats["rejected_csv"] = str(rejected_csv)
    return stats
