import json
import os
import subprocess
import sys
from pathlib import Path


def test_list_versions_cli_outputs_versions(sample_words_db: Path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "word_extractor",
            "list-versions",
            "--db-path",
            str(sample_words_db),
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )

    lines = result.stdout.splitlines()
    assert lines == [
        "2026: words=29 label=2026考研大纲 *",
        "2027: words=8 label=2027考研大纲",
    ]


def test_set_default_version_cli_switches_default(sample_words_db: Path):
    subprocess.run(
        [
            sys.executable,
            "-m",
            "word_extractor",
            "set-default-version",
            "--db-path",
            str(sample_words_db),
            "--version",
            "2027",
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )

    result = subprocess.run(
        [
            sys.executable,
            "skills/neep-vocab/scripts/neep_vocab.py",
            "lookup",
            "--json",
            "--db-path",
            str(sample_words_db),
            "adaptive",
        ],
        cwd=Path.cwd(),
        env={**os.environ},
        capture_output=True,
        text=True,
        check=True,
    )

    response = json.loads(result.stdout)
    assert response["ok"] is True
    assert response["data"]["version"] == "2027"
    assert response["data"]["version_source"] == "db_default"
    assert response["data"]["results"][0]["found"] is True
