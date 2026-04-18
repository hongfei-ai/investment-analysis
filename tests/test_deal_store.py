from pathlib import Path

import pytest

import shared
from auth import User


ADA = User(email="ada@example.com")


def _own(deal):
    """Claim an in-memory deal for ADA so shared.save_deal accepts it."""
    deal["owner_email"] = ADA.email
    return deal


def test_load_deal_returns_skeleton_for_new_name(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "DEALS_DIR", tmp_path)

    deal = shared.load_deal("Acme")

    assert deal["deal_id"] == "Acme"
    assert deal["company_name"] == "Acme"
    assert deal["status"] == "pre-call"
    assert set(deal.keys()) >= {"inputs", "pre_call", "call_notes", "diligence", "ic_preparation"}


def test_save_then_load_roundtrips(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "DEALS_DIR", tmp_path)

    deal = _own(shared.load_deal("Acme"))
    deal["inputs"]["founder_name"] = "Ada Lovelace"
    shared.save_deal(deal, ADA)

    reloaded = shared.load_deal("Acme")
    assert reloaded["inputs"]["founder_name"] == "Ada Lovelace"


def test_save_output_writes_markdown(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "DEALS_DIR", tmp_path)
    monkeypatch.setattr(shared, "OUTPUTS_DIR", tmp_path / "outputs")

    # Create a deal owned by ADA so save_output's require_editor passes.
    deal = _own(shared.load_deal("Acme"))
    shared.save_deal(deal, ADA)

    path = shared.save_output("Acme", "agent1_precall", "# Hello", ADA)

    assert Path(path).read_text(encoding="utf-8") == "# Hello"
    assert Path(path).parent.name == "Acme"


def test_save_output_rejects_unsafe_deal_name(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "OUTPUTS_DIR", tmp_path)

    with pytest.raises(ValueError):
        shared.save_output("../escape", "agent1_precall", "hi", ADA)
