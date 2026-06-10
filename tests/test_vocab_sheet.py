import contextlib
import csv
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "skills"
    / "kaoyan-vocab-sheet"
    / "scripts"
    / "vocab_sheet.py"
)
SPEC = importlib.util.spec_from_file_location("kaoyan_vocab_sheet_script", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"Unable to load vocab sheet script at {SCRIPT_PATH}")
vocab_sheet = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(vocab_sheet)

ALL_COLUMNS = vocab_sheet.ALL_COLUMNS
build_placeholder_entries = vocab_sheet.build_placeholder_entries
load_entries_from_json = vocab_sheet.load_entries_from_json
parse_words_from_csv = vocab_sheet.parse_words_from_csv
parse_words_from_text = vocab_sheet.parse_words_from_text


class VocabSheetTests(unittest.TestCase):
    def test_parse_words_from_text_keeps_order_and_deduplicates(self):
        text = """
        bypass
        quantify, disposition
        consequence（结果；后果）
        transition（过渡、转变）
        sober、reign
        bypass

        flourish
        """

        self.assertEqual(
            parse_words_from_text(text),
            [
                "bypass",
                "quantify",
                "disposition",
                "consequence",
                "transition",
                "sober",
                "reign",
                "flourish",
            ],
        )

    def test_parse_words_from_text_preserves_multiword_entries(self):
        self.assertEqual(
            parse_words_from_text("air conditioner, air conditioning"),
            ["air conditioner", "air conditioning"],
        )

    def test_parse_words_from_csv_reads_all_cells_by_default(self):
        path = Path("tmp_words.csv")
        try:
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.writer(handle)
                writer.writerow(["word", "word2", "note"])
                writer.writerow(["deceive", "noticeable（明显的）", "v. 欺骗"])
                writer.writerow(["sober、reign", "", ""])

            self.assertEqual(
                parse_words_from_csv(path),
                ["deceive", "noticeable", "sober", "reign"],
            )
        finally:
            path.unlink(missing_ok=True)

    def test_build_placeholder_entries_has_fixed_print_fields(self):
        entries = build_placeholder_entries(["bypass"])

        self.assertEqual(
            entries,
            [
                {
                    "index": 1,
                    "word": "bypass",
                    "us_phonetic": "",
                    "meaning": "",
                    "mnemonic": "",
                }
            ],
        )

    def test_load_entries_from_json_normalizes_print_fields(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            entries_path = Path(tmpdir) / "entries.json"
            entries_path.write_text(
                json.dumps(
                    {
                        "source_words": ["consequence"],
                        "entries": [
                            {
                                "word": "consequence",
                                "us_phonetic": "/ˈkɑːnsəkwens/",
                                "meaning": "n. 结果；后果",
                                "mnemonic": "con- + sequence，连续结果",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                load_entries_from_json(entries_path),
                [
                    {
                        "index": 1,
                        "word": "consequence",
                        "us_phonetic": "/ˈkɑːnsəkwens/",
                        "meaning": "n. 结果；后果",
                        "mnemonic": "con- + sequence，连续结果",
                    }
                ],
            )

    def test_load_entries_from_json_accepts_multiword_entries(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            entries_path = Path(tmpdir) / "entries.json"
            entries_path.write_text(
                json.dumps(
                    {
                        "source_words": ["air conditioner"],
                        "entries": [
                            {
                                "word": "air conditioner",
                                "us_phonetic": "/ˈer kənˌdɪʃənər/",
                                "meaning": "n. 空调",
                                "mnemonic": "air + conditioner，调节空气的设备",
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                load_entries_from_json(entries_path),
                [
                    {
                        "index": 1,
                        "word": "air conditioner",
                        "us_phonetic": "/ˈer kənˌdɪʃənər/",
                        "meaning": "n. 空调",
                        "mnemonic": "air + conditioner，调节空气的设备",
                    }
                ],
            )

    def test_load_entries_from_json_rejects_mismatched_source_words(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            entries_path = Path(tmpdir) / "entries.json"
            entries_path.write_text(
                json.dumps(
                    {
                        "source_words": ["tifle"],
                        "entries": [{"word": "title", "meaning": "标题"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "source_words 不一致"):
                load_entries_from_json(entries_path)

    def test_load_entries_from_json_requires_source_words_object_shape(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            entries_path = Path(tmpdir) / "entries.json"
            entries_path.write_text(
                json.dumps([{"word": "title", "meaning": "标题"}], ensure_ascii=False),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(RuntimeError, "source_words"):
                load_entries_from_json(entries_path)

    def test_load_entries_from_json_treats_null_fields_as_empty_strings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            entries_path = Path(tmpdir) / "entries.json"
            entries_path.write_text(
                json.dumps(
                    {
                        "source_words": ["title"],
                        "entries": [{"word": "title", "meaning": None}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                load_entries_from_json(entries_path),
                [
                    {
                        "index": 1,
                        "word": "title",
                        "us_phonetic": "",
                        "meaning": "",
                        "mnemonic": "",
                    }
                ],
            )

    def test_columns_include_note_column(self):
        self.assertEqual(
            ALL_COLUMNS,
            [
                "序号",
                "单词",
                "音标(美)",
                "释义",
                "助记",
                "笔记",
                "D0",
                "D1",
                "D2",
                "D4",
                "D7",
                "D15",
                "D30",
            ],
        )

    def test_main_generates_pdf_only_by_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            words_path = Path(tmpdir) / "words.txt"
            out_dir = Path(tmpdir) / "out"
            words_path.write_text("bypass\n", encoding="utf-8")

            with (
                patch.object(vocab_sheet, "write_pdf") as write_pdf,
                patch.object(vocab_sheet, "write_xlsx") as write_xlsx,
            ):
                exit_code = vocab_sheet.main(
                    [str(words_path), "--date", "2026-06-03", "--out-dir", str(out_dir)]
                )

            self.assertEqual(exit_code, 0)
            write_pdf.assert_called_once()
            write_xlsx.assert_not_called()

    def test_main_generates_xlsx_when_requested(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            words_path = Path(tmpdir) / "words.txt"
            out_dir = Path(tmpdir) / "out"
            words_path.write_text("bypass\n", encoding="utf-8")

            with (
                patch.object(vocab_sheet, "write_pdf") as write_pdf,
                patch.object(vocab_sheet, "write_xlsx") as write_xlsx,
            ):
                exit_code = vocab_sheet.main(
                    [
                        str(words_path),
                        "--xlsx",
                        "--date",
                        "2026-06-03",
                        "--out-dir",
                        str(out_dir),
                    ]
                )

            self.assertEqual(exit_code, 0)
            write_pdf.assert_called_once()
            write_xlsx.assert_called_once()

    def test_main_uses_entries_json_without_openai_key(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            entries_path = Path(tmpdir) / "entries.json"
            out_dir = Path(tmpdir) / "out"
            entries_path.write_text(
                json.dumps(
                    {
                        "source_words": ["bypass"],
                        "entries": [{"word": "bypass", "meaning": "v. 绕过"}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            with patch.object(vocab_sheet, "write_pdf") as write_pdf:
                exit_code = vocab_sheet.main(
                    [
                        "--entries-json",
                        str(entries_path),
                        "--date",
                        "2026-06-03",
                        "--out-dir",
                        str(out_dir),
                    ]
                )

            self.assertEqual(exit_code, 0)
            write_pdf.assert_called_once()

    def test_main_reads_entries_json_from_stdin(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_dir = Path(tmpdir) / "out"
            stdin = io.StringIO(
                json.dumps(
                    {
                        "source_words": ["bypass"],
                        "entries": [{"word": "bypass", "meaning": "v. 绕过"}],
                    },
                    ensure_ascii=False,
                )
            )

            with (
                patch.object(vocab_sheet.sys, "stdin", stdin),
                patch.object(vocab_sheet, "write_pdf") as write_pdf,
            ):
                exit_code = vocab_sheet.main(
                    [
                        "--entries-json",
                        "-",
                        "--date",
                        "2026-06-03",
                        "--out-dir",
                        str(out_dir),
                    ]
                )

            self.assertEqual(exit_code, 0)
            write_pdf.assert_called_once()

    def test_help_includes_usage_examples(self):
        stdout = io.StringIO()
        stderr = io.StringIO()

        with self.assertRaises(SystemExit) as exc_info:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                vocab_sheet.main(["--help"])

        self.assertEqual(exc_info.exception.code, 0)
        help_text = stdout.getvalue()
        self.assertIn("uv run scripts/vocab_sheet.py examples/words.txt", help_text)
        self.assertIn("--entries-json - --xlsx", help_text)

    def test_main_outputs_json_when_requested(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            words_path = Path(tmpdir) / "words.txt"
            out_dir = Path(tmpdir) / "out"
            stdout = io.StringIO()
            words_path.write_text("bypass\n", encoding="utf-8")

            with (
                patch.object(vocab_sheet, "write_pdf") as write_pdf,
                patch.object(vocab_sheet, "write_xlsx") as write_xlsx,
                contextlib.redirect_stdout(stdout),
            ):
                exit_code = vocab_sheet.main(
                    [
                        str(words_path),
                        "--xlsx",
                        "--json",
                        "--date",
                        "2026-06-03",
                        "--out-dir",
                        str(out_dir),
                    ]
                )

            self.assertEqual(exit_code, 0)
            write_pdf.assert_called_once()
            write_xlsx.assert_called_once()
            payload = json.loads(stdout.getvalue())
            self.assertEqual(
                payload,
                {
                    "ok": True,
                    "pdf_path": str(out_dir / "2026-06-03-vocab.pdf"),
                    "xlsx_path": str(out_dir / "2026-06-03-vocab.xlsx"),
                    "entry_count": 1,
                },
            )


if __name__ == "__main__":
    unittest.main()
