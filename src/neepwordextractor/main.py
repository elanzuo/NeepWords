"""CLI entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .core import extract_words


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract words from a scanned PDF.")
    parser.add_argument("--pdf", required=True, help="Path to the source PDF.")
    parser.add_argument("--start-page", type=int, required=True, help="Start page (1-based).")
    parser.add_argument("--end-page", type=int, required=True, help="End page (1-based).")
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory (default: output).",
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
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
