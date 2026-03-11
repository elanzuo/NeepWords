from pathlib import Path

from word_extractor.output import add_words_to_db
from word_extractor.storage import (
    DEFAULT_EXAMPLE_DB_PATH,
    DEFAULT_RUNTIME_DB_PATH,
    resolve_db_path,
    resolve_writable_db_path,
)


def _seed_db(path: Path, *, version: str = "2027") -> None:
    add_words_to_db(["adaptive"], db_path=path, version=version)


def test_resolve_db_path_prefers_runtime_output_db(tmp_path: Path):
    runtime_db = (tmp_path / DEFAULT_RUNTIME_DB_PATH).resolve()
    example_db = (tmp_path / DEFAULT_EXAMPLE_DB_PATH).resolve()
    _seed_db(runtime_db, version="2027")
    _seed_db(example_db, version="2026")

    assert resolve_db_path(start=tmp_path) == runtime_db


def test_resolve_db_path_falls_back_to_example_db(tmp_path: Path):
    example_db = (tmp_path / DEFAULT_EXAMPLE_DB_PATH).resolve()
    _seed_db(example_db)

    assert resolve_db_path(start=tmp_path) == example_db


def test_resolve_db_path_uses_config_before_defaults(tmp_path: Path):
    custom_db = (tmp_path / "custom" / "words.sqlite3").resolve()
    _seed_db(custom_db)
    (tmp_path / "neep.toml").write_text(
        '[words]\ndb_path = "custom/words.sqlite3"\n',
        encoding="utf-8",
    )

    assert resolve_db_path(start=tmp_path) == custom_db


def test_resolve_writable_db_path_keeps_runtime_default(tmp_path: Path):
    example_db = (tmp_path / DEFAULT_EXAMPLE_DB_PATH).resolve()
    _seed_db(example_db)

    assert (
        resolve_writable_db_path(start=tmp_path) == (tmp_path / DEFAULT_RUNTIME_DB_PATH).resolve()
    )
