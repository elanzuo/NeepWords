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

from .storage import (
    detect_schema_mode,
    ensure_version_row,
    ensure_writable_schema,
    normalize_version_key,
    table_columns,
)

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
    *,
    version: str | int,
    legacy_version: str | int | None = None,
    source_pdf: str | None = None,
) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        ensure_writable_schema(conn, legacy_version=legacy_version)
        version_id = ensure_version_row(
            conn,
            version,
            source_pdf=source_pdf,
        )
        conn.executemany(
            """
            INSERT INTO words (version_id, word, source)
            VALUES (?, ?, ?)
            ON CONFLICT(version_id, word) DO UPDATE SET
                source=COALESCE(words.source, excluded.source)
            """,
            [(version_id, word, source) for word, source in rows],
        )

def add_words_to_db(
    words: Iterable[str | Mapping[str, object]],
    *,
    db_path: Path,
    version: str | int,
    source: str | None = None,
    legacy_version: str | int | None = None,
) -> dict[str, object]:
    """Insert words into the sqlite database and return stats."""
    version_key = normalize_version_key(version)
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
        _write_words_db(
            db_path,
            rows,
            version=version_key,
            legacy_version=legacy_version,
        )

    stats = _compute_stats(accepted)
    stats["version"] = version_key
    return stats


def write_outputs(
    words: Iterable[str | Mapping[str, object]],
    output_dir: Path,
    *,
    version: str | int,
    spellcheck: bool = True,
    spellcheck_rejected: str = "csv",
    spellcheck_languages: Sequence[str] | None = None,
    legacy_version: str | int | None = None,
    source_pdf: str | None = None,
) -> dict[str, object]:
    """Write words to a sqlite database and return stats."""
    version_key = normalize_version_key(version)
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
        _write_words_db(
            words_db,
            rows,
            version=version_key,
            legacy_version=legacy_version,
            source_pdf=source_pdf,
        )

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
    stats["version"] = version_key
    stats["rejected_count"] = len(rejected)
    if rejected_csv is not None:
        stats["rejected_csv"] = str(rejected_csv)
    return stats


def export_words_to_csv(
    db_path: Path,
    csv_path: Path,
    columns: Sequence[str],
    *,
    version: str | int | None = None,
) -> dict[str, object]:
    """Export the words table to a CSV file."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")

    column_list = [column.strip() for column in columns if column and column.strip()]
    if not column_list:
        raise ValueError("At least one column must be provided.")

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        schema_mode = detect_schema_mode(conn)
        if schema_mode == "missing":
            raise ValueError("words table not found in database.")
        if schema_mode == "unknown":
            raise ValueError("Unsupported words schema.")

        if schema_mode == "legacy":
            available_columns = set(table_columns(conn, "words"))
            missing = [column for column in column_list if column not in available_columns]
            if missing:
                available = ", ".join(sorted(available_columns))
                raise ValueError(f"Unknown columns: {', '.join(missing)}. Available: {available}")
            select_columns = ", ".join(f'"{column}"' for column in column_list)
            cursor = conn.execute(f"SELECT {select_columns} FROM words ORDER BY id")
        else:
            available_columns = {"id", "word", "source", "added_at", "version", "label"}
            missing = [column for column in column_list if column not in available_columns]
            if missing:
                available = ", ".join(sorted(available_columns))
                raise ValueError(f"Unknown columns: {', '.join(missing)}. Available: {available}")

            selected: list[str] = []
            for column in column_list:
                if column == "version":
                    selected.append('vv.version_key AS "version"')
                elif column == "label":
                    selected.append('vv.label AS "label"')
                else:
                    selected.append(f'w."{column}"')
            sql = (
                "SELECT "
                + ", ".join(selected)
                + " FROM words AS w JOIN vocab_versions AS vv ON vv.id = w.version_id"
            )
            params: list[object] = []
            if version is not None:
                sql += " WHERE vv.version_key = ?"
                params.append(normalize_version_key(version))
            sql += " ORDER BY vv.version_key, w.id"
            cursor = conn.execute(sql, params)

        csv_path.parent.mkdir(parents=True, exist_ok=True)
        row_count = 0
        with csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(column_list)
            for row in cursor:
                writer.writerow([row[column] for column in column_list])
                row_count += 1

    payload: dict[str, object] = {"row_count": row_count, "csv_path": str(csv_path)}
    if version is not None:
        payload["version"] = normalize_version_key(version)
    return payload
