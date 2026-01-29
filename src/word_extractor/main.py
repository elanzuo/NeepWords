"""CLI entry point."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from .core import extract_words
from .output import add_words_to_db, export_words_to_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract words from a scanned PDF.")
    parser.add_argument("--pdf", help="Path to the source PDF.")
    parser.add_argument("--start-page", type=int, help="Start page (1-based).")
    parser.add_argument("--end-page", type=int, help="End page (1-based).")
    parser.add_argument(
        "--output-dir",
        default="words",
        help="Output directory (default: words).",
    )
    parser.add_argument("--debug-dir", help="Optional debug output directory.")
    parser.add_argument(
        "--spellcheck",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Enable Cocoa-based spellchecking (default: enabled).",
    )
    parser.add_argument(
        "--spellcheck-rejected",
        choices=("csv", "db"),
        default="csv",
        help="Where to store spellcheck failures (default: csv).",
    )
    parser.add_argument(
        "--spellcheck-language",
        action="append",
        default=["en"],
        help="Spellcheck language (repeatable). Default: en.",
    )
    parser.add_argument(
        "--split-offset",
        "--split-offse",
        dest="split_offset",
        type=float,
        default=0.0,
        help="Column split offset as a fraction of page width (default: 0.0).",
    )

    subparsers = parser.add_subparsers(dest="command")
    add_parser = subparsers.add_parser(
        "add-words",
        help="Add words manually into the words.sqlite3 database.",
    )
    add_parser.add_argument(
        "--entry",
        action="append",
        default=[],
        help="Entry to insert as 'word[:source]' (repeatable).",
    )
    add_parser.add_argument(
        "--db-path",
        default="output/words.sqlite3",
        help="Path to words.sqlite3 (default: output/words.sqlite3).",
    )

    export_parser = subparsers.add_parser(
        "export-csv",
        help="Export words.sqlite3 data to a CSV file.",
    )
    export_parser.add_argument(
        "--db-path",
        default="output/words.sqlite3",
        help="Path to words.sqlite3 (default: output/words.sqlite3).",
    )
    export_parser.add_argument(
        "--csv-path",
        help="CSV output path (default: words/YYYY-MM-DD.csv).",
    )
    export_parser.add_argument(
        "--columns",
        default="word,source",
        help="Comma-separated columns to export (default: word,source).",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command == "add-words":
        if not args.entry:
            raise SystemExit("--entry is required (repeatable).")
        entries: list[dict[str, object]] = []
        for raw_entry in args.entry:
            entry = str(raw_entry).strip()
            if not entry:
                continue
            if ":" in entry:
                word, source = entry.split(":", 1)
            else:
                word, source = entry, None
            word = word.strip()
            source = source.strip() if source is not None else None
            if not word:
                raise SystemExit("Entry word cannot be empty. Use --entry 'word[:source]'.")
            entries.append({"word": word, "source": source})
        if not entries:
            raise SystemExit("No valid entries provided.")
        stats = add_words_to_db(
            entries,
            db_path=Path(args.db_path),
        )
        print(
            "Added {total_count} word(s) (unique: {unique_count}, duplicates: "
            "{duplicate_count}).".format(**stats)
        )
        return
    if args.command == "export-csv":
        columns = [col.strip() for col in str(args.columns).split(",") if col.strip()]
        if not columns:
            raise SystemExit("--columns must include at least one column name.")
        csv_path = (
            Path(args.csv_path)
            if args.csv_path
            else Path("words") / f"{date.today().isoformat()}.csv"
        )
        try:
            stats = export_words_to_csv(
                Path(args.db_path),
                csv_path,
                columns,
            )
        except (FileNotFoundError, ValueError) as exc:
            raise SystemExit(str(exc)) from exc
        print(f"Exported {stats['row_count']} row(s) to {stats['csv_path']}.")
        return

    missing = [name for name in ("pdf", "start_page", "end_page") if getattr(args, name) is None]
    if missing:
        raise SystemExit("--pdf, --start-page, and --end-page are required for extraction.")
    extract_words(
        pdf_path=Path(args.pdf),
        start_page=args.start_page,
        end_page=args.end_page,
        output_dir=Path(args.output_dir),
        debug_dir=Path(args.debug_dir) if args.debug_dir else None,
        split_offset=args.split_offset,
        spellcheck=args.spellcheck,
        spellcheck_rejected=args.spellcheck_rejected,
        spellcheck_languages=args.spellcheck_language,
    )


if __name__ == "__main__":
    main()
