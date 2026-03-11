import sqlite3

from word_extractor.output import write_outputs


def test_write_outputs_with_strings(tmp_path):
    stats = write_outputs(["alpha", "beta", "alpha"], tmp_path)
    db_path = tmp_path / "words.sqlite3"

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT word FROM words ORDER BY word").fetchall()
        columns = conn.execute("PRAGMA table_info(words)").fetchall()

    assert rows == [("alpha",), ("beta",)]
    assert [column[1] for column in columns] == ["id", "word", "source", "added_at"]
    assert stats["total_count"] == 3
    assert stats["unique_count"] == 2
    assert stats["duplicate_count"] == 1
    assert stats["per_page_counts"] == {}


def test_write_outputs_with_metadata(tmp_path):
    words = [
        {"word": "alpha", "page": 1, "column": "L", "line": 1, "source": "p1L1"},
        {"word": "beta", "page": 1, "column": "R", "line": 2, "source": "p1R2"},
        {"word": "gamma", "page": 2, "column": "L", "line": 1, "source": "p2L1"},
    ]
    stats = write_outputs(words, tmp_path)
    db_path = tmp_path / "words.sqlite3"

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT word, source, added_at FROM words ORDER BY word").fetchall()

    assert [(row[0], row[1]) for row in rows] == [
        ("alpha", "p1L1"),
        ("beta", "p1R2"),
        ("gamma", "p2L1"),
    ]
    assert all(row[2] for row in rows)
    assert stats["per_page_counts"] == {1: 2, 2: 1}
