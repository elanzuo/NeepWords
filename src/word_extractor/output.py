"""Output writers and statistics."""

from __future__ import annotations

import csv
import importlib
import re
import sqlite3
import warnings
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence, cast

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


def _is_word_spelled_correctly(word: str, *, languages: Sequence[str]) -> bool:
    cocoa = _ensure_spellchecker_available()
    checker = cocoa.NSSpellChecker.sharedSpellChecker()
    available = set(checker.availableLanguages())
    for language in languages:
        if language not in available:
            continue
        checker.setLanguage_(language)
        range_result = checker.checkSpellingOfString_startingAt_(word, 0)
        if range_result[0] == cocoa.NSNotFound:
            return True
    return False


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


def _canonicalize_word(word: str) -> str:
    normalized = re.sub(r"\s+", " ", word.strip())
    return normalized.lower()


def _compute_stats(words: list[dict[str, object]]) -> dict[str, object]:
    word_values = [_canonicalize_word(str(item.get("word", ""))) for item in words]
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


def _write_words_db(
    db_path: Path,
    rows: Sequence[tuple[str, str | None]],
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        _ensure_words_table_schema(conn)
        conn.executemany(
            """
            INSERT INTO words (word, source)
            VALUES (?, ?)
            ON CONFLICT(word) DO UPDATE SET
                source=COALESCE(words.source, excluded.source)
            """,
            rows,
        )


def _ensure_words_table_schema(conn: sqlite3.Connection) -> None:
    columns = conn.execute("PRAGMA table_info(words)").fetchall()
    if not columns:
        conn.execute(
            """
            CREATE TABLE words (
                id INTEGER PRIMARY KEY,
                word TEXT NOT NULL UNIQUE,
                source TEXT,
                added_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            )
            """
        )
        return

    column_names = [row[1] for row in columns]
    if column_names == ["id", "word", "source", "added_at"]:
        return

    conn.execute(
        """
        CREATE TABLE words_migrated (
            id INTEGER PRIMARY KEY,
            word TEXT NOT NULL UNIQUE,
            source TEXT,
            added_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
        """
    )
    conn.execute(
        """
        INSERT INTO words_migrated (id, word, source, added_at)
        SELECT id, lower(trim(word)), source, COALESCE(created_at, strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        FROM words
        ORDER BY id
        """
    )
    conn.execute("DROP TABLE words")
    conn.execute("ALTER TABLE words_migrated RENAME TO words")


def add_words_to_db(
    words: Iterable[str | Mapping[str, object]],
    *,
    db_path: Path,
    source: str | None = None,
) -> dict[str, object]:
    """Insert words into the sqlite database and return stats."""
    normalized = _normalize_words(words)
    accepted: list[dict[str, object]] = []
    rows: list[tuple[str, str | None]] = []
    for item in normalized:
        word = _canonicalize_word(str(item.get("word", "")))
        if not word:
            continue
        source_value = item.get("source")
        if source_value is None or not str(source_value).strip():
            source_value = source
        source_text = str(source_value).strip() if source_value is not None else None
        rows.append((word, source_text))
        accepted.append({"word": word, "source": source_text})

    if rows:
        _write_words_db(db_path, rows)

    return _compute_stats(accepted)


def write_outputs(
    words: Iterable[str | Mapping[str, object]],
    output_dir: Path,
    *,
    spellcheck: bool = True,
    spellcheck_rejected: str = "csv",
    spellcheck_languages: Sequence[str] | None = None,
) -> dict[str, object]:
    """Write words to a sqlite database and return stats."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    normalized = _normalize_words(words)
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []

    languages = [lang for lang in (spellcheck_languages or ("en",)) if lang]
    available_languages: set[str] = set()
    if spellcheck:
        _ensure_spellchecker_available()
        cocoa = _ensure_spellchecker_available()
        checker = cocoa.NSSpellChecker.sharedSpellChecker()
        available_languages = set(checker.availableLanguages())
        missing = [lang for lang in languages if lang not in available_languages]
        if missing:
            warnings.warn(
                "Spellcheck language(s) unavailable: "
                f"{', '.join(missing)}. Available: {', '.join(sorted(available_languages))}",
                RuntimeWarning,
            )
        for item in normalized:
            word = str(item.get("word", "")).strip()
            if not word:
                continue
            if _is_word_spelled_correctly(word, languages=languages):
                accepted.append(item)
            else:
                rejected.append(item)
        if spellcheck_rejected == "db":
            accepted = [item for item in normalized if str(item.get("word", "")).strip()]
    else:
        accepted = [item for item in normalized if str(item.get("word", "")).strip()]

    words_db = output_path / "words.sqlite3"
    rows: list[tuple[str, str | None]] = []
    for item in accepted:
        word = _canonicalize_word(str(item.get("word", "")))
        if not word:
            continue
        source_value = item.get("source")
        source = str(source_value).strip() if source_value is not None else None
        rows.append((word, source))

    if rows:
        _write_words_db(words_db, rows)

    rejected_csv = None
    if spellcheck and spellcheck_rejected == "csv":
        rejected_csv = output_path / "rejected_words.csv"
        with rejected_csv.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["word", "reason", "source"],
            )
            writer.writeheader()
            for item in rejected:
                writer.writerow(
                    {
                        "word": str(item.get("word", "")).strip(),
                        "reason": "misspelled",
                        "source": item.get("source"),
                    }
                )

    stats = _compute_stats(accepted)
    stats["rejected_count"] = len(rejected)
    if rejected_csv is not None:
        stats["rejected_csv"] = str(rejected_csv)
    return stats


def export_words_to_csv(
    db_path: Path,
    csv_path: Path,
    columns: Sequence[str],
) -> dict[str, object]:
    """Export the words table to a CSV file."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    column_list = [column.strip() for column in columns if column and column.strip()]
    if not column_list:
        raise ValueError("At least one column must be provided.")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        column_rows = conn.execute("PRAGMA table_info(words)").fetchall()
        available_columns = {row["name"] for row in column_rows}
        if not available_columns:
            raise ValueError("words table not found in database.")
        missing = [column for column in column_list if column not in available_columns]
        if missing:
            available = ", ".join(sorted(available_columns))
            raise ValueError(f"Unknown columns: {', '.join(missing)}. Available: {available}")

        select_columns = ", ".join(f'"{column}"' for column in column_list)
        cursor = conn.execute(f"SELECT {select_columns} FROM words ORDER BY id")

        csv_path.parent.mkdir(parents=True, exist_ok=True)
        row_count = 0
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(column_list)
            for row in cursor:
                writer.writerow([row[column] for column in column_list])
                row_count += 1

    return {"row_count": row_count, "csv_path": str(csv_path)}
