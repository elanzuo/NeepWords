"""MCP server for querying WordExtractor words database (read-only)."""

from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Iterable

from mcp.server.fastmcp import FastMCP

from neep_mcp.lexicon import WordsLexicon, resolve_db_path

DEFAULT_RATE_LIMIT_SECONDS = 0.5


class RateLimiter:
    def __init__(self, min_interval: float = DEFAULT_RATE_LIMIT_SECONDS) -> None:
        self._min_interval = min_interval
        self._last_call = 0.0

    def check(self) -> str | None:
        now = time.monotonic()
        if now - self._last_call < self._min_interval:
            return "rate_limited"
        self._last_call = now
        return None


mcp = FastMCP("neep-words")
_rate_limiter = RateLimiter()


def _make_response(
    ok: bool, data: Any = None, error: str | None = None, warnings: list[str] | None = None
) -> dict[str, Any]:
    return {
        "ok": ok,
        "error": error,
        "data": data,
        "warnings": warnings or [],
    }


def _lexicon() -> WordsLexicon:
    return WordsLexicon(resolve_db_path())


@mcp.tool()
def lookup_words(words: Iterable[str], match: str | None = "auto") -> dict[str, Any]:
    """
    Look up multiple words in the NEEP (Postgraduate Entrance Exam) syllabus.

    Args:
        words: List of words to query (e.g., ["abandon", "ability"]).
        match: Matching strategy:
            - "auto" (default): Tries exact spelling match first, then falls back to normalized form (lemma).
            - "word": strict exact spelling match.
            - "norm": strict normalized form (lemma) match.
    """
    rate_error = _rate_limiter.check()
    if rate_error:
        return _make_response(False, error=rate_error)

    try:
        data, warnings = _lexicon().lookup_words(words, match=match)
    except FileNotFoundError:
        return _make_response(False, error="db_not_found")
    except ValueError as exc:
        return _make_response(False, error=str(exc))
    except sqlite3.Error:
        return _make_response(False, error="db_error")

    return _make_response(True, data=data, warnings=warnings)


@mcp.tool()
def search_words(
    query: str,
    mode: str | None = "contains",
    limit: int | None = 10,
    offset: int | None = 0,
) -> dict[str, Any]:
    """
    Search for words in the syllabus using prefix, substring, or fuzzy matching.

    Args:
        query: The search string.
        mode: Search mode:
            - "prefix": Matches words starting with the query (e.g., "ab" -> "abandon").
            - "suffix": Matches words ending with the query (e.g., "tion" -> "information").
            - "contains" (default): Matches words containing the query (e.g., "ban" -> "abandon").
            - "fuzzy": Matches characters in sequence (e.g., "tst" -> "test").
            - "wildcard": SQL LIKE pattern with %, _ (e.g., "in%tion" -> "information").
        limit: Max number of results to return (default 10, max 200).
        offset: Pagination offset.
    """
    rate_error = _rate_limiter.check()
    if rate_error:
        return _make_response(False, error=rate_error)

    try:
        data, warnings = _lexicon().search_words(query=query, mode=mode, limit=limit, offset=offset)
    except FileNotFoundError:
        return _make_response(False, error="db_not_found")
    except ValueError as exc:
        return _make_response(False, error=str(exc))
    except sqlite3.Error:
        return _make_response(False, error="db_error")

    return _make_response(True, data=data, warnings=warnings)


@mcp.tool()
def get_random_words(count: int | None = 5, min_frequency: int | None = None) -> dict[str, Any]:
    """
    Get a random set of words from the syllabus, useful for quizzes or daily learning.

    Args:
        count: Number of words to retrieve (default 5, max 50).
        min_frequency: If provided, only returns words with frequency >= this value.
                       Higher frequency generally means more common/important words.
    """
    rate_error = _rate_limiter.check()
    if rate_error:
        return _make_response(False, error=rate_error)

    try:
        data = _lexicon().get_random_words(count=count, min_frequency=min_frequency)
    except FileNotFoundError:
        return _make_response(False, error="db_not_found")
    except ValueError as exc:
        return _make_response(False, error=str(exc))
    except sqlite3.Error:
        return _make_response(False, error="db_error")

    return _make_response(True, data=data)


@mcp.resource("neep://stats/summary")
def stats_summary() -> str:
    try:
        stats = _lexicon().stats_summary()
    except FileNotFoundError:
        payload = _make_response(False, error="db_not_found")
        return json.dumps(payload, ensure_ascii=False)
    except sqlite3.Error:
        payload = _make_response(False, error="db_error")
        return json.dumps(payload, ensure_ascii=False)

    return json.dumps(_make_response(True, data=stats), ensure_ascii=False)


@mcp.resource("neep://stats/schema")
def stats_schema() -> str:
    try:
        schema = _lexicon().schema()
    except FileNotFoundError:
        payload = _make_response(False, error="db_not_found")
        return json.dumps(payload, ensure_ascii=False)
    except sqlite3.Error:
        payload = _make_response(False, error="db_error")
        return json.dumps(payload, ensure_ascii=False)

    return json.dumps(_make_response(True, data={"columns": schema}), ensure_ascii=False)


@mcp.prompt("neep_quiz")
def neep_quiz(count: int = 5) -> str:
    return (
        "You are preparing a vocabulary quiz based on the WordExtractor database. "
        "Call the get_random_words tool with the requested count, then create a short quiz "
        "(fill-in-the-blank or synonym choice). Provide the answer key after the questions. "
        f"Requested count: {count}."
    )


if __name__ == "__main__":
    mcp.run()
