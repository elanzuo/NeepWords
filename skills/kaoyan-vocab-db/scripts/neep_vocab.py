#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""Local CLI for direct Kaoyan vocabulary access without MCP."""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

MAX_WORD_LENGTH = 64
MAX_LOOKUP = 200
MAX_SEARCH = 200
SKILL_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_DB_PATH = SKILL_ROOT / "examples" / "words.sqlite3"
_WORD_RE = re.compile(r"[A-Za-z-]+")


@dataclass(frozen=True)
class ResolvedVersion:
    id: int
    version_key: str
    label: str | None
    source: str


ERROR_INFO: dict[str, dict[str, Any]] = {
    "db_not_found": {
        "message": "Vocabulary database file was not found.",
        "retryable": True,
        "hint": "Pass --db-path explicitly, set NEEP_WORDS_DB_PATH, or use the bundled example database.",
    },
    "db_path_required_for_write": {
        "message": "A writable database path is required for default-version changes.",
        "retryable": False,
        "hint": "Pass --db-path explicitly or set NEEP_WORDS_DB_PATH to a writable versioned database.",
    },
    "db_error": {
        "message": "SQLite failed while reading or updating the vocabulary database.",
        "retryable": True,
        "hint": "Verify the database file is readable, writable when needed, and valid, then retry the command.",
    },
    "words_table_not_found": {
        "message": "The target SQLite database does not contain the expected words table.",
        "retryable": False,
        "hint": "Use a Kaoyan-vocab compatible database or point --db-path at the correct file.",
    },
    "unsupported_schema": {
        "message": "The target SQLite database schema is not supported by this CLI.",
        "retryable": False,
        "hint": "Use a compatible legacy or versioned Kaoyan vocabulary database.",
    },
    "legacy_schema_no_versions": {
        "message": "This database uses the legacy schema and cannot resolve or change versions.",
        "retryable": False,
        "hint": "Use a versioned working database for version-aware queries or default-version changes.",
    },
    "missing_version": {
        "message": "A vocabulary version could not be resolved for this database.",
        "retryable": False,
        "hint": "Pass --version explicitly or use a database with a default or single available version.",
    },
    "missing_words": {
        "message": "Lookup requires at least one input word.",
        "retryable": False,
        "hint": "Pass one or more English words after the lookup command.",
    },
    "missing_query": {
        "message": "Search requires a query string.",
        "retryable": False,
        "hint": "Pass a search string after the search command.",
    },
    "invalid_match": {
        "message": "Lookup match mode is invalid.",
        "retryable": False,
        "hint": "Use --match auto or --match word.",
    },
    "invalid_mode": {
        "message": "Search mode is invalid.",
        "retryable": False,
        "hint": "Use one of: prefix, suffix, contains, fuzzy, wildcard.",
    },
    "invalid_query": {
        "message": "Search query is invalid after normalization.",
        "retryable": False,
        "hint": "Use at least one English letter. Wildcard mode only accepts letters, '-', '%' and '_'.",
    },
    "invalid_limit": {
        "message": "Search limit must be an integer.",
        "retryable": False,
        "hint": "Pass --limit with a positive integer value.",
    },
    "invalid_offset": {
        "message": "Search offset must be an integer.",
        "retryable": False,
        "hint": "Pass --offset with a non-negative integer value.",
    },
    "too_many_words": {
        "message": "Lookup received too many input words.",
        "retryable": False,
        "hint": "Split the request into smaller batches.",
    },
    "unknown_version": {
        "message": "The requested vocabulary version does not exist in the database.",
        "retryable": False,
        "hint": "Run list-versions first, then choose one of the returned version keys.",
    },
    "unknown_configured_version": {
        "message": "The configured vocabulary version does not exist in the database.",
        "retryable": False,
        "hint": "Update NEEP_WORDS_VERSION or use --version with an available version key.",
    },
}


