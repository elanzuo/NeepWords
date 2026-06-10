#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "openpyxl>=3.1.0",
#   "reportlab>=4.0.0",
# ]
# ///
"""Generate printable Kaoyan vocabulary review sheets."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Iterable


REVIEW_COLUMNS = ["D0", "D1", "D2", "D4", "D7", "D15", "D30"]
CONTENT_COLUMNS = ["序号", "单词", "音标(美)", "释义", "助记", "笔记"]
ALL_COLUMNS = CONTENT_COLUMNS + REVIEW_COLUMNS
PDF_FONT_CANDIDATES = [
    ("ArialUnicode", Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")),
    ("ArialUnicode", Path("/Library/Fonts/Arial Unicode.ttf")),
]
XLSX_FONT_NAME = "Arial Unicode MS"
SKIP_TOKENS = {
    "word",
    "words",
    "单词",
    "note",
    "notes",
    "释义",
    "meaning",
    "v",
    "vi",
    "vt",
    "n",
    "adj",
    "adv",
}


def parse_words_from_text(text: str) -> list[str]:
    words: list[str] = []
    seen: set[str] = set()

    for raw in re.split(r"[\n,，;；、\t]+", text):
        word = _clean_word(raw)
        if not word:
            continue
        key = word.lower()
        if key not in seen:
            seen.add(key)
            words.append(word)

    return words


def parse_words_from_csv(path: Path) -> list[str]:
    words: list[str] = []
    seen: set[str] = set()

    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        for row in reader:
            if not row:
                continue
            for cell in row:
                for word in parse_words_from_text(cell):
                    key = word.lower()
                    if key not in seen:
                        seen.add(key)
                        words.append(word)

    return words


def build_placeholder_entries(words: Iterable[str]) -> list[dict[str, object]]:
    return [
        {
            "index": index,
            "word": word,
            "us_phonetic": "",
            "meaning": "",
            "mnemonic": "",
        }
        for index, word in enumerate(words, start=1)
    ]


def load_entries_from_json(path: Path) -> list[dict[str, object]]:
    raw_json = sys.stdin.read() if str(path) == "-" else path.read_text(encoding="utf-8")
    payload = json.loads(raw_json)
    if not isinstance(payload, dict):
        raise RuntimeError("entries JSON 必须是包含 source_words 和 entries 的对象")
    if "source_words" not in payload or "entries" not in payload:
        raise RuntimeError("entries JSON 必须同时包含 source_words 和 entries")

    source_words = [_clean_entry_word(str(word)) for word in payload["source_words"]]
    source_words = [word for word in source_words if word]
    payload = payload["entries"]
    if not isinstance(payload, list):
        raise RuntimeError("entries JSON 的 entries 必须是数组")

    entries = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise RuntimeError(f"第 {index} 个词条不是对象")
        word = _clean_entry_word(str(item.get("word", "")))
        if not word:
            raise RuntimeError(f"第 {index} 个词条缺少有效 word")
        entries.append(
            {
                "index": len(entries) + 1,
                "word": word,
                "us_phonetic": _stringify_optional_text(item.get("us_phonetic")),
                "meaning": _stringify_optional_text(item.get("meaning")),
                "mnemonic": _stringify_optional_text(item.get("mnemonic")),
            }
        )
    if [entry["word"] for entry in entries] != source_words:
        raise RuntimeError("entries JSON 与 source_words 不一致，请检查是否静默改词、漏词或乱序")
    return entries


def write_xlsx(entries: list[dict[str, object]], path: Path) -> None:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, Side
        from openpyxl.worksheet.page import PageMargins
    except ImportError as exc:
        raise RuntimeError("缺少 openpyxl 依赖，请使用 uv run scripts/vocab_sheet.py ...") from exc

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "单词复习表"

    sheet.append(ALL_COLUMNS)
    for entry in entries:
        sheet.append(
            [
                entry["index"],
                entry["word"],
                entry["us_phonetic"],
                entry["meaning"],
                entry["mnemonic"],
                "",
                *["" for _ in REVIEW_COLUMNS],
            ]
        )

    widths = [6, 17, 17, 34, 26, 14, 7, 7, 7, 7, 7, 7, 7]
    for column_index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + column_index)].width = width

    thin = Side(style="thin", color="333333")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    for row in sheet.iter_rows():
        for cell in row:
            cell.border = border
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.font = Font(name=XLSX_FONT_NAME, size=10, bold=cell.row == 1)
        sheet.row_dimensions[row[0].row].height = 34 if row[0].row > 1 else 24

    sheet.freeze_panes = "A2"
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.page_margins = PageMargins(left=0.25, right=0.25, top=0.35, bottom=0.35)

    path.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(path)


def write_pdf(entries: list[dict[str, object]], path: Path) -> None:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle
    except ImportError as exc:
        raise RuntimeError("缺少 reportlab 依赖，请使用 uv run scripts/vocab_sheet.py ...") from exc

    path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(path),
        pagesize=landscape(A4),
        leftMargin=18,
        rightMargin=18,
        topMargin=18,
        bottomMargin=18,
    )

    font_name = _register_pdf_font(pdfmetrics, TTFont, UnicodeCIDFont)
    style = ParagraphStyle(
        "cell",
        fontName=font_name,
        fontSize=8,
        leading=10,
        wordWrap="CJK",
        alignment=1,
    )
    header_style = ParagraphStyle(
        "header",
        parent=style,
        fontSize=8,
        leading=10,
        alignment=1,
    )

    data = [[Paragraph(str(value), header_style) for value in ALL_COLUMNS]]
    for entry in entries:
        data.append(
            [
                Paragraph(str(entry["index"]), style),
                Paragraph(str(entry["word"]), style),
                Paragraph(str(entry["us_phonetic"]), style),
                Paragraph(str(entry["meaning"]), style),
                Paragraph(str(entry["mnemonic"]), style),
                Paragraph("", style),
                *[Paragraph("", style) for _ in REVIEW_COLUMNS],
            ]
        )

    table = Table(
        data,
        colWidths=[28, 78, 78, 175, 135, 70, 30, 30, 30, 30, 30, 30, 30],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWHEIGHT", (0, 1), (-1, -1), 28),
            ]
        )
    )
    doc.build([table])


def load_words_from_path(path: Path) -> list[str]:
    if path.suffix.lower() == ".csv":
        return parse_words_from_csv(path)
    return parse_words_from_text(path.read_text(encoding="utf-8"))


def build_arg_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
        description="生成 A4 考研单词复习表",
        epilog=(
            "Examples:\n"
            "  uv run scripts/vocab_sheet.py examples/words.txt\n"
            "  uv run scripts/vocab_sheet.py --entries-json - --xlsx"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    parser.add_argument("input", nargs="?", help="txt/csv 单词文件路径")
    parser.add_argument("--paste", action="store_true", help="从标准输入粘贴单词列表")
    parser.add_argument("--entries-json", help="已补全词条 JSON 路径，或用 - 从 stdin 读取")
    parser.add_argument("--out-dir", default="output", help="输出目录，默认 output")
    parser.add_argument("--date", default=date.today().isoformat(), help="文件名日期，默认今天")
    parser.add_argument("--xlsx", action="store_true", help="同时生成 xlsx；默认仅生成 pdf")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON 结果")
    args = parser.parse_args(argv)

    if args.entries_json:
        entries = load_entries_from_json(Path(args.entries_json))
    elif args.paste:
        words = parse_words_from_text(sys.stdin.read())
    elif args.input:
        words = load_words_from_path(Path(args.input))
    else:
        parser.error("请提供 txt/csv 文件，或使用 --paste 从标准输入读取")

    if not args.entries_json:
        if not words:
            parser.error("没有解析到单词")
        entries = build_placeholder_entries(words)
    elif not entries:
        parser.error("entries JSON 中没有可用词条")

    out_dir = Path(args.out_dir)
    pdf_path = out_dir / f"{args.date}-vocab.pdf"
    write_pdf(entries, pdf_path)
    xlsx_path: Path | None = None
    if args.xlsx:
        xlsx_path = out_dir / f"{args.date}-vocab.xlsx"
        write_xlsx(entries, xlsx_path)
    if args.json:
        print(
            json.dumps(
                {
                    "ok": True,
                    "pdf_path": str(pdf_path),
                    "xlsx_path": str(xlsx_path) if xlsx_path is not None else None,
                    "entry_count": len(entries),
                },
                ensure_ascii=False,
            )
        )
        return 0

    print(f"已生成: {pdf_path}")
    if xlsx_path is not None:
        print(f"已生成: {xlsx_path}")
    print(f"词条数: {len(entries)}")
    return 0


def _clean_word(raw: str) -> str:
    word = re.sub(r"^\s*(?:[-*•]|\d+[.)、])\s*", "", raw).strip()
    word = re.split(r"[（(【\[]", word, maxsplit=1)[0]
    word = word.strip(" \r\n\t.:：;；,，、")
    if word.lower() in SKIP_TOKENS:
        return ""
    if not re.fullmatch(r"[A-Za-z][A-Za-z' -]*", word):
        return ""
    return re.sub(r"\s+", " ", word)


def _clean_entry_word(raw: str) -> str:
    word = re.sub(r"^\s*(?:[-*•]|\d+[.)、])\s*", "", raw).strip()
    word = re.split(r"[（(【\[]", word, maxsplit=1)[0]
    word = word.strip(" \r\n\t.:：;；,，、")
    if word.lower() in SKIP_TOKENS:
        return ""
    if not re.fullmatch(r"[A-Za-z][A-Za-z' -]*", word):
        return ""
    return re.sub(r"\s+", " ", word)


def _stringify_optional_text(value: object | None) -> str:
    if value is None:
        return ""
    return str(value)


def _register_pdf_font(pdfmetrics, ttfont_cls, cidfont_cls) -> str:
    for font_name, font_path in PDF_FONT_CANDIDATES:
        if font_path.exists():
            pdfmetrics.registerFont(ttfont_cls(font_name, str(font_path)))
            return font_name

    fallback = "STSong-Light"
    pdfmetrics.registerFont(cidfont_cls(fallback))
    return fallback


if __name__ == "__main__":
    raise SystemExit(main())
