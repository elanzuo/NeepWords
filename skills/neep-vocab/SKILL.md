---
name: neep-vocab
description: Query the local NEEP postgraduate exam vocabulary SQLite lexicon for this repository without using MCP. Use when the user asks whether one or more English words are 考研词汇, wants direct lookup/search/random sampling from the stored word list, or needs local evidence such as norm, IPA, source, frequency, or timestamps from the SQLite database.
---

# NEEP Vocab

Use the bundled CLI instead of reimplementing SQL.

Run it from the repository root:

```bash
uv run python skills/neep-vocab/scripts/neep_vocab.py lookup --json abandon derive inevitable
uv run python skills/neep-vocab/scripts/neep_vocab.py search --json --mode prefix trans
uv run python skills/neep-vocab/scripts/neep_vocab.py random --json --count 5 --min-frequency 2
```

Prefer `--json` for agent use. Parse the JSON and summarize only what the command returns.

## Command selection

- Use `lookup` for membership checks on one or more words.
- Use `search` for `prefix`, `suffix`, `contains`, `fuzzy`, or `wildcard` matching.
- Use `random` for drills, quizzes, or sample vocabulary lists.

## Database path

The CLI resolves the database in this order:

1. `--db-path`
2. `NEEP_WORDS_DB_PATH`
3. `NEEP_WORDS_DB`
4. `resources/data/words.sqlite3`

If the user is asking about the repository's checked-in lexicon, use the default resolution.
If the user is asking about freshly extracted output from the pipeline, pass `--db-path output/words.sqlite3`.

## Response rules

- Report `found` or `not found` exactly as returned for `lookup`.
- Include `word`, `norm`, `ipa`, `source`, `frequency`, `created_at`, and `updated_at` only when they are present and useful to the request.
- Mention any returned `warnings` when they affect interpretation, such as input normalization.
- Do not infer that a word is in the exam syllabus unless the local database lookup says it is.
- For `search`, state the mode and list matched words tersely.
- For `random`, present the sampled words and relevant metadata without implying ranking or completeness.

## Input handling

- `lookup` supports `--match auto|word|norm`. Use `auto` unless the user explicitly wants strict `word` or `norm` matching.
- Non-wildcard input is normalized to the longest English token and lowercased before querying.
- Wildcard search accepts letters plus `-`, `%`, and `_`.
- Invalid input, missing database files, and SQLite errors are returned as machine-readable JSON errors on stderr. Treat these as command failures rather than empty results.
