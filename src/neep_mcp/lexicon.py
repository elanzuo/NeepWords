"""Shared local word-lookup helpers for the NEEP vocabulary database."""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

DEFAULT_DB_PATH = Path("resources") / "data" / "words.sqlite3"
MAX_WORD_LENGTH = 64
MAX_LOOKUP = 200
MAX_SEARCH = 200
MAX_RANDOM = 50

_WORD_RE = re.compile(r"[A-Za-z-]+")


@dataclass
class WordsQueryResult:
    word: str
    norm: str
    source: str | None
    ipa: str | None
    frequency: int | None
    created_at: str | None
    updated_at: str | None


class WordsDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        if not self.path.exists():
            raise FileNotFoundError(f"Database not found: {self.path}")
        uri = f"file:{self.path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch_all(self, sql: str, params: Sequence[Any]) -> list[sqlite3.Row]:
        with self.connect() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchall()


def resolve_db_path() -> Path:
    env_value = (
        os.environ.get("NEEP_WORDS_DB_PATH")
        or os.environ.get("NEEP_WORDS_DB")
        or str(DEFAULT_DB_PATH)
    )
    return Path(env_value)


def sanitize_token(value: str) -> tuple[str | None, list[str]]:
    warnings: list[str] = []
    if not value:
        return None, ["empty_input"]
    raw = value.strip()
    if not raw:
        return None, ["empty_input"]
    tokens = _WORD_RE.findall(raw)
    if not tokens:
        return None, ["no_english_tokens"]
    if len(tokens) > 1:
        warnings.append("multiple_tokens_found_using_longest")
    token = max(tokens, key=len)
    cleaned = re.sub(r"[^A-Za-z-]+", "", token).lower()
    if not cleaned:
        return None, ["no_english_tokens"]
    if len(cleaned) > MAX_WORD_LENGTH:
        return None, ["too_long"]
    if cleaned != raw.lower():
        warnings.append("normalized_input")
    return cleaned, warnings


def sanitize_wildcard(value: str) -> tuple[str | None, list[str]]:
    warnings: list[str] = []
    if value is None:
        return None, ["empty_input"]
    raw = str(value).strip()
    if not raw:
        return None, ["empty_input"]

    cleaned_chars: list[str] = []
    has_letter = False
    for ch in raw:
        if "A" <= ch <= "Z":
            cleaned_chars.append(ch.lower())
            has_letter = True
            if ch != ch.lower():
                warnings.append("normalized_input")
        elif "a" <= ch <= "z":
            cleaned_chars.append(ch)
            has_letter = True
        elif ch in {"-", "%", "_"}:
            cleaned_chars.append(ch)
        else:
            return None, ["invalid_characters"]

    cleaned = "".join(cleaned_chars)
    if not cleaned:
        return None, ["empty_input"]
    if not has_letter:
        return None, ["no_english_tokens"]
    if len(cleaned) > MAX_WORD_LENGTH:
        return None, ["too_long"]
    return cleaned, warnings


