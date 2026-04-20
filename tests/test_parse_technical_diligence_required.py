import pytest

from shared import parse_technical_diligence_required as parse


@pytest.mark.parametrize(
    "text,expected",
    [
        ("technical_diligence_required: true", True),
        ("technical_diligence_required: false", False),
        ("`technical_diligence_required: true`", True),
        ("Technical_Diligence_Required: TRUE", True),
        ("technical_diligence_required:`true`", True),
        ("some other text\ntechnical_diligence_required: true\nmore", True),
        ("no flag here", False),
        ("", False),
        (None, False),
        ("technical_diligence_required: maybe", False),
    ],
)
def test_parse(text, expected):
    assert parse(text) is expected
