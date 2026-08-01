from pathlib import Path

from amb.suite.load import load_suite
from amb.suite.validate import validate_suite

ROOT = Path(__file__).resolve().parents[1]


def test_smoke_validates():
    suite = load_suite(ROOT / "suites" / "smoke")
    errors = validate_suite(suite)
    assert errors == [], errors
