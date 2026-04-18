import pytest

from auth import (
    User,
    PermissionError,
    is_allowed_domain,
    is_editor,
    require_editor,
)


# ─── User dataclass ──────────────────────────────────────────────────────────

def test_user_is_authenticated_true():
    assert User(email="ada@example.com").is_authenticated is True


def test_user_is_authenticated_false_on_empty_email():
    assert User(email="").is_authenticated is False


# ─── is_allowed_domain ───────────────────────────────────────────────────────

@pytest.mark.parametrize(
    "email,allowed,expected",
    [
        ("ada@example.com", "example.com", True),
        ("ada@EXAMPLE.COM", "example.com", True),
        ("ada@example.com", "EXAMPLE.COM", True),
        ("ada@example.com", "other.com", False),
        ("ada@example.co.uk", "example.co.uk", True),
        ("ada@sub.example.com", "example.com", False),
        ("", "example.com", False),
        ("not-an-email", "example.com", False),
        ("ada@example.com", ["example.com", "other.com"], True),
        ("ada@other.com", ["example.com", "other.com"], True),
        ("ada@third.com", ["example.com", "other.com"], False),
        ("ada@example.com", [], False),
    ],
)
def test_is_allowed_domain(email, allowed, expected):
    assert is_allowed_domain(email, allowed) is expected


# ─── is_editor ───────────────────────────────────────────────────────────────

def _deal(owner="ada@example.com", collaborators=None, deal_id="Acme"):
    return {
        "deal_id": deal_id,
        "owner_email": owner,
        "collaborators": collaborators or [],
    }


def test_is_editor_owner():
    user = User(email="ada@example.com")
    assert is_editor(_deal(owner="ada@example.com"), user) is True


def test_is_editor_owner_case_insensitive():
    user = User(email="Ada@Example.COM")
    assert is_editor(_deal(owner="ada@example.com"), user) is True


def test_is_editor_collaborator():
    user = User(email="grace@example.com")
    deal = _deal(owner="ada@example.com", collaborators=["grace@example.com"])
    assert is_editor(deal, user) is True


def test_is_editor_non_member():
    user = User(email="mal@example.com")
    deal = _deal(owner="ada@example.com", collaborators=["grace@example.com"])
    assert is_editor(deal, user) is False


def test_is_editor_anonymous():
    deal = _deal(owner="ada@example.com")
    assert is_editor(deal, None) is False
    assert is_editor(deal, User(email="")) is False


def test_is_editor_unassigned_deal_is_not_editable():
    # unassigned deals require a Claim step; they are not editable by default
    user = User(email="ada@example.com")
    assert is_editor(_deal(owner="unassigned"), user) is False
    assert is_editor(_deal(owner=""), user) is False


# ─── require_editor ──────────────────────────────────────────────────────────

def test_require_editor_ok_for_owner():
    user = User(email="ada@example.com")
    require_editor(_deal(owner="ada@example.com"), user)  # no raise


def test_require_editor_raises_for_non_owner():
    user = User(email="mal@example.com")
    with pytest.raises(PermissionError):
        require_editor(_deal(owner="ada@example.com"), user)


def test_require_editor_raises_for_anonymous():
    with pytest.raises(PermissionError):
        require_editor(_deal(owner="ada@example.com"), None)
