import os
import sys
from pathlib import Path

import pytest

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from word_extractor.output import add_words_to_db


@pytest.fixture
def sample_words_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "words.sqlite3"
    version_2026 = [
        "abandon",
        "ability",
        "avert",
        "biology",
        "co-operate",
        "convert",
        "debut",
        "deform",
        "export",
        "form",
        "information",
        "interact",
        "intervene",
        "logy",
        "measurement",
        "portable",
        "preexisting",
        "preparing",
        "pressure",
        "reform",
        "suppression",
        "technology",
        "termination",
        "test",
        "transport",
        "translate",
        "transmit",
        "transplant",
        "vertigo",
    ]
    version_2027 = [
        "abandon",
        "adaptive",
        "co-operate",
        "cybersecurity",
        "debug",
        "formation",
        "prewarming",
        "transport",
    ]

    add_words_to_db(version_2026, db_path=db_path, version="2026")
    add_words_to_db(version_2027, db_path=db_path, version="2027")
    return db_path


@pytest.fixture
def configured_words_db(sample_words_db: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("NEEP_WORDS_DB_PATH", os.fspath(sample_words_db))
    monkeypatch.delenv("NEEP_WORDS_VERSION", raising=False)
    return sample_words_db
