"""Tests for audit.read_activity and the M6 metadata-audit pattern."""

import pytest

import shared
import audit


@pytest.fixture
def deals_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "DEALS_DIR", tmp_path)
    return tmp_path


def test_read_activity_empty(deals_in_tmp):
    assert audit.read_activity("Nonexistent") == []


def test_read_activity_merges_audit_and_runs_newest_first(deals_in_tmp):
    # Deliberately interleaved timestamps.
    audit.append_audit("Acme", actor="ada@example.com", action="deal_created")
    shared.record_run("Acme", "agent1_precall", "done",
                      by_user="ada@example.com",
                      started_at="2026-04-01T10:00:00Z",
                      ended_at="2026-04-01T10:02:00Z")
    audit.append_audit("Acme", actor="ada@example.com", action="metadata_changed",
                       details={"field": "deal_stage", "from": "contacted", "to": "diligence"})
    shared.record_run("Acme", "agent2_diligence_mgmt", "error",
                      by_user="ada@example.com")

    entries = audit.read_activity("Acme")
    assert len(entries) == 4
    # All have the uniform keys the UI consumes
    for e in entries:
        assert set(e.keys()) == {"ts", "kind", "actor", "action", "details"}
        assert e["kind"] in ("audit", "run")
    # Newest first — the last-written record appears at index 0
    timestamps = [e["ts"] for e in entries]
    assert timestamps == sorted(timestamps, reverse=True)


def test_read_activity_distinguishes_run_status(deals_in_tmp):
    shared.record_run("Acme", "agent1_precall", "done", by_user="a@b")
    shared.record_run("Acme", "agent2_diligence_mgmt", "error", by_user="a@b")

    actions = {e["action"] for e in audit.read_activity("Acme") if e["kind"] == "run"}
    assert actions == {"agent_run:done", "agent_run:error"}


def test_metadata_change_audit_pattern(deals_in_tmp):
    """The M6 metadata editor emits `metadata_changed` with from/to details.
    This test pins the shape downstream code (and the activity-feed UI) relies on.
    """
    audit.append_audit(
        "Acme",
        actor="ada@example.com",
        action="metadata_changed",
        details={"field": "priority", "from": None, "to": "H"},
    )
    entries = audit.read_activity("Acme")
    assert len(entries) == 1
    e = entries[0]
    assert e["action"] == "metadata_changed"
    assert e["details"]["field"] == "priority"
    assert e["details"]["from"] is None
    assert e["details"]["to"] == "H"
