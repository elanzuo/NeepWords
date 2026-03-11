This directory can contain a checked-in read-only seed database for out-of-the-box lookup.

Preferred file name: `words.sqlite3`

Resolution behavior:

- Query tools prefer `output/words.sqlite3`.
- If no working database exists, query tools fall back to `resources/examples/words.sqlite3`.
- Write and state-changing commands do not fall back to this directory by default.