def normalize_version_key(value: str | int | None) -> str:
    if value is None:
        raise ValueError("missing_version")

    raw = str(value).strip()
    if not raw:
        raise ValueError("missing_version")

    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 2:
        year = 2000 + int(digits)
    elif len(digits) == 4:
        year = int(digits)
    else:
        raise ValueError("invalid_version")

    if year < 2000 or year > 2099:
        raise ValueError("invalid_version")

    return str(year)


def table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row[1] for row in rows]


def detect_schema_mode(conn: sqlite3.Connection) -> str:
    words_columns = table_columns(conn, "words")
    if not words_columns:
        return "missing"

    versions_columns = table_columns(conn, "vocab_versions")
    if versions_columns:
        required_words = {"id", "version_id", "word", "source", "added_at"}
        required_versions = {
            "id",
            "version_key",
            "label",
            "source_pdf",
            "imported_at",
            "is_default",
        }
        if required_words.issubset(set(words_columns)) and required_versions.issubset(
            set(versions_columns)
        ):
            return "versioned"
        return "unknown"

    legacy_words = {"id", "word", "source", "added_at"}
    if set(words_columns) == legacy_words:
        return "legacy"

    return "unknown"


def list_versions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            vv.id,
            vv.version_key,
            vv.label,
            vv.source_pdf,
            vv.imported_at,
            vv.is_default,
            COUNT(w.id) AS word_count
        FROM vocab_versions AS vv
        LEFT JOIN words AS w ON w.version_id = vv.id
        GROUP BY vv.id
        ORDER BY vv.version_key
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "version": row[1],
            "label": row[2],
            "source_pdf": row[3],
            "imported_at": row[4],
            "is_default": bool(row[5]),
            "word_count": row[6],
        }
        for row in rows
    ]


def resolve_configured_version() -> str | None:
    env_value = os.environ.get("NEEP_WORDS_VERSION")
    if env_value:
        return normalize_version_key(env_value)
    return None


def resolve_read_db_path(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit)

    env_value = os.environ.get("NEEP_WORDS_DB_PATH")
    if env_value:
        return Path(env_value)

    return EXAMPLE_DB_PATH


def resolve_write_db_path(explicit: str | Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit)

    env_value = os.environ.get("NEEP_WORDS_DB_PATH")
    if env_value:
        return Path(env_value)

    raise ValueError("db_path_required_for_write")


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
    raw = str(value).strip()
    if not raw:
        return None, ["empty_input"]

    cleaned_chars: list[str] = []
    has_letter = False
    for ch in raw:
        if "A" <= ch <= "Z":
            cleaned_chars.append(ch.lower())
            has_letter = True
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


