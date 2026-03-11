import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from neep_mcp.lexicon import WordsLexicon, build_lexicon


@pytest.fixture
def lexicon(sample_words_db: Path) -> WordsLexicon:
    return WordsLexicon(sample_words_db)


def test_lookup_words_uses_db_default_version(lexicon: WordsLexicon):
    payload, warnings = lexicon.lookup_words(["abandon", "zxqjz_qwerty"])

    assert "multiple_tokens_found_using_longest" in warnings
    assert payload["version"] == "2026"
    assert payload["version_source"] == "db_default"

    found = next(item for item in payload["results"] if item["input"] == "abandon")
    missing = next(item for item in payload["results"] if item["input"] == "zxqjz_qwerty")

    assert found["found"] is True
    assert found["word"].lower() == "abandon"
    assert found["version"] == "2026"
    assert missing["found"] is False
    assert missing["query"] == "qwerty"
    assert missing["version"] == "2026"


def test_search_words_supports_explicit_version(lexicon: WordsLexicon):
    payload, warnings = lexicon.search_words(
        "form",
        mode="contains",
        limit=20,
        offset=0,
        version="2027",
    )

    assert warnings == []
    assert payload["mode"] == "contains"
    assert payload["limit"] == 20
    assert payload["offset"] == 0
    assert payload["version"] == "2027"
    assert payload["version_source"] == "explicit"
    assert payload["results"]
    assert all("form" in item["word"].lower() for item in payload["results"])
    assert {item["word"] for item in payload["results"]} == {"formation"}


def test_build_lexicon_uses_env_default_version(
    sample_words_db: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("NEEP_WORDS_DB_PATH", os.fspath(sample_words_db))
    monkeypatch.setenv("NEEP_WORDS_VERSION", "27考研")

    lexicon = build_lexicon(start=Path.cwd())
    payload, warnings = lexicon.lookup_words(["adaptive"])

    assert warnings == []
    assert payload["version"] == "2027"
    assert payload["version_source"] == "configured"
    assert payload["results"][0]["found"] is True


def test_skill_query_script_json_output(sample_words_db: Path):
    env = {**os.environ, "NEEP_WORDS_DB_PATH": str(sample_words_db), "NEEP_WORDS_VERSION": "2027"}
    result = subprocess.run(
        [
            sys.executable,
            "skills/neep-vocab/scripts/neep_vocab.py",
            "lookup",
            "--json",
            "adaptive",
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
    assert response["command"] == "lookup"
    assert response["error"] is None
    assert response["data"]["version"] == "2027"
    assert len(response["data"]["results"]) == 2
    assert response["data"]["results"][0]["found"] is True
    assert response["data"]["results"][0]["status"] == "found"
    assert response["data"]["results"][1]["found"] is False
    assert response["data"]["results"][1]["status"] == "not_found"


def test_skill_search_script_json_output(sample_words_db: Path):
    env = {**os.environ, "NEEP_WORDS_DB_PATH": str(sample_words_db)}
    result = subprocess.run(
        [
            sys.executable,
            "skills/neep-vocab/scripts/neep_vocab.py",
            "search",
            "--json",
            "--mode",
            "contains",
            "--version",
            "2027",
            "form",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    response = json.loads(result.stdout)
    assert response["ok"] is True
    assert response["command"] == "search"
    assert response["error"] is None
    assert response["data"]["mode"] == "contains"
    assert response["data"]["version"] == "2027"
    assert response["data"]["results"] == [{"word": "formation"}]


def test_skill_list_versions_script_json_output(sample_words_db: Path):
    env = {**os.environ, "NEEP_WORDS_DB_PATH": str(sample_words_db)}
    result = subprocess.run(
        [
            sys.executable,
            "skills/neep-vocab/scripts/neep_vocab.py",
            "list-versions",
            "--json",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    response = json.loads(result.stdout)
    assert response["ok"] is True
    assert response["command"] == "list_versions"
    assert response["error"] is None
    assert response["data"]["schema_mode"] == "versioned"
    assert [row["version"] for row in response["data"]["versions"]] == ["2026", "2027"]
    assert response["data"]["versions"][0]["is_default"] is True


def test_skill_set_default_version_script_json_output(sample_words_db: Path):
    env = {**os.environ, "NEEP_WORDS_DB_PATH": str(sample_words_db)}
    result = subprocess.run(
        [
            sys.executable,
            "skills/neep-vocab/scripts/neep_vocab.py",
            "set-default-version",
            "--json",
            "--version",
            "2027",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    response = json.loads(result.stdout)
    assert response["ok"] is True
    assert response["command"] == "set_default_version"
    assert response["error"] is None
    assert response["data"]["version"] == "2027"
    assert response["data"]["is_default"] is True

    follow_up = subprocess.run(
        [
            sys.executable,
            "skills/neep-vocab/scripts/neep_vocab.py",
            "lookup",
            "--json",
            "adaptive",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    follow_up_response = json.loads(follow_up.stdout)
    assert follow_up_response["data"]["version"] == "2027"
    assert follow_up_response["data"]["version_source"] == "db_default"


def test_skill_lookup_script_reports_invalid_input_as_item_status(sample_words_db: Path):
    env = {**os.environ, "NEEP_WORDS_DB_PATH": str(sample_words_db)}
    result = subprocess.run(
        [
            sys.executable,
            "skills/neep-vocab/scripts/neep_vocab.py",
            "lookup",
            "--json",
            "中文",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    response = json.loads(result.stdout)
    assert response["ok"] is True
    assert response["command"] == "lookup"
    assert response["error"] is None
    assert response["warnings"] == ["no_english_tokens"]
    assert response["data"]["results"] == [
        {
            "input": "中文",
            "found": False,
            "error": "invalid_input",
            "status": "invalid_input",
        }
    ]


def test_skill_search_script_reports_structured_error(sample_words_db: Path):
    env = {**os.environ, "NEEP_WORDS_DB_PATH": str(sample_words_db)}
    result = subprocess.run(
        [
            sys.executable,
            "skills/neep-vocab/scripts/neep_vocab.py",
            "search",
            "--json",
            "--mode",
            "wildcard",
            "%%",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    response = json.loads(result.stderr)
    assert response["ok"] is False
    assert response["command"] == "search"
    assert response["data"] is None
    assert response["warnings"] == []
    assert response["error"]["code"] == "invalid_query"
    assert response["error"]["retryable"] is False
    assert "English letter" in response["error"]["hint"]
