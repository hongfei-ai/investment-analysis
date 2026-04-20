"""Tests for atomic_save_deal optimistic locking."""

import pytest

import shared


@pytest.fixture
def deals_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setattr(shared, "DEALS_DIR", tmp_path)
    return tmp_path


def test_fresh_deal_starts_at_version_1_after_save(deals_in_tmp):
    deal = shared.load_deal("Acme")
    assert deal["_version"] == 0  # skeleton
    shared.atomic_save_deal(deal)
    assert deal["_version"] == 1


def test_save_bumps_version_each_time(deals_in_tmp):
    deal = shared.load_deal("Acme")
    shared.atomic_save_deal(deal)
    shared.atomic_save_deal(deal)
    shared.atomic_save_deal(deal)
    assert deal["_version"] == 3


def test_expected_version_matching_succeeds(deals_in_tmp):
    deal = shared.load_deal("Acme")
    shared.atomic_save_deal(deal)   # version 1

    reloaded = shared.load_deal("Acme")
    assert reloaded["_version"] == 1

    shared.atomic_save_deal(reloaded, expected_version=1)
    assert reloaded["_version"] == 2


def test_expected_version_mismatch_raises(deals_in_tmp):
    deal = shared.load_deal("Acme")
    shared.atomic_save_deal(deal)  # version 1

    stale = shared.load_deal("Acme")
    # Another writer bumps the file in the meantime
    other = shared.load_deal("Acme")
    shared.atomic_save_deal(other)  # version 2

    with pytest.raises(shared.VersionMismatch):
        shared.atomic_save_deal(stale, expected_version=1)


def test_save_deal_wraps_atomic_save(deals_in_tmp):
    from auth import User
    ada = User(email="ada@example.com")
    deal = shared.load_deal("Acme")
    deal["owner_email"] = ada.email
    shared.save_deal(deal, ada)
    reloaded = shared.load_deal("Acme")
    assert reloaded["_version"] == 1


def test_updated_at_is_stamped_on_save(deals_in_tmp):
    deal = shared.load_deal("Acme")
    before = deal["updated_at"]
    shared.atomic_save_deal(deal)
    assert deal["updated_at"] != before or deal["_version"] == 1
