"""Shared local word-lookup helpers for the NEEP vocabulary database."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

from word_extractor.storage import ResolvedVersion, detect_schema_mode, resolve_configured_version
from word_extractor.storage import list_versions as list_version_rows
from word_extractor.storage import resolve_db_path as resolve_storage_db_path
from word_extractor.storage import resolve_version as resolve_db_version

MAX_WORD_LENGTH = 64
MAX_LOOKUP = 200
MAX_SEARCH = 200

_WORD_RE = re.compile(r"[A-Za-z-]+")


@dataclass
class WordsQueryResult:
    word: str
    source: str | None
    added_at: str | None
    version: str | None


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


def resolve_db_path(explicit: str | Path | None = None, *, start: Path | None = None) -> Path:
    return resolve_storage_db_path(explicit, start=start)


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


def _row_to_result(row: sqlite3.Row, *, version: str | None) -> WordsQueryResult:
    return WordsQueryResult(
        word=row["word"],
        source=row["source"],
        added_at=row["added_at"],
        version=version,
    )


class WordsLexicon:
    def __init__(self, path: Path, configured_version: str | None = None) -> None:
        self._db = WordsDatabase(path)
        self.path = path
        self.configured_version = configured_version

    def _resolve_version(
        self, conn: sqlite3.Connection, *, version: str | None
    ) -> ResolvedVersion | None:
        schema_mode = detect_schema_mode(conn)
        if schema_mode == "legacy":
            if version is not None or self.configured_version is not None:
                raise ValueError("legacy_schema_no_versions")
            return None
        if schema_mode == "missing":
            raise ValueError("words_table_not_found")
        if schema_mode != "versioned":
            raise ValueError("unsupported_schema")
        return resolve_db_version(
            conn,
            requested_version=version,
            configured_version=self.configured_version,
        )

    def lookup_words(
        self,
        words: Iterable[str],
        match: str | None = "auto",
        version: str | None = None,
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
            resolved_version = self._resolve_version(conn, version=version)
            for item in items:
                original = str(item)
                cleaned, clean_warnings = sanitize_token(original)
                warnings.extend(clean_warnings)
                if cleaned is None:
                    results.append({"input": original, "found": False, "error": "invalid_input"})
                    continue

                if resolved_version is None:
                    row = conn.execute("SELECT * FROM words WHERE word = ?", (cleaned,)).fetchone()
                else:
                    row = conn.execute(
                        """
                        SELECT w.word, w.source, w.added_at
                        FROM words AS w
                        WHERE w.version_id = ? AND w.word = ?
                        """,
                        (resolved_version.id, cleaned),
                    ).fetchone()

                if row is None:
                    result: dict[str, Any] = {"input": original, "query": cleaned, "found": False}
                    if resolved_version is not None:
                        result["version"] = resolved_version.version_key
                    results.append(result)
                    continue

                payload = _row_to_result(
                    row,
                    version=resolved_version.version_key if resolved_version is not None else None,
                )
                result = {
                    "input": original,
                    "query": cleaned,
                    "found": True,
                    "word": payload.word,
                    "source": payload.source,
                    "added_at": payload.added_at,
                }
                if payload.version is not None:
                    result["version"] = payload.version
                results.append(result)

        payload: dict[str, Any] = {"results": results}
        if resolved_version is not None:
            payload["version"] = resolved_version.version_key
            payload["version_source"] = resolved_version.source
        return payload, warnings

    def search_words(
        self,
        query: str,
        mode: str | None = "contains",
        limit: int | None = 10,
        offset: int | None = 0,
        version: str | None = None,
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

        with self._db.connect() as conn:
            resolved_version = self._resolve_version(conn, version=version)
            if resolved_version is None:
                rows = conn.execute(
                    "SELECT word FROM words WHERE word LIKE ? ORDER BY word LIMIT ? OFFSET ?",
                    (pattern, limit_value, offset_value),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT w.word
                    FROM words AS w
                    WHERE w.version_id = ? AND w.word LIKE ?
                    ORDER BY w.word
                    LIMIT ? OFFSET ?
                    """,
                    (resolved_version.id, pattern, limit_value, offset_value),
                ).fetchall()

        results = [{"word": row["word"]} for row in rows]
        payload: dict[str, Any] = {
            "query": cleaned,
            "mode": mode_value,
            "limit": limit_value,
            "offset": offset_value,
            "results": results,
        }
        if resolved_version is not None:
            payload["version"] = resolved_version.version_key
            payload["version_source"] = resolved_version.source
        return payload, warnings

    def list_versions(self) -> dict[str, Any]:
        with self._db.connect() as conn:
            schema_mode = detect_schema_mode(conn)
            if schema_mode == "missing":
                raise ValueError("words_table_not_found")
            if schema_mode == "legacy":
                total = conn.execute("SELECT COUNT(*) AS count FROM words").fetchone()
                return {
                    "schema_mode": "legacy",
                    "versions": [],
                    "total_words": total["count"] if total else 0,
                }
            if schema_mode != "versioned":
                raise ValueError("unsupported_schema")
            versions = list_version_rows(conn)
            return {"schema_mode": "versioned", "versions": versions}

    def stats_summary(self) -> dict[str, Any]:
        with self._db.connect() as conn:
            schema_mode = detect_schema_mode(conn)
            if schema_mode == "missing":
                raise ValueError("words_table_not_found")
            if schema_mode == "legacy":
                total = conn.execute("SELECT COUNT(*) AS count FROM words").fetchone()
                last_added = conn.execute("SELECT MAX(added_at) AS added_at FROM words").fetchone()
                return {
                    "schema_mode": "legacy",
                    "total_words": total["count"] if total else 0,
                    "last_added": last_added["added_at"] if last_added else None,
                }
            if schema_mode != "versioned":
                raise ValueError("unsupported_schema")

            total = conn.execute("SELECT COUNT(*) AS count FROM words").fetchone()
            last_added = conn.execute("SELECT MAX(added_at) AS added_at FROM words").fetchone()
            versions = list_version_rows(conn)
        return {
            "schema_mode": "versioned",
            "total_words": total["count"] if total else 0,
            "last_added": last_added["added_at"] if last_added else None,
            "versions": versions,
        }

    def schema(self) -> dict[str, Any]:
        with self._db.connect() as conn:
            schema_mode = detect_schema_mode(conn)
            if schema_mode == "missing":
                raise ValueError("words_table_not_found")
            if schema_mode == "legacy":
                return {
                    "schema_mode": "legacy",
                    "tables": {
                        "words": [
                            {
                                "name": row["name"],
                                "type": row["type"],
                                "notnull": row["notnull"],
                                "default": row["dflt_value"],
                                "pk": row["pk"],
                            }
                            for row in conn.execute("PRAGMA table_info(words)").fetchall()
                        ]
                    },
                }
            if schema_mode != "versioned":
                raise ValueError("unsupported_schema")

            tables: dict[str, list[dict[str, Any]]] = {}
            for table_name in ("vocab_versions", "words"):
                tables[table_name] = [
                    {
                        "name": row["name"],
                        "type": row["type"],
                        "notnull": row["notnull"],
                        "default": row["dflt_value"],
                        "pk": row["pk"],
                    }
                    for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()
                ]
        return {"schema_mode": "versioned", "tables": tables}


def build_lexicon(
    db_path: str | Path | None = None,
    *,
    start: Path | None = None,
) -> WordsLexicon:
    path = resolve_db_path(db_path, start=start)
    configured_version, _ = resolve_configured_version(start=start)
    return WordsLexicon(path, configured_version=configured_version)
