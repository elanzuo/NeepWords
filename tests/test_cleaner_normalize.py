from word_extractor.cleaner import expand_variants, normalize_text


def test_normalize_text_strips_disallowed_chars():
    text = "ab1c, 你好"
    assert normalize_text(text) == ["ab c"]


def test_normalize_text_merges_hyphenation():
    text = "inter-\nnational"
    assert normalize_text(text) == ["international"]


def test_normalize_text_preserves_slash_format():
    text = "gaol   /  jail"
    assert normalize_text(text) == ["gaol / jail"]


def test_normalize_text_filters_noise():
    text = "-\n()\nword"
    assert normalize_text(text) == ["word"]


def test_expand_variants_splits_slash():
    assert expand_variants("gaol / jail") == ["gaol", "jail"]


def test_expand_variants_expands_parentheses():
    assert expand_variants("stor(e)y") == ["story", "storey"]


def test_expand_variants_handles_combined_cases():
    assert expand_variants("colou(r) / color") == ["colour", "color"]
