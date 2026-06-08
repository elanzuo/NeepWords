---
name: kaoyan-vocab-lookup
description: >
  Local lookup and explicit default-version management for a Kaoyan vocabulary
  SQLite lexicon. Use when checking whether English
  words exist in the stored word list, searching matching words, listing
  available/default versions, or changing the database default version only
  when the user explicitly asks. Do not use for PDF/OCR extraction. Inputs: English words, search patterns, or a
  target version, with optional version and database path overrides. Outputs:
  deterministic JSON from the bundled CLI with command, ok, data, warnings, and
  structured errors. Preconditions: run from the skill directory with uv
  available and a readable SQLite words database; changing the default version
  requires a writable versioned database and persists state.
---

# Kaoyan Vocab DB

Use the bundled CLI instead of reimplementing SQL.

## Tool Location

Run from the skill directory. Do not call bare Python directly. Always use `uv run`.

Main command:

```bash
uv run scripts/neep_vocab.py
```

## Available Scripts

- `scripts/neep_vocab.py` - Query a Kaoyan vocabulary SQLite database and manage the explicit default version

## Scope

Use it for:

- Membership checks for one or more English words
- Search queries (`prefix`, `suffix`, `contains`, `fuzzy`, `wildcard`)
- Inspecting which versions exist and which version is currently the DB default
- Changing the DB default version, but only when the user explicitly asks to affect future queries that omit `--version`

Do not use it for:

- Extracting words from PDF pages or OCR pipelines

## Commands

Run commands from the skill directory:

```bash
uv run scripts/neep_vocab.py lookup --json abandon derive inevitable
uv run scripts/neep_vocab.py search --json --mode prefix trans
uv run scripts/neep_vocab.py lookup --json --version 2027 adaptive
uv run scripts/neep_vocab.py list-versions --json
uv run scripts/neep_vocab.py set-default-version --db-path /path/to/words.sqlite3 --json --version 2027
```

Prefer `--json` for agent use. Parse the JSON and summarize only what the command returns.

## Command Selection

- Use `lookup` for membership checks on one or more words.
- Use `search` for `prefix`, `suffix`, `contains`, `fuzzy`, or `wildcard` matching.
- Use `list-versions` to inspect which vocabulary versions exist and which one is the DB default.
- Use `set-default-version` only when the user explicitly asks to change the default used by later queries that omit `--version`.

## Database Path

The CLI resolves the database in this order:

1. `--db-path`
2. `NEEP_WORDS_DB_PATH`
3. `examples/words.sqlite3` (read commands only)

By default, `lookup`, `search`, and `list-versions` fall back to the skill's bundled read-only example database.
`set-default-version` does not use the example database implicitly; it requires `--db-path` or `NEEP_WORDS_DB_PATH`.
If the user is asking about a non-default target, pass `--db-path` explicitly.

## Version Selection

The CLI resolves the query version in this order:

1. `--version`
2. `NEEP_WORDS_VERSION`
3. Database default version
4. The only version in the database

When the user explicitly asks for "27 考研" or similar, pass `--version 2027`.
If the user does not specify a version, rely on the resolution order above and report the resolved version when it matters.
If the user explicitly asks to change the database default version, use `set-default-version` instead of suggesting config overrides.

## Response Rules

- Expect a stable JSON envelope: `command`, `ok`, `data`, `warnings`, `error`.
- Report `found`, `not_found`, or `invalid_input` exactly as returned for each `lookup` item.
- Mention `version` when it affects interpretation or when the user asked for a specific year.
- Include `word`, `source`, and `added_at` only when they are present and useful to the request.
- Mention any returned `warnings` when they affect interpretation, such as input normalization.
- Do not infer that a word is in the exam syllabus unless the local database lookup says it is.
- For `search`, state the mode and list matched words tersely.
- For `list-versions`, include which version is default.
- For `set-default-version`, confirm the returned `version` and that later unspecified queries will use that default.
- Treat `ok: false` as a command failure. Read the structured `error` object and adjust the command only when the hint shows a safe correction.

## Input Handling

- `lookup` supports `--match auto|word`. Use `auto` unless the user explicitly wants strict `word` matching.
- `lookup/search` both support `--version`.
- `list-versions` does not use `--version`.
- `set-default-version` requires `--version` and a writable versioned database path.
- Non-wildcard input is normalized to the longest English token and lowercased before querying.
- Wildcard search accepts letters plus `-`, `%`, and `_`.
- `lookup` can return mixed per-item statuses in one successful response.
- Invalid query arguments, missing database files, and SQLite failures are returned as structured JSON errors on stderr.

## Dependencies And Side Effects

- Requires `uv`
- Reads `NEEP_WORDS_DB_PATH` and `NEEP_WORDS_VERSION`
- `lookup/search/list-versions` read SQLite state only
- `set-default-version` writes to the target SQLite database and persists the new default version

## Setup/Repair

Dependency setup is automatic because the script uses inline `uv` metadata.

If the environment is sandboxed and the default cache path is not writable, prefix commands with `UV_CACHE_DIR=/tmp/uv-cache`.

Examples:

```bash
uv run scripts/neep_vocab.py list-versions --json
UV_CACHE_DIR=/tmp/uv-cache uv run scripts/neep_vocab.py lookup --json transition
```

## Boundary Examples

Do not trigger this skill for:

- "从 PDF 第 50 页提取考研词汇"
- The query is only about OCR processing or PDF rendering rather than local lexicon access
