---
name: kaoyan-vocab-sheet
description: Generate printable Kaoyan English vocabulary review sheets from pasted word lists or txt/csv files, with AI-filled US phonetics, Chinese meanings, mnemonics, Kaoyan collocations/short examples, and A4 PDF output by default; generate XLSX only when explicitly requested.
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
5. Use the current Codex model, not `OPENAI_API_KEY`, to produce entries JSON with the fixed fields below.
6. Pipe the entries JSON to the local CLI with `--entries-json -`; do not leave an intermediate JSON file unless the user explicitly asks for one.
7. Return the generated PDF path to the user. Only generate and return XLSX when the user explicitly asks for XLSX/Excel.
8. When the result will be consumed by another tool step, prefer `--json` so the output is machine-readable.

Entries JSON shape:

```json
{
  "source_words": ["consequence"],
  "entries": [
    {
      "word": "consequence",
      "us_phonetic": "/ˈkɑːnsəkwens/",
      "meaning": "结果；后果",
      "mnemonic": "con- + sequence，连续结果",
      "usage": "as a consequence of the policy"
    }
  ]
}
```

`entries[*].word` must exactly match `source_words` after normalization. The CLI rejects mismatches to catch silent corrections, missing words, extra words, and reordering.

Content rules:

- `us_phonetic`: US phonetic transcription.
- `meaning`: concise Simplified Chinese, prioritize Kaoyan common meanings.
- `mnemonic`: short mnemonic, root, affix, or association.
- `usage`: one Kaoyan-relevant collocation or very short example, about 8-12 English words.

Examples:

```bash
uv run scripts/vocab_sheet.py --entries-json - <<'JSON'
{
  "source_words": ["consequence"],
  "entries": [
    {
      "word": "consequence",
      "us_phonetic": "/ˈkɑːnsəkwens/",
      "meaning": "结果；后果",
      "mnemonic": "con- + sequence，连续结果",
      "usage": "as a consequence of the policy"
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
      "meaning": "结果；后果",
      "mnemonic": "con- + sequence，连续结果",
      "usage": "as a consequence of the policy"
    }
  ]
}
JSON
```

Generate machine-readable output:

```bash
uv run scripts/vocab_sheet.py --entries-json - --json <<'JSON'
{
  "source_words": ["consequence"],
  "entries": [
    {
      "word": "consequence",
      "us_phonetic": "/ˈkɑːnsəkwens/",
      "meaning": "结果；后果",
      "mnemonic": "con- + sequence，连续结果",
      "usage": "as a consequence of the policy"
    }
  ]
}
JSON
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

If `--xlsx` is passed, this file is also written:

```text
YYYY-MM-DD-vocab.xlsx
```

The table columns are fixed:

```text
序号 | 单词 | 音标(美) | 释义 | 助记 | 考研搭配/短例句 | D0 | D1 | D2 | D4 | D7 | D15 | D30
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
