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
    parser.add_argument("--output-dir", required=True, help="Output directory.")
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    extract_words(
        pdf_path=Path(args.pdf),
        start_page=args.start_page,
        end_page=args.end_page,
        output_dir=Path(args.output_dir),
        debug_dir=Path(args.debug_dir) if args.debug_dir else None,
        spellcheck=args.spellcheck,
        spellcheck_rejected=args.spellcheck_rejected,
    )


if __name__ == "__main__":
    main()