def connect_readonly(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError
    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def connect_writable(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise FileNotFoundError
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def resolve_version(
    conn: sqlite3.Connection,
    *,
    requested_version: str | None = None,
    configured_version: str | None = None,
) -> ResolvedVersion:
    explicit = normalize_version_key(requested_version) if requested_version is not None else None
    if explicit is not None:
        row = conn.execute(
            "SELECT id, version_key, label FROM vocab_versions WHERE version_key = ?",
            (explicit,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown_version")
        return ResolvedVersion(id=row[0], version_key=row[1], label=row[2], source="explicit")

    if configured_version is not None:
        row = conn.execute(
            "SELECT id, version_key, label FROM vocab_versions WHERE version_key = ?",
            (configured_version,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown_configured_version")
        return ResolvedVersion(id=row[0], version_key=row[1], label=row[2], source="configured")

    default_row = conn.execute(
        """
        SELECT id, version_key, label
        FROM vocab_versions
        WHERE is_default = 1
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()
    if default_row is not None:
        return ResolvedVersion(
            id=default_row[0],
            version_key=default_row[1],
            label=default_row[2],
            source="db_default",
        )

    rows = conn.execute(
        "SELECT id, version_key, label FROM vocab_versions ORDER BY version_key"
    ).fetchall()
    if len(rows) == 1:
        row = rows[0]
        return ResolvedVersion(id=row[0], version_key=row[1], label=row[2], source="single_available")

    raise ValueError("missing_version")


def resolve_version_for_query(
    conn: sqlite3.Connection,
    *,
    requested_version: str | None = None,
    configured_version: str | None = None,
) -> ResolvedVersion | None:
    schema_mode = detect_schema_mode(conn)
    if schema_mode == "legacy":
        if requested_version is not None or configured_version is not None:
            raise ValueError("legacy_schema_no_versions")
        return None
    if schema_mode == "missing":
        raise ValueError("words_table_not_found")
    if schema_mode != "versioned":
        raise ValueError("unsupported_schema")
    return resolve_version(
        conn,
        requested_version=requested_version,
        configured_version=configured_version,
    )


def set_default_version(conn: sqlite3.Connection, version_key: str | int) -> dict[str, Any]:
    schema_mode = detect_schema_mode(conn)
    if schema_mode == "missing":
        raise ValueError("words_table_not_found")
    if schema_mode == "legacy":
        raise ValueError("legacy_schema_no_versions")
    if schema_mode != "versioned":
        raise ValueError("unsupported_schema")

    normalized = normalize_version_key(version_key)
    row = conn.execute(
        "SELECT id, version_key, label FROM vocab_versions WHERE version_key = ?",
        (normalized,),
    ).fetchone()
    if row is None:
        raise ValueError("unknown_version")

    conn.execute("UPDATE vocab_versions SET is_default = 0 WHERE is_default != 0")
    conn.execute("UPDATE vocab_versions SET is_default = 1 WHERE id = ?", (row[0],))
    conn.commit()
    return {
        "id": row[0],
        "version": row[1],
        "label": row[2],
        "is_default": True,
    }


def lookup_words(
    conn: sqlite3.Connection,
    words: Iterable[str],
    *,
    match: str | None = "auto",
    version: str | None = None,
) -> tuple[dict[str, Any], list[str]]:
    items = list(words)
    if not items:
        raise ValueError("missing_words")
    if len(items) > MAX_LOOKUP:
        raise ValueError("too_many_words")

    match_value = (match or "auto").lower()
    if match_value not in {"auto", "word"}:
        raise ValueError("invalid_match")

    configured_version = resolve_configured_version()
    resolved_version = resolve_version_for_query(
        conn,
        requested_version=version,
        configured_version=configured_version,
    )

    results: list[dict[str, Any]] = []
    warnings: list[str] = []
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

        result = {
            "input": original,
            "query": cleaned,
            "found": True,
            "word": row["word"],
            "source": row["source"],
            "added_at": row["added_at"],
        }
        if resolved_version is not None:
            result["version"] = resolved_version.version_key
        results.append(result)

    payload: dict[str, Any] = {"results": results}
    if resolved_version is not None:
        payload["version"] = resolved_version.version_key
        payload["version_source"] = resolved_version.source
    return payload, warnings


def search_words(
    conn: sqlite3.Connection,
    query: str,
    *,
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

    configured_version = resolve_configured_version()
    resolved_version = resolve_version_for_query(
        conn,
        requested_version=version,
        configured_version=configured_version,
    )
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

    payload: dict[str, Any] = {
        "query": cleaned,
        "mode": mode_value,
        "limit": limit_value,
        "offset": offset_value,
        "results": [{"word": row["word"]} for row in rows],
    }
    if resolved_version is not None:
        payload["version"] = resolved_version.version_key
        payload["version_source"] = resolved_version.source
    return payload, warnings


def _add_shared_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to the vocabulary SQLite database. Read commands default to the bundled example DB.",
    )
    parser.add_argument(
        "--version",
        default=None,
        help="Optional vocabulary version such as 2027 or 27考研.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output. This is the recommended mode for agent use.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Access the local Kaoyan vocabulary database without MCP.",
        epilog=(
            "Examples:\n"
            "  uv run scripts/neep_vocab.py lookup --json abandon derive inevitable\n"
            "  uv run scripts/neep_vocab.py search --json --mode prefix trans\n"
            "  uv run scripts/neep_vocab.py list-versions --json\n"
            "  uv run scripts/neep_vocab.py set-default-version --db-path ./words.sqlite3 --json --version 2027"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    lookup = subparsers.add_parser("lookup", help="Check whether words exist in the lexicon.")
    lookup.add_argument("words", nargs="+", help="Words to look up.")
    lookup.add_argument(
        "--match",
        choices=["auto", "word"],
        default="auto",
        help="Matching strategy (default: auto).",
    )
    _add_shared_args(lookup)

    search = subparsers.add_parser("search", help="Search for words by pattern.")
    search.add_argument("query", help="Search query.")
    search.add_argument(
        "--mode",
        choices=["prefix", "suffix", "contains", "fuzzy", "wildcard"],
        default="contains",
        help="Search mode (default: contains).",
    )
    search.add_argument("--limit", type=int, default=10, help="Max results to return.")
    search.add_argument("--offset", type=int, default=0, help="Pagination offset.")
    _add_shared_args(search)

    list_versions_parser = subparsers.add_parser(
        "list-versions",
        help="List available vocabulary versions in the lexicon.",
    )
    list_versions_parser.add_argument(
        "--db-path",
        default=None,
        help="Path to the vocabulary SQLite database. Defaults to the bundled example DB.",
    )
    list_versions_parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output. This is the recommended mode for agent use.",
    )

    set_default = subparsers.add_parser(
        "set-default-version",
        help="Set the database default vocabulary version.",
    )
    set_default.add_argument(
        "--db-path",
        default=None,
        help="Path to a writable versioned vocabulary SQLite database.",
    )
    set_default.add_argument(
        "--version",
        required=True,
        help="Vocabulary version such as 2027 or 27考研.",
    )
    set_default.add_argument(
        "--json",
        action="store_true",
        help="Print JSON output. This is the recommended mode for agent use.",
    )
    return parser


def _print_json(response: dict[str, Any]) -> None:
    print(json.dumps(response, ensure_ascii=False, indent=2))


def _command_name(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("-", "_")


def _success_response(command: str, data: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    return {
        "command": _command_name(command),
        "ok": True,
        "data": data,
        "warnings": warnings,
        "error": None,
    }


def _error_response(command: str | None, code: str) -> dict[str, Any]:
    meta = ERROR_INFO.get(
        code,
        {
            "message": "The command failed.",
            "retryable": False,
            "hint": "Inspect the command inputs and database configuration, then retry if appropriate.",
        },
    )
    return {
        "command": _command_name(command),
        "ok": False,
        "data": None,
        "warnings": [],
        "error": {
            "code": code,
            "message": meta["message"],
            "retryable": meta["retryable"],
            "hint": meta["hint"],
        },
    }


def _emit_error(command: str | None, code: str) -> int:
    print(json.dumps(_error_response(command, code), ensure_ascii=False), file=sys.stderr)
    return 2


def _format_lookup(results: list[dict[str, Any]], warnings: list[str]) -> str:
    lines: list[str] = []
    if warnings:
        lines.append(f"warnings: {', '.join(warnings)}")
    for row in results:
        status = row.get("status")
        if status == "invalid_input":
            lines.append(f"{row['input']}: invalid_input")
            continue
        if status == "not_found" or not row.get("found"):
            query = row.get("query") or row.get("input")
            lines.append(f"{query}: not_found")
            continue
        parts = [f"{row['input']}: found", f"word={row['word']}"]
        if row.get("version"):
            parts.append(f"version={row['version']}")
        if row.get("source"):
            parts.append(f"source={row['source']}")
        if row.get("added_at"):
            parts.append(f"added_at={row['added_at']}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _format_search(data: dict[str, Any], warnings: list[str]) -> str:
    lines: list[str] = []
    if warnings:
        lines.append(f"warnings: {', '.join(warnings)}")
    header = f"query={data['query']} mode={data['mode']} limit={data['limit']} offset={data['offset']}"
    if data.get("version"):
        header += f" version={data['version']}"
    lines.append(header)
    for row in data["results"]:
        lines.append(row["word"])
    return "\n".join(lines)


def _format_versions(data: dict[str, Any]) -> str:
    if data["schema_mode"] == "legacy":
        return f"schema=legacy total_words={data['total_words']}"

    lines: list[str] = []
    for row in data["versions"]:
        line = f"{row['version']}: words={row['word_count']}"
        if row.get("label"):
            line += f" label={row['label']}"
        if row.get("is_default"):
            line += " *"
        lines.append(line)
    return "\n".join(lines)


def _handle_list_versions(args: argparse.Namespace) -> int:
    db_path = resolve_read_db_path(args.db_path)
    with connect_readonly(db_path) as conn:
        schema_mode = detect_schema_mode(conn)
        if schema_mode == "missing":
            raise ValueError("words_table_not_found")
        if schema_mode == "legacy":
            total = conn.execute("SELECT COUNT(*) AS count FROM words").fetchone()
            data = {
                "schema_mode": "legacy",
                "versions": [],
                "total_words": total[0] if total is not None else 0,
            }
        elif schema_mode == "versioned":
            data = {"schema_mode": "versioned", "versions": list_versions(conn)}
        else:
            raise ValueError("unsupported_schema")
    response = _success_response(args.command, data, [])
    if args.json:
        _print_json(response)
    else:
        print(_format_versions(data))
    return 0


def _handle_set_default_version(args: argparse.Namespace) -> int:
    db_path = resolve_write_db_path(args.db_path)
    with connect_writable(db_path) as conn:
        data = set_default_version(conn, args.version)
    response = _success_response(args.command, data, [])
    if args.json:
        _print_json(response)
    else:
        print(f"default_version={data['version']}")
    return 0


def _handle_lookup(args: argparse.Namespace) -> int:
    db_path = resolve_read_db_path(args.db_path)
    with connect_readonly(db_path) as conn:
        data, warnings = lookup_words(conn, args.words, match=args.match, version=args.version)
    for row in data["results"]:
        if row.get("found"):
            row["status"] = "found"
        elif row.get("error") == "invalid_input":
            row["status"] = "invalid_input"
        else:
            row["status"] = "not_found"
    response = _success_response(args.command, data, warnings)
    if args.json:
        _print_json(response)
    else:
        print(_format_lookup(data["results"], warnings))
    return 0


def _handle_search(args: argparse.Namespace) -> int:
    db_path = resolve_read_db_path(args.db_path)
    with connect_readonly(db_path) as conn:
        data, warnings = search_words(
            conn,
            query=args.query,
            mode=args.mode,
            limit=args.limit,
            offset=args.offset,
            version=args.version,
        )
    response = _success_response(args.command, data, warnings)
    if args.json:
        _print_json(response)
    else:
        print(_format_search(data, warnings))
    return 0


def main() -> int:
    args = build_parser().parse_args()
    command = args.command
    try:
        if command == "list-versions":
            return _handle_list_versions(args)
        if command == "set-default-version":
            return _handle_set_default_version(args)
        if command == "lookup":
            return _handle_lookup(args)
        if command == "search":
            return _handle_search(args)
        raise ValueError("unsupported_command")
    except FileNotFoundError:
        return _emit_error(command, "db_not_found")
    except ValueError as exc:
        return _emit_error(command, str(exc))
    except sqlite3.Error:
        return _emit_error(command, "db_error")


if __name__ == "__main__":
    raise SystemExit(main())
