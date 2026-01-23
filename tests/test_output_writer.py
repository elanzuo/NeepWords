from neepwordextractor.output import write_outputs


def test_write_outputs_with_strings(tmp_path):
    stats = write_outputs(["alpha", "beta", "alpha"], tmp_path)
    txt = (tmp_path / "words.txt").read_text(encoding="utf-8").splitlines()
    json_text = (tmp_path / "words.json").read_text(encoding="utf-8")

    assert txt == ["alpha", "beta", "alpha"]
    assert '"word": "alpha"' in json_text
    assert stats["total_count"] == 3
    assert stats["unique_count"] == 2
    assert stats["duplicate_count"] == 1
    assert stats["per_page_counts"] == {}


def test_write_outputs_with_metadata(tmp_path):
    words = [
        {"word": "alpha", "page": 1, "column": "L", "line": 1},
        {"word": "beta", "page": 1, "column": "R", "line": 2},
        {"word": "gamma", "page": 2, "column": "L", "line": 1},
    ]
    stats = write_outputs(words, tmp_path)
    txt = (tmp_path / "words.txt").read_text(encoding="utf-8").splitlines()

    assert txt == ["alpha", "beta", "gamma"]
    assert stats["per_page_counts"] == {1: 2, 2: 1}
