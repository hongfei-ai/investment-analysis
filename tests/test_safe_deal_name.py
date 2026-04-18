import pytest

from shared import _safe_deal_name


@pytest.mark.parametrize("name", ["Acme", "Acme Corp", "Acme-2024", "deal_42"])
def test_accepts_plain_names(name):
    assert _safe_deal_name(name) == name


def test_strips_surrounding_whitespace():
    assert _safe_deal_name("  Acme  ") == "Acme"


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "../etc",
        "..",
        ".",
        ".hidden",
        "a/b",
        "a\\b",
        "foo\x00bar",
    ],
)
def test_rejects_unsafe_names(bad):
    with pytest.raises(ValueError):
        _safe_deal_name(bad)


@pytest.mark.parametrize("bad", [None, 123, object()])
def test_rejects_non_string(bad):
    with pytest.raises((ValueError, TypeError, AttributeError)):
        _safe_deal_name(bad)
