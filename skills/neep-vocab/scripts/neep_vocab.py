#!/usr/bin/env python3
"""Local CLI for direct NEEP vocabulary access without MCP."""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from neep_mcp.lexicon import build_lexicon, resolve_db_path  # noqa: E402
from word_extractor.storage import (  # noqa: E402
    detect_schema_mode,
    list_versions,
    resolve_writable_db_path,
    set_default_version,
)


def _add_shared_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to words.sqlite3 (default: config/env/default repository path).",
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


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Access the local NEEP vocabulary database without MCP."
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
        help="Path to words.sqlite3 (default: config/env/default repository path).",
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
        help="Path to words.sqlite3 (default: config/env/default repository path).",
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


def _format_lookup(results: list[dict[str, Any]], warnings: list[str]) -> str:
    lines: list[str] = []
    if warnings:
        lines.append(f"warnings: {', '.join(warnings)}")
    for row in results:
        if not row.get("found"):
            query = row.get("query") or row.get("input")
            lines.append(f"{query}: not found")
            continue
        parts = [
            f"{row['input']}: found",
            f"word={row['word']}",
        ]
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


def _print_json(response: dict[str, Any]) -> None:
    print(json.dumps(response, ensure_ascii=False, indent=2))


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


def main() -> int:
    args = _build_parser().parse_args()

    try:
        if args.command == "list-versions":
            db_path = resolve_db_path(args.db_path, start=Path.cwd())
            if not db_path.exists():
                raise FileNotFoundError
            with sqlite3.connect(db_path) as conn:
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
            response = {"ok": True, "data": data, "warnings": []}
            if args.json:
                _print_json(response)
            else:
                print(_format_versions(data))
            return 0

        if args.command == "set-default-version":
            db_path = resolve_writable_db_path(args.db_path, start=Path.cwd())
            if not db_path.exists():
                raise FileNotFoundError
            with sqlite3.connect(db_path) as conn:
                data = set_default_version(conn, args.version)
            response = {"ok": True, "data": data, "warnings": []}
            if args.json:
                _print_json(response)
            else:
                print(f"default_version={data['version']}")
            return 0

        db_path = resolve_db_path(args.db_path, start=Path.cwd())
        lexicon = build_lexicon(db_path, start=Path.cwd())

        if args.command == "lookup":
            data, warnings = lexicon.lookup_words(args.words, match=args.match, version=args.version)
            response = {"ok": True, "data": data, "warnings": warnings}
            if args.json:
                _print_json(response)
            else:
                print(_format_lookup(data["results"], warnings))
            return 0

        if args.command == "search":
            data, warnings = lexicon.search_words(
                query=args.query,
                mode=args.mode,
                limit=args.limit,
                offset=args.offset,
                version=args.version,
            )
            response = {"ok": True, "data": data, "warnings": warnings}
            if args.json:
                _print_json(response)
            else:
                print(_format_search(data, warnings))
            return 0

    except FileNotFoundError:
        print(json.dumps({"ok": False, "error": "db_not_found"}), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        return 2
    except sqlite3.Error:
        print(json.dumps({"ok": False, "error": "db_error"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
