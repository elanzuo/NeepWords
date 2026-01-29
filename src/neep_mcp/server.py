"""MCP server for querying WordExtractor words database (read-only)."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from mcp.server.fastmcp import FastMCP

DEFAULT_DB_PATH = Path("words") / "words.sqlite3"
MAX_WORD_LENGTH = 64
MAX_LOOKUP = 200
MAX_SEARCH = 200
MAX_RANDOM = 50
DEFAULT_RATE_LIMIT_SECONDS = 0.5

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


class RateLimiter:
    def __init__(self, min_interval: float = DEFAULT_RATE_LIMIT_SECONDS) -> None:
        self._min_interval = min_interval
        self._last_call = 0.0

    def check(self) -> str | None:
        now = time.monotonic()
        if now - self._last_call < self._min_interval:
            return "rate_limited"
        self._last_call = now
        return None


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

    def fetch_one(self, sql: str, params: Sequence[Any]) -> sqlite3.Row | None:
        with self.connect() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchone()

    def fetch_all(self, sql: str, params: Sequence[Any]) -> list[sqlite3.Row]:
        with self.connect() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchall()


mcp = FastMCP("neep-words")
_rate_limiter = RateLimiter()


def _resolve_db_path() -> Path:
    env_value = (
        os.environ.get("NEEP_WORDS_DB_PATH")
        or os.environ.get("NEEP_WORDS_DB")
        or str(DEFAULT_DB_PATH)
    )
    return Path(env_value)


def _make_response(
    ok: bool, data: Any = None, error: str | None = None, warnings: list[str] | None = None
) -> dict[str, Any]:
    return {
        "ok": ok,
        "error": error,
        "data": data,
        "warnings": warnings or [],
    }


def _sanitize_token(value: str) -> tuple[str | None, list[str]]:
    warnings: list[str] = []
    if not value:
        return None, ["empty_input"]
    raw = value.strip()
    if not raw:
        return None, ["empty_input"]
    tokens = _WORD_RE.findall(raw)
    if not tokens:
        return None, ["no_english_tokens"]
    token = max(tokens, key=len)
    cleaned = re.sub(r"[^A-Za-z-]+", "", token).lower()
    if not cleaned:
        return None, ["no_english_tokens"]
    if len(cleaned) > MAX_WORD_LENGTH:
        return None, ["too_long"]
    if cleaned != raw.lower():
        warnings.append("normalized_input")
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


def _db() -> WordsDatabase:
    return WordsDatabase(_resolve_db_path())


@mcp.tool()
def lookup_words(words: Iterable[str], match: str | None = "auto") -> dict[str, Any]:
    rate_error = _rate_limiter.check()
    if rate_error:
        return _make_response(False, error=rate_error)

    if words is None:
        return _make_response(False, error="missing_words")

    items = list(words)
    if not items:
        return _make_response(False, error="missing_words")
    if len(items) > MAX_LOOKUP:
        return _make_response(False, error="too_many_words")

    match_value = (match or "auto").lower()
    if match_value not in {"auto", "word", "norm"}:
        return _make_response(False, error="invalid_match")

    results: list[dict[str, Any]] = []
    warnings: list[str] = []

    try:
        with _db().connect() as conn:
            for item in items:
                original = str(item)
                cleaned, clean_warnings = _sanitize_token(original)
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
                    row = conn.execute("SELECT * FROM words WHERE norm = ?", (cleaned,)).fetchone()
                    if row is None:
                        row = conn.execute(
                            "SELECT * FROM words WHERE lower(word) = ?", (cleaned,)
                        ).fetchone()

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
    except FileNotFoundError:
        return _make_response(False, error="db_not_found")
    except sqlite3.Error:
        return _make_response(False, error="db_error")

    return _make_response(True, data={"results": results}, warnings=warnings)


@mcp.tool()
def search_words(
    query: str,
    mode: str | None = "prefix",
    limit: int | None = 10,
    offset: int | None = 0,
) -> dict[str, Any]:
    rate_error = _rate_limiter.check()
    if rate_error:
        return _make_response(False, error=rate_error)

    if query is None:
        return _make_response(False, error="missing_query")
    cleaned, warnings = _sanitize_token(str(query))
    if cleaned is None:
        return _make_response(False, error="invalid_query", warnings=warnings)

    mode_value = (mode or "prefix").lower()
    if mode_value not in {"prefix", "contains", "fuzzy"}:
        return _make_response(False, error="invalid_mode")

    try:
        limit_value = int(limit or 10)
    except (TypeError, ValueError):
        return _make_response(False, error="invalid_limit")

    try:
        offset_value = int(offset or 0)
    except (TypeError, ValueError):
        return _make_response(False, error="invalid_offset")

    limit_value = max(1, min(limit_value, MAX_SEARCH))
    offset_value = max(0, offset_value)

    if mode_value == "prefix":
        pattern = f"{cleaned}%"
    elif mode_value == "contains":
        pattern = f"%{cleaned}%"
    else:
        pattern = "%" + "%".join(cleaned) + "%"

    try:
        rows = _db().fetch_all(
            "SELECT * FROM words WHERE norm LIKE ? ORDER BY norm LIMIT ? OFFSET ?",
            (pattern, limit_value, offset_value),
        )
    except FileNotFoundError:
        return _make_response(False, error="db_not_found")
    except sqlite3.Error:
        return _make_response(False, error="db_error")

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

    return _make_response(
        True,
        data={
            "query": cleaned,
            "mode": mode_value,
            "limit": limit_value,
            "offset": offset_value,
            "results": results,
        },
        warnings=warnings,
    )


@mcp.tool()
def get_random_words(count: int | None = 5, min_frequency: int | None = None) -> dict[str, Any]:
    rate_error = _rate_limiter.check()
    if rate_error:
        return _make_response(False, error=rate_error)

    try:
        count_value = int(count or 5)
    except (TypeError, ValueError):
        return _make_response(False, error="invalid_count")

    count_value = max(1, min(count_value, MAX_RANDOM))

    freq_value: int | None
    if min_frequency is None:
        freq_value = None
    else:
        try:
            freq_value = max(1, int(min_frequency))
        except (TypeError, ValueError):
            return _make_response(False, error="invalid_min_frequency")

    sql = "SELECT * FROM words"
    params: list[Any] = []
    if freq_value is not None:
        sql += " WHERE frequency >= ?"
        params.append(freq_value)
    sql += " ORDER BY RANDOM() LIMIT ?"
    params.append(count_value)

    try:
        rows = _db().fetch_all(sql, params)
    except FileNotFoundError:
        return _make_response(False, error="db_not_found")
    except sqlite3.Error:
        return _make_response(False, error="db_error")

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

    return _make_response(
        True,
        data={"count": count_value, "min_frequency": freq_value, "results": results},
    )


@mcp.resource("neep://stats/summary")
def stats_summary() -> str:
    try:
        with _db().connect() as conn:
            total = conn.execute("SELECT COUNT(*) AS count FROM words").fetchone()
            last_updated = conn.execute(
                "SELECT MAX(updated_at) AS updated_at FROM words"
            ).fetchone()
    except FileNotFoundError:
        payload = _make_response(False, error="db_not_found")
        return json.dumps(payload, ensure_ascii=False)
    except sqlite3.Error:
        payload = _make_response(False, error="db_error")
        return json.dumps(payload, ensure_ascii=False)

    stats = {
        "total_words": total["count"] if total else 0,
        "last_updated": last_updated["updated_at"] if last_updated else None,
    }

    rejected_csv = _resolve_db_path().with_name("rejected_words.csv")
    if rejected_csv.exists():
        stats["rejected_csv"] = str(rejected_csv)
        try:
            with rejected_csv.open("r", encoding="utf-8") as handle:
                rejected_count = sum(1 for _ in handle) - 1
            stats["rejected_count"] = max(0, rejected_count)
        except OSError:
            stats["rejected_count"] = None

    return json.dumps(_make_response(True, data=stats), ensure_ascii=False)


@mcp.resource("neep://stats/schema")
def stats_schema() -> str:
    try:
        with _db().connect() as conn:
            rows = conn.execute("PRAGMA table_info(words)").fetchall()
    except FileNotFoundError:
        payload = _make_response(False, error="db_not_found")
        return json.dumps(payload, ensure_ascii=False)
    except sqlite3.Error:
        payload = _make_response(False, error="db_error")
        return json.dumps(payload, ensure_ascii=False)

    schema = [
        {
            "name": row["name"],
            "type": row["type"],
            "notnull": row["notnull"],
            "default": row["dflt_value"],
            "pk": row["pk"],
        }
        for row in rows
    ]
    return json.dumps(_make_response(True, data={"columns": schema}), ensure_ascii=False)


@mcp.prompt("neep_quiz")
def neep_quiz(count: int = 5) -> str:
    return (
        "You are preparing a vocabulary quiz based on the WordExtractor database. "
        "Call the get_random_words tool with the requested count, then create a short quiz "
        "(fill-in-the-blank or synonym choice). Provide the answer key after the questions. "
        f"Requested count: {count}."
    )


if __name__ == "__main__":
    mcp.run()
