"""Shared storage helpers for versioned SQLite word data."""

from __future__ import annotations

import os
import sqlite3
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path("resources") / "data" / "words.sqlite3"
SETTINGS_FILE_NAME = "neep.toml"


@dataclass(frozen=True)
class ResolvedVersion:
    id: int
    version_key: str
    label: str | None
    source: str


def normalize_version_key(value: str | int | None) -> str:
    if value is None:
        raise ValueError("missing_version")

    raw = str(value).strip()
    if not raw:
        raise ValueError("missing_version")

    digits = "".join(ch for ch in raw if ch.isdigit())
    if len(digits) == 2:
        year = 2000 + int(digits)
    elif len(digits) == 4:
        year = int(digits)
    else:
        raise ValueError("invalid_version")

    if year < 2000 or year > 2099:
        raise ValueError("invalid_version")

    return str(year)


def default_version_label(version_key: str) -> str:
    return f"{version_key}考研大纲"


def find_settings_file(start: Path | None = None) -> Path | None:
    current = (start or Path.cwd()).resolve()
    search_roots = [current, *current.parents]
    for root in search_roots:
        candidate = root / SETTINGS_FILE_NAME
        if candidate.exists():
            return candidate
    return None


def load_words_settings(start: Path | None = None) -> tuple[dict[str, Any], Path | None]:
    settings_path = find_settings_file(start)
    if settings_path is None:
        return {}, None

    with settings_path.open("rb") as handle:
        payload = tomllib.load(handle)

    words = payload.get("words")
    if isinstance(words, dict):
        return words, settings_path
    return {}, settings_path


def resolve_db_path(explicit: str | Path | None = None, *, start: Path | None = None) -> Path:
    if explicit is not None:
        return Path(explicit)

    env_value = os.environ.get("NEEP_WORDS_DB_PATH") or os.environ.get("NEEP_WORDS_DB")
    if env_value:
        return Path(env_value)

    settings, settings_path = load_words_settings(start)
    config_value = settings.get("db_path")
    if isinstance(config_value, str) and config_value.strip():
        configured = Path(config_value.strip())
        if not configured.is_absolute() and settings_path is not None:
            return (settings_path.parent / configured).resolve()
        return configured

    return DEFAULT_DB_PATH


def resolve_configured_version(start: Path | None = None) -> tuple[str | None, str | None]:
    env_value = os.environ.get("NEEP_WORDS_VERSION")
    if env_value:
        return normalize_version_key(env_value), "env"

    settings, _ = load_words_settings(start)
    config_value = settings.get("default_version")
    if isinstance(config_value, str) and config_value.strip():
        return normalize_version_key(config_value), "config"

    return None, None


def table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row[1] for row in rows]


def detect_schema_mode(conn: sqlite3.Connection) -> str:
    words_columns = table_columns(conn, "words")
    if not words_columns:
        return "missing"

    versions_columns = table_columns(conn, "vocab_versions")
    if versions_columns:
        required_words = {"id", "version_id", "word", "source", "added_at"}
        required_versions = {
            "id",
            "version_key",
            "label",
            "source_pdf",
            "imported_at",
            "is_default",
        }
        if required_words.issubset(set(words_columns)) and required_versions.issubset(
            set(versions_columns)
        ):
            return "versioned"
        return "unknown"

    legacy_words = {"id", "word", "source", "added_at"}
    if set(words_columns) == legacy_words:
        return "legacy"

    return "unknown"


def ensure_versioned_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS vocab_versions (
            id INTEGER PRIMARY KEY,
            version_key TEXT NOT NULL UNIQUE,
            label TEXT,
            source_pdf TEXT,
            imported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1))
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY,
            version_id INTEGER NOT NULL REFERENCES vocab_versions(id),
            word TEXT NOT NULL,
            source TEXT,
            added_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(version_id, word)
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_words_version_word ON words(version_id, word)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_words_word ON words(word)"
    )


def migrate_legacy_schema(
    conn: sqlite3.Connection,
    *,
    legacy_version: str | int,
    label: str | None = None,
) -> str:
    schema_mode = detect_schema_mode(conn)
    if schema_mode == "versioned":
        return "already_versioned"
    if schema_mode == "missing":
        ensure_versioned_schema(conn)
        version_key = normalize_version_key(legacy_version)
        ensure_version_row(conn, version_key, label=label, set_default_if_missing=True)
        return "initialized_versioned"
    if schema_mode != "legacy":
        raise ValueError("unsupported_schema")

    version_key = normalize_version_key(legacy_version)

    conn.execute(
        """
        CREATE TABLE vocab_versions (
            id INTEGER PRIMARY KEY,
            version_key TEXT NOT NULL UNIQUE,
            label TEXT,
            source_pdf TEXT,
            imported_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1))
        )
        """
    )
    conn.execute(
        """
        INSERT INTO vocab_versions (version_key, label, is_default)
        VALUES (?, ?, 1)
        """,
        (version_key, label or default_version_label(version_key)),
    )
    version_id = conn.execute(
        "SELECT id FROM vocab_versions WHERE version_key = ?",
        (version_key,),
    ).fetchone()[0]
    conn.execute(
        """
        CREATE TABLE words_migrated (
            id INTEGER PRIMARY KEY,
            version_id INTEGER NOT NULL REFERENCES vocab_versions(id),
            word TEXT NOT NULL,
            source TEXT,
            added_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
            UNIQUE(version_id, word)
        )
        """
    )
    conn.execute(
        """
        INSERT INTO words_migrated (id, version_id, word, source, added_at)
        SELECT
            id,
            ?,
            lower(trim(word)),
            source,
            COALESCE(added_at, strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        FROM words
        ORDER BY id
        """,
        (version_id,),
    )
    conn.execute("DROP TABLE words")
    conn.execute("ALTER TABLE words_migrated RENAME TO words")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_words_version_word ON words(version_id, word)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_words_word ON words(word)")
    return "migrated"


