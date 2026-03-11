This directory can contain a checked-in read-only seed database for out-of-the-box lookup.

Preferred file name: `words.sqlite3`

Resolution behavior:

- Query tools prefer `output/words.sqlite3`.
- If no working database exists, query tools fall back to `resources/examples/words.sqlite3`.
- Write and state-changing commands do not fall back to this directory by default.

Distribution notes:

- The example database is intended for product demos, local testing, and documentation examples.
- Do not treat this directory as a place to publish source PDFs, scanned page images, or other copyrighted upstream materials.
- If you replace the example database with a real extracted lexicon, confirm that you have the right to redistribute that data first.
