"""Tests that M5 permission gates actually deny non-editors at the shared layer."""

import pytest

import shared
from auth import User, PermissionError


@pytest.fixture
def deals_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "DEALS_DIR", tmp_path)
    monkeypatch.setattr(shared, "OUTPUTS_DIR", tmp_path / "outputs")
    return tmp_path


ADA = User(email="ada@example.com")
MAL = User(email="mal@example.com")


def _owned_by(owner_email: str):
    deal = shared.load_deal("Acme")
    deal["owner_email"] = owner_email
    shared.atomic_save_deal(deal)  # bypass enforcement to set up state
    return shared.load_deal("Acme")


def test_save_deal_allows_owner(deals_in_tmp):
    deal = _owned_by(ADA.email)
    shared.save_deal(deal, ADA)  # should not raise
    assert shared.load_deal("Acme")["_version"] >= 1


def test_save_deal_denies_non_owner(deals_in_tmp):
    deal = _owned_by(ADA.email)
    with pytest.raises(PermissionError):
        shared.save_deal(deal, MAL)


def test_save_deal_denies_unassigned(deals_in_tmp):
    deal = _owned_by("unassigned")
    with pytest.raises(PermissionError):
        shared.save_deal(deal, ADA)


def test_save_deal_allows_collaborator(deals_in_tmp):
    deal = _owned_by(ADA.email)
    deal["collaborators"] = ["grace@example.com"]
    shared.atomic_save_deal(deal)
    deal = shared.load_deal("Acme")

    grace = User(email="grace@example.com")
    shared.save_deal(deal, grace)


def test_save_output_denies_non_owner(deals_in_tmp):
    _owned_by(ADA.email)
    with pytest.raises(PermissionError):
        shared.save_output("Acme", "agent1_precall", "# Hi", MAL)


def test_save_output_allows_owner(deals_in_tmp):
    _owned_by(ADA.email)
    path = shared.save_output("Acme", "agent1_precall", "# Hi", ADA)
    assert path.read_text(encoding="utf-8") == "# Hi"


def test_save_deal_anonymous_user_denied(deals_in_tmp):
    deal = _owned_by(ADA.email)
    with pytest.raises(PermissionError):
        shared.save_deal(deal, User(email=""))


def test_claim_flow_sets_owner_and_records_audit(deals_in_tmp):
    """The dashboard Claim button: unassigned → owner becomes current user,
    audit record appended, and subsequent save_deal by that user succeeds."""
    import audit as audit_mod

    _owned_by("unassigned")

    # Simulate the dashboard _claim_deal body
    deal = shared.load_deal("Acme")
    assert deal["owner_email"] == "unassigned"
    deal["owner_email"] = ADA.email
    deal.setdefault("created_by", ADA.email)
    shared.atomic_save_deal(deal)
    audit_mod.append_audit("Acme", actor=ADA.email, action="owner_claimed",
                           details={"new_owner": ADA.email})

    reloaded = shared.load_deal("Acme")
    assert reloaded["owner_email"] == ADA.email

    records = audit_mod.read_audit("Acme")
    assert len(records) == 1
    assert records[0]["action"] == "owner_claimed"
    assert records[0]["actor"] == ADA.email

    # After claim, the owner can save normally
    shared.save_deal(reloaded, ADA)