def ensure_writable_schema(conn: sqlite3.Connection, *, legacy_version: str | int | None = None) -> None:
    schema_mode = detect_schema_mode(conn)
    if schema_mode == "missing":
        ensure_versioned_schema(conn)
        return
    if schema_mode == "versioned":
        ensure_versioned_schema(conn)
        return
    if schema_mode == "legacy":
        if legacy_version is None:
            raise ValueError("legacy_schema_requires_migration")
        migrate_legacy_schema(conn, legacy_version=legacy_version)
        return
    raise ValueError("unsupported_schema")


def ensure_version_row(
    conn: sqlite3.Connection,
    version_key: str | int,
    *,
    label: str | None = None,
    source_pdf: str | None = None,
    set_default_if_missing: bool = True,
) -> int:
    normalized = normalize_version_key(version_key)
    row = conn.execute(
        "SELECT id FROM vocab_versions WHERE version_key = ?",
        (normalized,),
    ).fetchone()
    if row is not None:
        version_id = int(row[0])
        if label is not None or source_pdf is not None:
            conn.execute(
                """
                UPDATE vocab_versions
                SET label = COALESCE(label, ?),
                    source_pdf = COALESCE(source_pdf, ?)
                WHERE id = ?
                """,
                (label, source_pdf, version_id),
            )
        return version_id

    has_default = conn.execute(
        "SELECT 1 FROM vocab_versions WHERE is_default = 1 LIMIT 1"
    ).fetchone()
    conn.execute(
        """
        INSERT INTO vocab_versions (version_key, label, source_pdf, is_default)
        VALUES (?, ?, ?, ?)
        """,
        (
            normalized,
            label or default_version_label(normalized),
            source_pdf,
            0 if has_default or not set_default_if_missing else 1,
        ),
    )
    row = conn.execute(
        "SELECT id FROM vocab_versions WHERE version_key = ?",
        (normalized,),
    ).fetchone()
    if row is None:
        raise RuntimeError("failed_to_create_version")
    return int(row[0])


def resolve_version(
    conn: sqlite3.Connection,
    *,
    requested_version: str | int | None = None,
    configured_version: str | None = None,
) -> ResolvedVersion:
    explicit = normalize_version_key(requested_version) if requested_version is not None else None
    if explicit is not None:
        row = conn.execute(
            """
            SELECT id, version_key, label
            FROM vocab_versions
            WHERE version_key = ?
            """,
            (explicit,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown_version")
        return ResolvedVersion(
            id=row[0],
            version_key=row[1],
            label=row[2],
            source="explicit",
        )

    if configured_version is not None:
        normalized = normalize_version_key(configured_version)
        row = conn.execute(
            """
            SELECT id, version_key, label
            FROM vocab_versions
            WHERE version_key = ?
            """,
            (normalized,),
        ).fetchone()
        if row is None:
            raise ValueError("unknown_configured_version")
        return ResolvedVersion(
            id=row[0],
            version_key=row[1],
            label=row[2],
            source="configured",
        )

    default_row = conn.execute(
        """
        SELECT id, version_key, label
        FROM vocab_versions
        WHERE is_default = 1
        ORDER BY id
        LIMIT 1
        """
    ).fetchone()
    if default_row is not None:
        return ResolvedVersion(
            id=default_row[0],
            version_key=default_row[1],
            label=default_row[2],
            source="db_default",
        )

    rows = conn.execute(
        """
        SELECT id, version_key, label
        FROM vocab_versions
        ORDER BY version_key
        """
    ).fetchall()
    if len(rows) == 1:
        row = rows[0]
        return ResolvedVersion(
            id=row[0],
            version_key=row[1],
            label=row[2],
            source="single_available",
        )

    raise ValueError("missing_version")


def list_versions(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT
            vv.id,
            vv.version_key,
            vv.label,
            vv.source_pdf,
            vv.imported_at,
            vv.is_default,
            COUNT(w.id) AS word_count
        FROM vocab_versions AS vv
        LEFT JOIN words AS w ON w.version_id = vv.id
        GROUP BY vv.id
        ORDER BY vv.version_key
        """
    ).fetchall()
    return [
        {
            "id": row[0],
            "version": row[1],
            "label": row[2],
            "source_pdf": row[3],
            "imported_at": row[4],
            "is_default": bool(row[5]),
            "word_count": row[6],
        }
        for row in rows
    ]


def set_default_version(conn: sqlite3.Connection, version_key: str | int) -> dict[str, Any]:
    schema_mode = detect_schema_mode(conn)
    if schema_mode == "missing":
        raise ValueError("words_table_not_found")
    if schema_mode == "legacy":
        raise ValueError("legacy_schema_no_versions")
    if schema_mode != "versioned":
        raise ValueError("unsupported_schema")

    normalized = normalize_version_key(version_key)
    row = conn.execute(
        """
        SELECT id, version_key, label
        FROM vocab_versions
        WHERE version_key = ?
        """,
        (normalized,),
    ).fetchone()
    if row is None:
        raise ValueError("unknown_version")

    conn.execute("UPDATE vocab_versions SET is_default = 0 WHERE is_default != 0")
    conn.execute(
        "UPDATE vocab_versions SET is_default = 1 WHERE id = ?",
        (row[0],),
    )
    return {
        "id": row[0],
        "version": row[1],
        "label": row[2],
        "is_default": True,
    }
