"""Unit tests for integrations.notion_push.

Focused on the pure helpers: markdown-to-blocks conversion and deal-property
mapping. Network-dependent paths (create_page, update_page, etc.) are
covered indirectly via the poller tests using a stub client.
"""

from __future__ import annotations

import pytest

from integrations import notion_push as np


# ─── markdown_to_blocks ─────────────────────────────────────────────────────

def test_empty_markdown_returns_no_blocks():
    assert np.markdown_to_blocks("") == []
    assert np.markdown_to_blocks("   \n\n  ") == []


def test_plain_paragraph():
    blocks = np.markdown_to_blocks("Hello world.")
    assert len(blocks) == 1
    assert blocks[0]["type"] == "paragraph"
    assert blocks[0]["paragraph"]["rich_text"][0]["text"]["content"] == "Hello world."


def test_headings_h1_h2_h3():
    md = "# Title\n## Section\n### Subsection"
    blocks = np.markdown_to_blocks(md)
    types = [b["type"] for b in blocks]
    assert types == ["heading_1", "heading_2", "heading_3"]


def test_bullets_and_numbered_lists():
    md = "- alpha\n- beta\n\n1. one\n2. two"
    blocks = np.markdown_to_blocks(md)
    types = [b["type"] for b in blocks]
    assert types == [
        "bulleted_list_item", "bulleted_list_item",
        "numbered_list_item", "numbered_list_item",
    ]


def test_fenced_code_block_preserved_verbatim():
    md = "```python\nx = 1\ny = 2\n```"
    blocks = np.markdown_to_blocks(md)
    assert len(blocks) == 1
    assert blocks[0]["type"] == "code"
    assert blocks[0]["code"]["language"] == "python"
    text = blocks[0]["code"]["rich_text"][0]["text"]["content"]
    assert text == "x = 1\ny = 2"


def test_long_paragraph_splits_into_chunks():
    long_text = "word " * 500  # ~2500 chars
    blocks = np.markdown_to_blocks(long_text.strip())
    assert len(blocks) == 1
    chunks = blocks[0]["paragraph"]["rich_text"]
    assert len(chunks) >= 2
    for chunk in chunks:
        assert len(chunk["text"]["content"]) <= np._NOTION_RICH_TEXT_LIMIT


def test_mixed_content_round_trip_order():
    md = "# Top\n\nIntro paragraph.\n\n## Section A\n\n- first\n- second\n\nCloser."
    blocks = np.markdown_to_blocks(md)
    types = [b["type"] for b in blocks]
    assert types == [
        "heading_1", "paragraph", "heading_2",
        "bulleted_list_item", "bulleted_list_item", "paragraph",
    ]


# ─── Property builders ──────────────────────────────────────────────────────

def test_build_deal_properties_extracts_inputs():
    deal = {
        "deal_id": "Acme",
        "company_name": "Acme",
        "deal_stage": "diligence",
        "priority": "H",
        "next_step": "Call founder",
        "inputs": {
            "founder_name": "Ada Lovelace",
            "founder_linkedin": "https://linkedin.com/in/ada",
            "company_website": "https://acme.com",
        },
    }
    props = np._build_deal_properties(deal)
    assert props["Company Name"]["title"][0]["text"]["content"] == "Acme"
    assert props["Deal Stage"]["select"]["name"] == "diligence"
    assert props["Priority"]["select"]["name"] == "H"
    assert props["Founder Name"]["rich_text"][0]["text"]["content"] == "Ada Lovelace"
    assert props["Founder LinkedIn"]["url"] == "https://linkedin.com/in/ada"


def test_build_deal_properties_handles_missing_optional_fields():
    deal = {"deal_id": "Bare", "company_name": "Bare", "inputs": {}}
    props = np._build_deal_properties(deal)
    assert props["Deal Stage"]["select"] is None
    assert props["Priority"]["select"] is None
    assert props["Founder LinkedIn"]["url"] is None
    assert props["Notes"]["rich_text"] == []


# ─── Gating ──────────────────────────────────────────────────────────────────

def test_all_public_writes_are_noops_when_disabled(monkeypatch):
    """Every public push fn must return cleanly without touching the network
    when NOTION_ENABLED is false."""
    monkeypatch.delenv("NOTION_ENABLED", raising=False)

    def explode(*a, **kw):
        raise AssertionError("Notion API must not be called when disabled")

    # Poison the client so any call would blow up
    for name in ("query_db", "retrieve_page", "update_page", "create_page",
                 "append_blocks", "retrieve_user"):
        monkeypatch.setattr(f"integrations.notion_client.{name}", explode)

    # None of these should raise
    np.push_deal_metadata({"deal_id": "X", "company_name": "X", "inputs": {}})
    np.set_deal_status("X", "Done")
    np.record_deal_error("X", "boom")
    np.clear_deal_error("X")
    np.mark_agent_done("X", "agent1_precall")
    np.create_output_page("X", "page", "agent1_precall", None, "2026-04-25T10:00:00Z")
    np.finalize_output_page("page", "# hi", 1.0)
    np.fail_output_page("page", "boom")
    np.append_heartbeat("page", "tick")
