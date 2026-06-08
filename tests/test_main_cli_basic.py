import subprocess
import sys
from pathlib import Path


def test_main_cli_help_lists_only_basic_subcommands():
    result = subprocess.run(
        [sys.executable, "-m", "word_extractor", "--help"],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )

    assert "add-words" in result.stdout
    assert "export-csv" in result.stdout
    assert "migrate-db" not in result.stdout
    assert "list-versions" not in result.stdout
    assert "set-default-version" not in result.stdout


def test_main_cli_add_words_subcommand_still_works(sample_words_db: Path):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "word_extractor",
            "add-words",
            "--db-path",
            str(sample_words_db),
            "--version",
            "2027",
            "--entry",
            "newword:test-source",
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Added 1 word(s) into version 2027" in result.stdout


def test_main_cli_export_csv_subcommand_still_works(sample_words_db: Path, tmp_path: Path):
    csv_path = tmp_path / "export.csv"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "word_extractor",
            "export-csv",
            "--db-path",
            str(sample_words_db),
            "--csv-path",
            str(csv_path),
            "--columns",
            "version,word",
            "--version",
            "2027",
        ],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=True,
    )

    assert "Exported" in result.stdout
    assert csv_path.exists()