def _row_to_result(row: sqlite3.Row) -> WordsQueryResult:
    return WordsQueryResult(
        word=row["word"],
        norm=row["norm"],
        source=row["source"],
        ipa=row["ipa"],
        frequency=row["frequency"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class WordsLexicon:
    def __init__(self, path: Path) -> None:
        self._db = WordsDatabase(path)
        self.path = path

    def lookup_words(
        self, words: Iterable[str], match: str | None = "auto"
    ) -> tuple[dict[str, Any], list[str]]:
        if words is None:
            raise ValueError("missing_words")

        items = list(words)
        if not items:
            raise ValueError("missing_words")
        if len(items) > MAX_LOOKUP:
            raise ValueError("too_many_words")

        match_value = (match or "auto").lower()
        if match_value not in {"auto", "word", "norm"}:
            raise ValueError("invalid_match")

        results: list[dict[str, Any]] = []
        warnings: list[str] = []

        with self._db.connect() as conn:
            for item in items:
                original = str(item)
                cleaned, clean_warnings = sanitize_token(original)
                warnings.extend(clean_warnings)
                if cleaned is None:
                    results.append({"input": original, "found": False, "error": "invalid_input"})
                    continue

                if match_value == "word":
                    row = conn.execute(
                        "SELECT * FROM words WHERE lower(word) = ?", (cleaned,)
                    ).fetchone()
                elif match_value == "norm":
                    row = conn.execute("SELECT * FROM words WHERE norm = ?", (cleaned,)).fetchone()
                else:
                    row = conn.execute(
                        "SELECT * FROM words WHERE lower(word) = ?", (cleaned,)
                    ).fetchone()
                    if row is None:
                        row = conn.execute("SELECT * FROM words WHERE norm = ?", (cleaned,)).fetchone()

                if row is None:
                    results.append({"input": original, "query": cleaned, "found": False})
                    continue

                payload = _row_to_result(row)
                results.append(
                    {
                        "input": original,
                        "query": cleaned,
                        "found": True,
                        "word": payload.word,
                        "norm": payload.norm,
                        "source": payload.source,
                        "ipa": payload.ipa,
                        "frequency": payload.frequency,
                        "created_at": payload.created_at,
                        "updated_at": payload.updated_at,
                    }
                )

        return {"results": results}, warnings

    def search_words(
        self, query: str, mode: str | None = "contains", limit: int | None = 10, offset: int | None = 0
    ) -> tuple[dict[str, Any], list[str]]:
        if query is None:
            raise ValueError("missing_query")

        mode_value = (mode or "contains").lower()
        if mode_value not in {"prefix", "suffix", "contains", "fuzzy", "wildcard"}:
            raise ValueError("invalid_mode")

        if mode_value == "wildcard":
            cleaned, warnings = sanitize_wildcard(str(query))
        else:
            cleaned, warnings = sanitize_token(str(query))
        if cleaned is None:
            raise ValueError("invalid_query")

        try:
            limit_value = int(limit or 10)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_limit") from exc

        try:
            offset_value = int(offset or 0)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_offset") from exc

        limit_value = max(1, min(limit_value, MAX_SEARCH))
        offset_value = max(0, offset_value)

        if mode_value == "prefix":
            pattern = f"{cleaned}%"
        elif mode_value == "suffix":
            pattern = f"%{cleaned}"
        elif mode_value == "contains":
            pattern = f"%{cleaned}%"
        elif mode_value == "wildcard":
            pattern = cleaned
        else:
            pattern = "%" + "%".join(cleaned) + "%"

        rows = self._db.fetch_all(
            "SELECT * FROM words WHERE norm LIKE ? ORDER BY norm LIMIT ? OFFSET ?",
            (pattern, limit_value, offset_value),
        )

        results = [{"word": row["word"]} for row in rows]
        return {
            "query": cleaned,
            "mode": mode_value,
            "limit": limit_value,
            "offset": offset_value,
            "results": results,
        }, warnings

    def get_random_words(
        self, count: int | None = 5, min_frequency: int | None = None
    ) -> dict[str, Any]:
        try:
            count_value = int(count or 5)
        except (TypeError, ValueError) as exc:
            raise ValueError("invalid_count") from exc

        count_value = max(1, min(count_value, MAX_RANDOM))

        freq_value: int | None
        if min_frequency is None:
            freq_value = None
        else:
            try:
                freq_value = max(1, int(min_frequency))
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid_min_frequency") from exc

        sql = "SELECT * FROM words"
        params: list[Any] = []
        if freq_value is not None:
            sql += " WHERE frequency >= ?"
            params.append(freq_value)
        sql += " ORDER BY RANDOM() LIMIT ?"
        params.append(count_value)

        rows = self._db.fetch_all(sql, params)
        results = [
            {
                "word": row["word"],
                "norm": row["norm"],
                "source": row["source"],
                "ipa": row["ipa"],
                "frequency": row["frequency"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]
        return {"count": count_value, "min_frequency": freq_value, "results": results}

    def stats_summary(self) -> dict[str, Any]:
        with self._db.connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS count FROM words").fetchone()
            last_updated = conn.execute("SELECT MAX(updated_at) AS updated_at FROM words").fetchone()

        stats = {
            "total_words": total["count"] if total else 0,
            "last_updated": last_updated["updated_at"] if last_updated else None,
        }

        rejected_csv = self.path.with_name("rejected_words.csv")
        if rejected_csv.exists():
            stats["rejected_csv"] = str(rejected_csv)
            try:
                with rejected_csv.open("r", encoding="utf-8") as handle:
                    rejected_count = sum(1 for _ in handle) - 1
                stats["rejected_count"] = max(0, rejected_count)
            except OSError:
                stats["rejected_count"] = None

        return stats

    def schema(self) -> list[dict[str, Any]]:
        with self._db.connect() as conn:
            rows = conn.execute("PRAGMA table_info(words)").fetchall()

        return [
            {
                "name": row["name"],
                "type": row["type"],
                "notnull": row["notnull"],
                "default": row["dflt_value"],
                "pk": row["pk"],
            }
            for row in rows
        ]
