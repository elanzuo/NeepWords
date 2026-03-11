---
name: neep-vocab
description: Query the local NEEP postgraduate exam vocabulary SQLite lexicon for this repository without using MCP. Use when the user asks whether one or more English words are 考研词汇, wants direct lookup/search from the stored word list, or needs local evidence such as source or timestamps from the SQLite database.
---

# NEEP Vocab

Use the bundled CLI instead of reimplementing SQL.

Run it from the repository root:

```bash
uv run python skills/neep-vocab/scripts/neep_vocab.py lookup --json abandon derive inevitable
uv run python skills/neep-vocab/scripts/neep_vocab.py search --json --mode prefix trans
uv run python skills/neep-vocab/scripts/neep_vocab.py lookup --json --version 2027 adaptive
uv run python skills/neep-vocab/scripts/neep_vocab.py list-versions --json
uv run python skills/neep-vocab/scripts/neep_vocab.py set-default-version --json --version 2027
```

Prefer `--json` for agent use. Parse the JSON and summarize only what the command returns.

## Command selection

- Use `lookup` for membership checks on one or more words.
- Use `search` for `prefix`, `suffix`, `contains`, `fuzzy`, or `wildcard` matching.
- Use `list-versions` to inspect which vocabulary versions exist and which one is the DB default.
- Use `set-default-version` only when the user explicitly asks to change the default version for future unspecified queries.

## Database path

The CLI resolves the database in this order:

1. `--db-path`
2. `NEEP_WORDS_DB_PATH`
3. `NEEP_WORDS_DB`
4. `neep.toml` -> `[words].db_path`
5. `resources/data/words.sqlite3`

If the user is asking about the repository's checked-in lexicon, use the default resolution.
If the user is asking about freshly extracted output from the pipeline, pass `--db-path output/words.sqlite3`.

## Version selection

The CLI resolves the query version in this order:

1. `--version`
2. `NEEP_WORDS_VERSION`
3. `neep.toml` -> `[words].default_version`
4. Database default version
5. The only version in the database

When the user explicitly asks for “27 考研” or similar, pass `--version 2027`.
If the user does not specify a version, rely on the resolution order above and report the resolved version when it matters.
If the user asks to change the database default, use `set-default-version` instead of relying on env/config overrides.

## Response rules

- Report `found` or `not found` exactly as returned for `lookup`.
- Mention `version` when it affects interpretation or when the user asked for a specific year.
- Include `word`, `source`, and `added_at` only when they are present and useful to the request.
- Mention any returned `warnings` when they affect interpretation, such as input normalization.
- Do not infer that a word is in the exam syllabus unless the local database lookup says it is.
- For `search`, state the mode and list matched words tersely.
- For `list-versions`, include which version is default.
- Treat `set-default-version` as a state-changing action and mention that it changes future queries that omit `--version`.

## Input handling

- `lookup` supports `--match auto|word`. Use `auto` unless the user explicitly wants strict `word` matching.
- `lookup/search` both support `--version`.
- `list-versions` and `set-default-version` do not need `--version` for query filtering; `set-default-version --version ...` means the target default.
- Non-wildcard input is normalized to the longest English token and lowercased before querying.
- Wildcard search accepts letters plus `-`, `%`, and `_`.
- Invalid input, missing database files, and SQLite errors are returned as machine-readable JSON errors on stderr. Treat these as command failures rather than empty results.
