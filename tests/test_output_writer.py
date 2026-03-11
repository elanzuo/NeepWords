import sqlite3

from word_extractor.output import add_words_to_db, export_words_to_csv, write_outputs


def test_write_outputs_with_strings(tmp_path):
    stats = write_outputs(["alpha", "beta", "alpha"], tmp_path, version="2026", spellcheck=False)
    db_path = tmp_path / "words.sqlite3"

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT vv.version_key, w.word
            FROM words AS w
            JOIN vocab_versions AS vv ON vv.id = w.version_id
            ORDER BY vv.version_key, w.word
            """
        ).fetchall()
        columns = conn.execute("PRAGMA table_info(words)").fetchall()
        version_columns = conn.execute("PRAGMA table_info(vocab_versions)").fetchall()

    assert rows == [("2026", "alpha"), ("2026", "beta")]
    assert [column[1] for column in columns] == ["id", "version_id", "word", "source", "added_at"]
    assert [column[1] for column in version_columns] == [
        "id",
        "version_key",
        "label",
        "source_pdf",
        "imported_at",
        "is_default",
    ]
    assert stats["total_count"] == 3
    assert stats["unique_count"] == 2
    assert stats["duplicate_count"] == 1
    assert stats["per_page_counts"] == {}
    assert stats["version"] == "2026"


def test_write_outputs_with_metadata(tmp_path):
    words = [
        {"word": "alpha", "page": 1, "column": "L", "line": 1, "source": "p1L1"},
        {"word": "beta", "page": 1, "column": "R", "line": 2, "source": "p1R2"},
        {"word": "gamma", "page": 2, "column": "L", "line": 1, "source": "p2L1"},
    ]
    stats = write_outputs(words, tmp_path, version="2027", spellcheck=False)
    db_path = tmp_path / "words.sqlite3"

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT vv.version_key, w.word, w.source, w.added_at
            FROM words AS w
            JOIN vocab_versions AS vv ON vv.id = w.version_id
            ORDER BY w.word
            """
        ).fetchall()

    assert [(row[0], row[1], row[2]) for row in rows] == [
        ("2027", "alpha", "p1L1"),
        ("2027", "beta", "p1R2"),
        ("2027", "gamma", "p2L1"),
    ]
    assert all(row[3] for row in rows)
    assert stats["per_page_counts"] == {1: 2, 2: 1}
    assert stats["version"] == "2027"


def test_add_words_to_db_migrates_legacy_schema_when_legacy_version_is_provided(tmp_path):
    db_path = tmp_path / "words.sqlite3"

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE words (
                id INTEGER PRIMARY KEY,
                word TEXT NOT NULL UNIQUE,
                source TEXT,
                added_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            )
            """
        )
        conn.execute("INSERT INTO words (word, source) VALUES ('alpha', 'legacy-a')")
        conn.execute("INSERT INTO words (word, source) VALUES ('beta', 'legacy-b')")

    stats = add_words_to_db(
        ["gamma"],
        db_path=db_path,
        version="2027",
        legacy_version="2026",
    )

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT vv.version_key, w.word, w.source
            FROM words AS w
            JOIN vocab_versions AS vv ON vv.id = w.version_id
            ORDER BY vv.version_key, w.word
            """
        ).fetchall()

    assert rows == [
        ("2026", "alpha", "legacy-a"),
        ("2026", "beta", "legacy-b"),
        ("2027", "gamma", None),
    ]
    assert stats["version"] == "2027"


def test_export_words_to_csv_filters_by_version(tmp_path):
    db_path = tmp_path / "words.sqlite3"
    csv_path = tmp_path / "words.csv"

    add_words_to_db(["alpha", "beta"], db_path=db_path, version="2026")
    add_words_to_db(["beta", "gamma"], db_path=db_path, version="2027")

    stats = export_words_to_csv(
        db_path,
        csv_path,
        ["version", "word"],
        version="2027",
    )

    assert stats["row_count"] == 2
    assert stats["version"] == "2027"
    assert csv_path.read_text(encoding="utf-8").splitlines() == [
        "version,word",
        "2027,beta",
        "2027,gamma",
    ]
