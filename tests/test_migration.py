"""Tests for migrations/001_add_owner_and_stage.py — idempotent + safe defaults."""

from migrations import migrate_001, run_all


def test_owner_defaults_from_deal_champion():
    deal = {"inputs": {"deal_champion": "Ada Lovelace"}, "status": "pre-call"}
    migrated = migrate_001(deal)
    assert migrated["owner_email"] == "Ada Lovelace"


def test_owner_defaults_to_unassigned_when_no_champion():
    deal = {"inputs": {"deal_champion": ""}, "status": "pre-call"}
    assert migrate_001(deal)["owner_email"] == "unassigned"


def test_owner_defaults_to_unassigned_when_no_inputs():
    deal = {"status": "pre-call"}
    assert migrate_001(deal)["owner_email"] == "unassigned"


def test_deal_stage_derived_from_status():
    assert migrate_001({"status": "pre-call"})["deal_stage"] == "contacted"
    assert migrate_001({"status": "diligence"})["deal_stage"] == "diligence"
    assert migrate_001({"status": "post-diligence"})["deal_stage"] == "diligence"
    assert migrate_001({"status": "ic-prep"})["deal_stage"] == "ic"
    assert migrate_001({"status": "complete"})["deal_stage"] == "ic"


def test_deal_stage_fallback_for_unknown_status():
    assert migrate_001({"status": "weird"})["deal_stage"] == "contacted"


def test_migration_is_idempotent():
    deal = {"status": "pre-call"}
    once = migrate_001(dict(deal))
    twice = migrate_001(dict(once))
    assert once == twice


def test_existing_fields_are_not_overwritten():
    deal = {
        "status": "pre-call",
        "owner_email": "ada@example.com",
        "deal_stage": "term_sheet",
        "_version": 42,
        "priority": "H",
    }
    migrated = migrate_001(dict(deal))
    assert migrated["owner_email"] == "ada@example.com"
    assert migrated["deal_stage"] == "term_sheet"
    assert migrated["_version"] == 42
    assert migrated["priority"] == "H"


def test_new_optional_fields_default_to_none():
    deal = migrate_001({"status": "pre-call"})
    for k in ("priority", "round_size", "check_size", "valuation",
              "sector", "geography", "next_step", "next_step_due"):
        assert deal[k] is None


def test_run_all_applies_every_migration():
    deal = {"status": "pre-call"}
    result = run_all(dict(deal))
    assert result["owner_email"] == "unassigned"
    assert result["deal_stage"] == "contacted"
    assert "_version" in result
