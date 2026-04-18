"""Tests for audit.py and shared.record_run / read_runs."""

import pytest

import shared
import audit


@pytest.fixture
def deals_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "DEALS_DIR", tmp_path)
    return tmp_path


# ─── audit.py ────────────────────────────────────────────────────────────────

def test_audit_round_trip(deals_in_tmp):
    audit.append_audit("Acme", "ada@example.com", "stage_changed", {"to": "ic"})
    audit.append_audit("Acme", "ada@example.com", "ran_agent", {"agent": "agent7"})
    records = audit.read_audit("Acme")
    assert len(records) == 2
    assert records[0]["actor"] == "ada@example.com"
    assert records[0]["action"] == "stage_changed"
    assert records[0]["details"] == {"to": "ic"}
    assert records[1]["action"] == "ran_agent"
    assert all("ts" in r for r in records)


def test_audit_empty_returns_empty_list(deals_in_tmp):
    assert audit.read_audit("Nonexistent") == []


def test_audit_details_default_to_empty_dict(deals_in_tmp):
    audit.append_audit("Acme", "ada@example.com", "claimed")
    records = audit.read_audit("Acme")
    assert records[0]["details"] == {}


def test_audit_rejects_unsafe_deal_name(deals_in_tmp):
    with pytest.raises(ValueError):
        audit.append_audit("../escape", "ada@example.com", "hack")


def test_audit_is_append_only_across_calls(deals_in_tmp):
    for i in range(5):
        audit.append_audit("Acme", "ada@example.com", f"action_{i}")
    records = audit.read_audit("Acme")
    assert [r["action"] for r in records] == [f"action_{i}" for i in range(5)]


# ─── shared.record_run / read_runs ───────────────────────────────────────────

def test_record_run_round_trip(deals_in_tmp):
    shared.record_run("Acme", "agent1_precall", "running", by_user="ada@example.com",
                      started_at="2026-04-18T10:00:00Z")
    shared.record_run("Acme", "agent1_precall", "done", by_user="ada@example.com",
                      started_at="2026-04-18T10:00:00Z",
                      ended_at="2026-04-18T10:02:00Z")
    runs = shared.read_runs("Acme")
    assert len(runs) == 2
    assert runs[0]["status"] == "running"
    assert runs[1]["status"] == "done"
    assert runs[1]["ended_at"] == "2026-04-18T10:02:00Z"


def test_read_runs_returns_empty_for_missing_deal(deals_in_tmp):
    assert shared.read_runs("Nonexistent") == []
