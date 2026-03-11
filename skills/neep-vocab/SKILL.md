---
name: neep-vocab
description: >
  Local lookup and explicit default-version management for this repository's
  NEEP vocabulary SQLite lexicon without MCP. Use when checking whether English
  words exist in the stored word list, searching matching words, listing
  available/default versions, or changing the database default version only
  when the user explicitly asks. Do not use for PDF/OCR extraction or serving
  external queries through MCP. Inputs: English words, search patterns, or a
  target version, with optional version and database path overrides. Outputs:
  deterministic JSON from the bundled CLI with command, ok, data, warnings, and
  structured errors. Preconditions: run from this repository with uv available
  and a readable SQLite words database; changing the default version requires a
  writable database and persists state.
---

# NEEP Vocab

Use the bundled CLI instead of reimplementing SQL.

## Scope

Use it for:

- Membership checks for one or more English words
- Search queries (`prefix`, `suffix`, `contains`, `fuzzy`, `wildcard`)
- Inspecting which versions exist and which version is currently the DB default
- Changing the DB default version, but only when the user explicitly asks to affect future queries that omit `--version`

Do not use it for:

- Extracting words from PDF pages or OCR pipelines
- Starting an MCP server for external clients

## Commands

Run commands from the repository root:

```bash
uv run python skills/neep-vocab/scripts/neep_vocab.py lookup --json abandon derive inevitable
uv run python skills/neep-vocab/scripts/neep_vocab.py search --json --mode prefix trans
uv run python skills/neep-vocab/scripts/neep_vocab.py lookup --json --version 2027 adaptive
uv run python skills/neep-vocab/scripts/neep_vocab.py list-versions --json
uv run python skills/neep-vocab/scripts/neep_vocab.py set-default-version --json --version 2027
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
3. `neep.toml` -> `[words].db_path`
4. `output/words.sqlite3`
5. `resources/examples/words.sqlite3`

By default, query commands prefer the user's extracted working database in `output/words.sqlite3`.
If that file does not exist, they fall back to the repository's read-only seed database in `resources/examples/words.sqlite3`.
If the user is asking about a non-default extraction target, pass `--db-path` explicitly.

## Version Selection

The CLI resolves the query version in this order:

1. `--version`
2. `NEEP_WORDS_VERSION`
3. `neep.toml` -> `[words].default_version`
4. Database default version
5. The only version in the database

When the user explicitly asks for "27 考研" or similar, pass `--version 2027`.
If the user does not specify a version, rely on the resolution order above and report the resolved version when it matters.
If the user explicitly asks to change the database default version, use `set-default-version` instead of suggesting env/config overrides.

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
- `set-default-version` requires `--version` and targets the writable database default.
- Non-wildcard input is normalized to the longest English token and lowercased before querying.
- Wildcard search accepts letters plus `-`, `%`, and `_`.
- `lookup` can return mixed per-item statuses in one successful response.
- Invalid query arguments, missing database files, and SQLite failures are returned as structured JSON errors on stderr.

## Dependencies And Side Effects

- Requires `uv` and the project Python environment
- Requires running from this repository so relative defaults resolve correctly
- Reads `NEEP_WORDS_DB_PATH`, `NEEP_WORDS_VERSION`, and optional `neep.toml`
- Lookup/search/list commands read SQLite state only
- `set-default-version` writes to the target SQLite database and persists the new default version

## Boundary Examples

Do not trigger this skill for:

- "从 PDF 第 50 页提取考研词汇"
- "帮我启动一个 MCP 服务供别的客户端查询"
- The query is only about OCR processing, PDF rendering, or MCP configuration rather than local lexicon access
