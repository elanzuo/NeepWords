import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from neep_mcp.lexicon import WordsLexicon

DB_PATH = Path("resources/data/words.sqlite3")


@pytest.fixture
def lexicon() -> WordsLexicon:
    return WordsLexicon(DB_PATH)


def test_lookup_words_returns_found_and_not_found(lexicon: WordsLexicon):
    payload, warnings = lexicon.lookup_words(["abandon", "zxqjz_qwerty"])

    assert "multiple_tokens_found_using_longest" in warnings
    found = next(item for item in payload["results"] if item["input"] == "abandon")
    missing = next(item for item in payload["results"] if item["input"] == "zxqjz_qwerty")

    assert found["found"] is True
    assert found["word"].lower() == "abandon"
    assert missing["found"] is False
    assert missing["query"] == "qwerty"


def test_search_words_contains_contract(lexicon: WordsLexicon):
    payload, warnings = lexicon.search_words("vert", mode="contains", limit=20, offset=0)

    assert warnings == []
    assert payload["mode"] == "contains"
    assert payload["limit"] == 20
    assert payload["offset"] == 0
    assert payload["results"]
    assert all("vert" in item["word"].lower() for item in payload["results"])


def test_skill_query_script_json_output():
    env = {**os.environ, "NEEP_WORDS_DB_PATH": str(DB_PATH)}
    result = subprocess.run(
        [
            sys.executable,
            "skills/neep-vocab/scripts/neep_vocab.py",
            "lookup",
            "--json",
            "abandon",
            "zxqjz_qwerty",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    response = json.loads(result.stdout)
    assert response["ok"] is True
    assert len(response["data"]["results"]) == 2
    assert response["data"]["results"][0]["found"] is True
    assert response["data"]["results"][1]["found"] is False


def test_skill_search_script_json_output():
    env = {**os.environ, "NEEP_WORDS_DB_PATH": str(DB_PATH)}
    result = subprocess.run(
        [
            sys.executable,
            "skills/neep-vocab/scripts/neep_vocab.py",
            "search",
            "--json",
            "--mode",
            "contains",
            "vert",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    response = json.loads(result.stdout)
    assert response["ok"] is True
    assert response["data"]["mode"] == "contains"
    assert response["data"]["results"]
    assert all("vert" in row["word"].lower() for row in response["data"]["results"])


def test_skill_random_script_json_output():
    env = {**os.environ, "NEEP_WORDS_DB_PATH": str(DB_PATH)}
    result = subprocess.run(
        [
            sys.executable,
            "skills/neep-vocab/scripts/neep_vocab.py",
            "random",
            "--json",
            "--count",
            "3",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    response = json.loads(result.stdout)
    assert response["ok"] is True
    assert response["data"]["count"] == 3
    assert len(response["data"]["results"]) == 3
