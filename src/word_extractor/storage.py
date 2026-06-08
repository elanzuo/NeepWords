"""Shared storage helpers for versioned SQLite word data."""

from __future__ import annotations

import sqlite3
from typing import Any


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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_words_version_word ON words(version_id, word)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_words_word ON words(word)")


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
    conn.execute("CREATE INDEX IF NOT EXISTS idx_words_version_word ON words(version_id, word)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_words_word ON words(word)")
    return "migrated"


def ensure_writable_schema(
    conn: sqlite3.Connection, *, legacy_version: str | int | None = None
) -> None:
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
