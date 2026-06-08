import json
import os
import subprocess
from pathlib import Path

SKILL_DIR = Path.cwd() / "skills" / "kaoyan-vocab-lookup"


def run_skill_command(
    *args: str, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["uv", "run", "scripts/neep_vocab.py", *args],
        cwd=cwd or SKILL_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


def test_skill_query_script_json_output(sample_words_db: Path):
    env = {**os.environ, "NEEP_WORDS_DB_PATH": str(sample_words_db), "NEEP_WORDS_VERSION": "2027"}
    result = run_skill_command(
        "lookup",
        "--json",
        "adaptive",
        "zxqjz_qwerty",
        env=env,
    )

    assert result.returncode == 0
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
    result = run_skill_command(
        "search",
        "--json",
        "--mode",
        "contains",
        "--version",
        "2027",
        "form",
        env=env,
    )

    assert result.returncode == 0
    response = json.loads(result.stdout)
    assert response["ok"] is True
    assert response["command"] == "search"
    assert response["error"] is None
    assert response["data"]["mode"] == "contains"
    assert response["data"]["version"] == "2027"
    assert response["data"]["results"] == [{"word": "formation"}]


def test_skill_list_versions_script_json_output(sample_words_db: Path):
    env = {**os.environ, "NEEP_WORDS_DB_PATH": str(sample_words_db)}
    result = run_skill_command("list-versions", "--json", env=env)

    assert result.returncode == 0
    response = json.loads(result.stdout)
    assert response["ok"] is True
    assert response["command"] == "list_versions"
    assert response["error"] is None
    assert response["data"]["schema_mode"] == "versioned"
    assert [row["version"] for row in response["data"]["versions"]] == ["2026", "2027"]
    assert response["data"]["versions"][0]["is_default"] is True


def test_skill_set_default_version_script_json_output(sample_words_db: Path):
    env = {**os.environ, "NEEP_WORDS_DB_PATH": str(sample_words_db)}
    result = run_skill_command(
        "set-default-version",
        "--json",
        "--version",
        "2027",
        env=env,
    )

    assert result.returncode == 0
    response = json.loads(result.stdout)
    assert response["ok"] is True
    assert response["command"] == "set_default_version"
    assert response["error"] is None
    assert response["data"]["version"] == "2027"
    assert response["data"]["is_default"] is True

    follow_up = run_skill_command("lookup", "--json", "adaptive", env=env)
    assert follow_up.returncode == 0
    follow_up_response = json.loads(follow_up.stdout)
    assert follow_up_response["data"]["version"] == "2027"
    assert follow_up_response["data"]["version_source"] == "db_default"


def test_skill_lookup_script_reports_invalid_input_as_item_status(sample_words_db: Path):
    env = {**os.environ, "NEEP_WORDS_DB_PATH": str(sample_words_db)}
    result = run_skill_command("lookup", "--json", "中文", env=env)

    assert result.returncode == 0
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
    result = run_skill_command("search", "--json", "--mode", "wildcard", "%%", env=env)

    assert result.returncode == 2
    response = json.loads(result.stderr)
    assert response["ok"] is False
    assert response["command"] == "search"
    assert response["data"] is None
    assert response["warnings"] == []
    assert response["error"]["code"] == "invalid_query"
    assert response["error"]["retryable"] is False
    assert "English letter" in response["error"]["hint"]


def test_skill_reads_bundled_example_db_by_default():
    result = run_skill_command("lookup", "--json", "transition")

    assert result.returncode == 0
    response = json.loads(result.stdout)
    assert response["ok"] is True
    assert response["command"] == "lookup"
    assert response["data"]["results"][0]["found"] is True


def test_skill_requires_explicit_write_db_path():
    env = {key: value for key, value in os.environ.items() if key != "NEEP_WORDS_DB_PATH"}
    result = run_skill_command("set-default-version", "--json", "--version", "2027", env=env)

    assert result.returncode == 2
    response = json.loads(result.stderr)
    assert response["ok"] is False
    assert response["command"] == "set_default_version"
    assert response["error"]["code"] == "db_path_required_for_write"


def test_skill_help_includes_examples():
    result = run_skill_command("--help")

    assert result.returncode == 0
    assert "uv run scripts/neep_vocab.py lookup --json abandon derive inevitable" in result.stdout
    assert "uv run scripts/neep_vocab.py set-default-version --db-path" in result.stdout
