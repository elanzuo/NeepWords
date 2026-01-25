import sqlite3

from neepwordextractor.output import write_outputs


def test_write_outputs_with_strings(tmp_path):
    stats = write_outputs(["alpha", "beta", "alpha"], tmp_path)
    db_path = tmp_path / "words.sqlite3"

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT word, norm, frequency FROM words ORDER BY norm").fetchall()

    assert rows == [("alpha", "alpha", 2), ("beta", "beta", 1)]
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
        rows = conn.execute(
            "SELECT word, norm, source, frequency FROM words ORDER BY norm"
        ).fetchall()

    assert rows == [
        ("alpha", "alpha", "p1L1", 1),
        ("beta", "beta", "p1R2", 1),
        ("gamma", "gamma", "p2L1", 1),
    ]
    assert stats["per_page_counts"] == {1: 2, 2: 1}
