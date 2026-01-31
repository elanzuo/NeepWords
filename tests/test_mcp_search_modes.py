import os
import re
import sys
import time
from contextlib import contextmanager
from typing import Iterable

import pytest

# Ensure project root is importable
sys.path.append(os.getcwd())

from neep_mcp import server as mcp_server


@contextmanager
def _rate_limiter_disabled():
    limiter = mcp_server._rate_limiter
    original_min_interval = limiter._min_interval
    original_last_call = limiter._last_call
    try:
        limiter._min_interval = 0.0
        limiter._last_call = 0.0
        yield
    finally:
        limiter._min_interval = original_min_interval
        limiter._last_call = original_last_call


def _like_to_regex(pattern: str) -> re.Pattern[str]:
    escaped: list[str] = []
    for ch in pattern:
        if ch == "%":
            escaped.append(".*")
        elif ch == "_":
            escaped.append(".")
        else:
            escaped.append(re.escape(ch))
    return re.compile("^" + "".join(escaped) + "$")


def _is_subsequence(needle: str, haystack: str) -> bool:
    it = iter(haystack)
    return all(ch in it for ch in needle)


def _search(mode: str, query: str, limit: int = 200, offset: int = 0):
    with _rate_limiter_disabled():
        return mcp_server.search_words(query=query, mode=mode, limit=limit, offset=offset)


def _extract_words(response: dict) -> list[str]:
    assert response["ok"] is True
    return [row["word"] for row in response["data"]["results"]]


@pytest.mark.parametrize(
    "pattern",
    [
        "%vert",  # suffix
        "in%tion",  # in...tion
        "re____",  # re + 4 chars
        "co-%",  # hyphen allowed
        "%tion",  # common suffix
        "pre%ing",  # prefix/suffix combo
        "de_%",  # single-char wildcard near start
        "%logy",  # another common suffix
    ],
)
def test_search_words_wildcard_accepts_valid_patterns(pattern: str):
    response = _search("wildcard", pattern)
    assert response["ok"] is True


@pytest.mark.parametrize("pattern", ["%", "__", "%%"])
def test_search_words_wildcard_rejects_no_letters(pattern: str):
    response = _search("wildcard", pattern)
    assert response["ok"] is False
    assert response["error"] == "invalid_query"


def test_search_words_wildcard_results_match_like_pattern():
    pattern = "%vert%"
    response = _search("wildcard", pattern)
    words = _extract_words(response)
    regex = _like_to_regex(pattern)

    for word in words:
        assert regex.match(word.lower())


def test_search_words_prefix_contains_fuzzy_contracts():
    prefix_queries = ["trans", "inter", "pre"]
    suffix_queries = ["tion", "ment", "able"]
    contains_queries = ["vert", "form", "press"]
    fuzzy_queries = ["tst", "tmn", "spr"]

    for query in prefix_queries:
        prefix_resp = _search("prefix", query)
        for word in _extract_words(prefix_resp):
            assert word.lower().startswith(query)

    for query in suffix_queries:
        suffix_resp = _search("suffix", query)
        for word in _extract_words(suffix_resp):
            assert word.lower().endswith(query)

    for query in contains_queries:
        contains_resp = _search("contains", query)
        for word in _extract_words(contains_resp):
            assert query in word.lower()

    for query in fuzzy_queries:
        fuzzy_resp = _search("fuzzy", query)
        for word in _extract_words(fuzzy_resp):
            assert _is_subsequence(query, word.lower())


def test_search_words_wildcard_matches_contains_equivalent():
    pattern = "%vert%"
    wildcard_resp = _search("wildcard", pattern)
    contains_resp = _search("contains", "vert")

    wildcard_words = {word.lower() for word in _extract_words(wildcard_resp)}
    contains_words = {word.lower() for word in _extract_words(contains_resp)}

    # If wildcard returned anything, it should be within contains results
    if wildcard_words:
        assert wildcard_words.issubset(contains_words)


@pytest.mark.skipif(
    os.environ.get("NEEP_PERF_TEST") != "1",
    reason="set NEEP_PERF_TEST=1 to run perf comparison",
)
def test_search_words_performance_comparison():
    os.environ.setdefault("NEEP_WORDS_DB_PATH", "resources/data/words.sqlite3")

    modes = {
        "prefix": (["trans", "inter", "pre", "con"], 40),
        "suffix": (["tion", "ment", "able", "less"], 40),
        "contains": (["vert", "form", "press", "port"], 40),
        "fuzzy": (["tst", "tmn", "spr", "prg"], 40),
        "wildcard": (["%vert%", "in%tion", "re____", "%tion"], 40),
    }

    timings: dict[str, float] = {}
    with _rate_limiter_disabled():
        for mode, (queries, loops) in modes.items():
            start = time.perf_counter()
            for _ in range(loops):
                for query in queries:
                    response = mcp_server.search_words(query=query, mode=mode, limit=20)
                    assert response["ok"] is True
            elapsed = time.perf_counter() - start
            timings[mode] = elapsed / (loops * len(queries))

    print("search_words avg latency (seconds)")
    for mode, avg in timings.items():
        print(f"{mode}: {avg:.6f}")
