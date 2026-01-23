from neepwordextractor.cleaner import normalize_text


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
