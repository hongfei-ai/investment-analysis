"""Unit tests for integrations.poller.

Covers the reconcile path (Notion → filesystem) and trigger dispatch. The
Notion client is fully stubbed — no network traffic. The filesystem uses
a tmp_path fixture so the on-disk JSON state is isolated per test.
"""

from __future__ import annotations

import pytest

import shared
from auth import User
from integrations import agent_runner, poller


# ─── Fixtures ───────────────────────────────────────────────────────────────

@pytest.fixture
def deals_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "DEALS_DIR", tmp_path)
    monkeypatch.setattr(shared, "OUTPUTS_DIR", tmp_path / "outputs")
    return tmp_path


def _make_page(
    *,
    title: str = "Acme",
    run_agent: str | None = None,
    status: str | None = None,
    deal_stage: str | None = "contacted",
    priority: str | None = None,
    founder_name: str = "",
    owner_email: str = "",
    collaborators: list[str] | None = None,
    last_edited_by_id: str = "user-1",
    last_edited_email: str = "",
) -> dict:
    """Construct a fake Notion page dict matching the shape `retrieve_page` returns."""
    def _people(emails: list[str]) -> list[dict]:
        return [
            {"id": f"p{i}", "person": {"email": email}}
            for i, email in enumerate(emails)
        ]

    return {
        "id": "page-123",
        "last_edited_time": "2026-04-25T10:00:00.000Z",
        "last_edited_by": {
            "id": last_edited_by_id,
            "person": {"email": last_edited_email} if last_edited_email else {},
        },
        "properties": {
            "Company Name":    {"title": [{"plain_text": title}]},
            "Run Agent":       {"select": {"name": run_agent} if run_agent else None},
            "Status":          {"select": {"name": status} if status else None},
            "Deal Stage":      {"select": {"name": deal_stage} if deal_stage else None},
            "Priority":        {"select": {"name": priority} if priority else None},
            "Next Step":       {"rich_text": []},
            "Notes":           {"rich_text": []},
            "Founder Name":    {"rich_text": [{"plain_text": founder_name}] if founder_name else []},
            "Founder LinkedIn": {"url": ""},
            "Company Website": {"url": ""},
            "Intro Source":    {"rich_text": []},
            "Intro Context":   {"rich_text": []},
            "Initial Notes":   {"rich_text": []},
            "Owner":           {"people": _people([owner_email]) if owner_email else []},
            "Collaborators":   {"people": _people(collaborators or [])},
        },
    }


# ─── Trigger resolution ─────────────────────────────────────────────────────

def test_resolve_trigger_single_agent():
    kind, keys = agent_runner.resolve_trigger("A3")
    assert kind == "agent"
    assert keys == ["agent3_founder_diligence"]


def test_resolve_trigger_phase():
    kind, keys = agent_runner.resolve_trigger("Phase 2")
    assert kind == "phase"
    assert keys[0] == "agent2_diligence_mgmt"
    assert "agent6_thesis_check" in keys


def test_resolve_trigger_unknown():
    kind, keys = agent_runner.resolve_trigger("banana")
    assert kind == "unknown"
    assert keys == []


def test_agent_config_has_all_nine_agents():
    expected = {
        "agent1_precall", "agent2_diligence_mgmt", "agent3_founder_diligence",
        "agent4_market_diligence", "agent5_reference_check", "agent6_thesis_check",
        "agent7_premortem", "agent8_ic_simulation", "agent9_ic_memo",
    }
    assert set(agent_runner.AGENT_CONFIG.keys()) == expected

    # Every entry must carry the four required keys
    for key, cfg in agent_runner.AGENT_CONFIG.items():
        for required in ("system", "user_fn", "section", "field", "max_tokens"):
            assert required in cfg, f"{key} missing {required!r}"


# ─── Reconcile: Notion → filesystem ─────────────────────────────────────────

def test_reconcile_pulls_inputs_into_deal_json(deals_in_tmp):
    page = _make_page(
        title="Acme",
        founder_name="Ada Lovelace",
        deal_stage="diligence",
        priority="H",
    )
    deal_name = poller.reconcile_from_notion(page, User(email="ada@example.com"))

    reloaded = shared.load_deal(deal_name)
    assert deal_name == "Acme"
    assert reloaded["deal_stage"] == "diligence"
    assert reloaded["priority"] == "H"
    assert reloaded["inputs"]["founder_name"] == "Ada Lovelace"


def test_reconcile_syncs_owner_and_collaborators(deals_in_tmp):
    page = _make_page(
        title="Beta",
        owner_email="grace@example.com",
        collaborators=["ada@example.com", "hedy@example.com"],
    )
    poller.reconcile_from_notion(page, User(email="grace@example.com"))

    reloaded = shared.load_deal("Beta")
    assert reloaded["owner_email"] == "grace@example.com"
    assert set(reloaded["collaborators"]) == {"ada@example.com", "hedy@example.com"}


def test_reconcile_empty_priority_clears_field(deals_in_tmp):
    # First set a priority on disk
    d = shared.load_deal("Gamma")
    d["priority"] = "H"
    shared.atomic_save_deal(d)

    page = _make_page(title="Gamma", priority=None)
    poller.reconcile_from_notion(page, User(email="ada@example.com"))

    reloaded = shared.load_deal("Gamma")
    assert reloaded["priority"] is None


def test_reconcile_raises_on_missing_company_name():
    page = _make_page(title="")
    with pytest.raises(ValueError):
        poller.reconcile_from_notion(page, User(email="ada@example.com"))


# ─── Authorization pre-check ────────────────────────────────────────────────

def test_authorized_true_for_owner(deals_in_tmp):
    d = shared.load_deal("Delta")
    d["owner_email"] = "ada@example.com"
    shared.atomic_save_deal(d)
    assert agent_runner.authorized("Delta", User(email="ada@example.com")) is True


def test_authorized_false_for_stranger(deals_in_tmp):
    d = shared.load_deal("Epsilon")
    d["owner_email"] = "ada@example.com"
    shared.atomic_save_deal(d)
    assert agent_runner.authorized("Epsilon", User(email="mal@example.com")) is False


def test_authorized_true_for_collaborator(deals_in_tmp):
    d = shared.load_deal("Zeta")
    d["owner_email"] = "ada@example.com"
    d["collaborators"] = ["grace@example.com"]
    shared.atomic_save_deal(d)
    assert agent_runner.authorized("Zeta", User(email="grace@example.com")) is True
