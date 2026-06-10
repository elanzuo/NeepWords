---
name: kaoyan-vocab-sheet
description: Generate printable Kaoyan English vocabulary review sheets from pasted word lists or txt/csv files, with AI-filled US phonetics, Chinese meanings, mnemonics, and A4 PDF output by default; generate XLSX only when explicitly requested.
---

# Kaoyan Vocab Sheet

Use this when the user wants to turn English vocabulary into printable A4 review sheets.

## Tool Location

Run from the skill directory. Do not call bare Python directly. Always use `uv run`.

Main command:

```bash
uv run scripts/vocab_sheet.py
```

## Available Scripts

- `scripts/vocab_sheet.py` - Parse pasted words, txt/csv files, or entries JSON and generate PDF/XLSX review sheets

## Workflow

1. Read the user's pasted words or txt/csv file.
2. Normalize only separators, numbering, bullets, and bracketed Chinese notes such as `transition（过渡）`.
3. Do not silently correct spelling. If a token looks wrong, for example `tifle` or `demmand`, stop and ask the user whether to keep or correct it. If unsure how to fix an error, ask the user to decide.
4. Deduplicate exact normalized duplicates, and report which duplicates were removed.
5. First run the local CLI on the raw word list with `--dry-run --json` to get the normalized `source_words`, placeholder `entries`, duplicates removed, skipped tokens, and the resolved output paths.
6. Use the current Codex model, not `OPENAI_API_KEY`, to fill the placeholder `entries` fields while keeping `entries[*].word` exactly aligned with `source_words`.
7. Pipe the completed entries JSON to the same CLI with `--entries-json -`; do not leave an intermediate JSON file unless the user explicitly asks for one.
8. Return the generated PDF path to the user. Only generate and return XLSX when the user explicitly asks for XLSX/Excel.

Entries JSON shape:

```json
{
  "source_words": ["consequence"],
  "entries": [
    {
      "word": "consequence",
      "us_phonetic": "/ˈkɑːnsəkwens/",
      "meaning": "n. 结果；后果",
      "mnemonic": "con- + sequence，连续结果"
    }
  ]
}
```

`entries[*].word` must exactly match `source_words` after normalization. The CLI rejects mismatches to catch silent corrections, missing words, extra words, and reordering.

Content rules:

- `us_phonetic`: US phonetic transcription.
- `meaning`: concise Simplified Chinese with one leading part-of-speech tag such as `n.`/`v.`/`adj.`/`adv.`, prioritize Kaoyan common meanings.
- `mnemonic`: short mnemonic, root, affix, or association.

Examples:

```bash
uv run scripts/vocab_sheet.py --entries-json - <<'JSON'
{
  "source_words": ["consequence"],
  "entries": [
    {
      "word": "consequence",
      "us_phonetic": "/ˈkɑːnsəkwens/",
      "meaning": "n. 结果；后果",
      "mnemonic": "con- + sequence，连续结果"
    }
  ]
}
JSON
```

Generate XLSX only when explicitly requested:

```bash
uv run scripts/vocab_sheet.py --entries-json - --xlsx <<'JSON'
{
  "source_words": ["consequence"],
  "entries": [
    {
      "word": "consequence",
      "us_phonetic": "/ˈkɑːnsəkwens/",
      "meaning": "n. 结果；后果",
      "mnemonic": "con- + sequence，连续结果"
    }
  ]
}
JSON
```

Generate machine-readable output from a raw word list:

```bash
uv run scripts/vocab_sheet.py examples/words.txt --dry-run --json
```

For a blank parsing/layout check only:

```bash
uv run scripts/vocab_sheet.py examples/words.txt
```

## Output

Files are written to `output/` by default. PDF is the default output:

```text
YYYY-MM-DD-vocab.pdf
```

If that file already exists, the CLI automatically increments the suffix without overwriting:

```text
YYYY-MM-DD-vocab-2.pdf
YYYY-MM-DD-vocab-3.pdf
```

If `--xlsx` is passed, this file is also written:

```text
YYYY-MM-DD-vocab.xlsx
```

The table columns are fixed:

```text
序号 | 单词 | 音标(美) | 释义 | 助记 | 笔记 | D0 | D1 | D2 | D4 | D7 | D15 | D30
```

## Report

Final response must include:

- generated file path
- processed word count
- skipped tokens, if any
- exact duplicates removed, if any
- spelling changes approved by the user, if any
- unresolved uncertain tokens handed back to the user, if any

## Setup/Repair

Dependency setup is automatic because the script uses inline `uv` metadata.

If the environment is sandboxed and the default cache path is not writable, prefix commands with `UV_CACHE_DIR=/tmp/uv-cache`.

Examples:

```bash
uv run scripts/vocab_sheet.py examples/words.txt
UV_CACHE_DIR=/tmp/uv-cache uv run scripts/vocab_sheet.py examples/words.txt
```

Verify:

```bash
uv run scripts/vocab_sheet.py examples/words.txt
```

## CLI Notes

- Use `--file-stem` to control the output filename prefix. The default is today's date, so the default PDF path is `output/YYYY-MM-DD-vocab.pdf`.
- Existing output files are never overwritten. If the chosen PDF/XLSX name already exists, the CLI increments the filename suffix and returns the resolved path.
- `--json` still generates files unless `--dry-run` is also passed.
- `--dry-run --json` returns machine-readable fields including `source_words`, `entries`, `pdf_path`, `xlsx_path`, `entry_count`, `duplicates_removed`, `skipped_tokens`, and `generated`.
