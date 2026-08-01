from amb.norm import norm_v1


def test_casefold_and_whitespace():
    assert norm_v1("  Coffee\nPrefer ") == "coffee prefer"


def test_answer_strip_punct():
    assert norm_v1("Coffee!", for_answer=True) == "coffee"
