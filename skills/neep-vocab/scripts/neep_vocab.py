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

from neep_mcp.lexicon import WordsLexicon, resolve_db_path  # noqa: E402


def _add_shared_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db-path",
        default=None,
        help="Path to words.sqlite3 (default: resources/data/words.sqlite3 or NEEP_WORDS_DB_PATH).",
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

    random = subparsers.add_parser("random", help="Return random words from the lexicon.")
    random.add_argument("--count", type=int, default=5, help="Number of words to return.")
    _add_shared_args(random)

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
    lines.append(
        f"query={data['query']} mode={data['mode']} limit={data['limit']} offset={data['offset']}"
    )
    for row in data["results"]:
        lines.append(row["word"])
    return "\n".join(lines)


def _format_random(data: dict[str, Any]) -> str:
    lines = [f"count={data['count']}"]
    for row in data["results"]:
        parts = [row["word"]]
        if row.get("source"):
            parts.append(f"source={row['source']}")
        if row.get("added_at"):
            parts.append(f"added_at={row['added_at']}")
        lines.append(" | ".join(parts))
    return "\n".join(lines)


def _print_json(response: dict[str, Any]) -> None:
    print(json.dumps(response, ensure_ascii=False, indent=2))


def main() -> int:
    args = _build_parser().parse_args()
    db_path = Path(args.db_path) if args.db_path else resolve_db_path()
    lexicon = WordsLexicon(db_path)

    try:
        if args.command == "lookup":
            data, warnings = lexicon.lookup_words(args.words, match=args.match)
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
            )
            response = {"ok": True, "data": data, "warnings": warnings}
            if args.json:
                _print_json(response)
            else:
                print(_format_search(data, warnings))
            return 0

        data = lexicon.get_random_words(count=args.count)
        response = {"ok": True, "data": data, "warnings": []}
        if args.json:
            _print_json(response)
        else:
            print(_format_random(data))
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
