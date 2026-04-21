"""
One-shot Notion bootstrap.

Creates the Deals and Agent Outputs databases under a given parent page,
with the schema the poller expects. Run this once per Notion workspace,
then capture the returned database IDs into `.streamlit/secrets.toml`:

    NOTION_DEALS_DB_ID    = "..."
    NOTION_OUTPUTS_DB_ID  = "..."

Usage:

    # Prerequisites: share a Notion page with the integration, grab its ID
    export NOTION_TOKEN=secret_xxx
    python -m integrations.bootstrap_notion --parent-page-id <PAGE_ID>

The parent page must be shared with the integration. Subsequent runs are
no-ops (you can safely delete the created databases and re-run).
"""

from __future__ import annotations

import argparse
import sys

from integrations import notion_client as nc


_DEAL_STAGES = [
    "sourced", "contacted", "met", "diligence",
    "ic", "term_sheet", "invested", "passed", "tracking",
]
_PRIORITIES = ["H", "M", "L"]
_AGENT_KEYS = [
    "agent1_precall", "agent2_diligence_mgmt", "agent3_founder_diligence",
    "agent4_market_diligence", "agent5_reference_check", "agent6_thesis_check",
    "agent7_premortem", "agent8_ic_simulation", "agent9_ic_memo",
]
_RUN_AGENT_OPTIONS = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9",
                      "Phase 1", "Phase 2", "Phase 3"]
_AGENT_PROGRESS_TAGS = [f"{k} ✓" for k in ("A1", "A2", "A3", "A4", "A5",
                                            "A6", "A7", "A8", "A9")]


def _select(options: list[str]) -> dict:
    return {"select": {"options": [{"name": o} for o in options]}}


def _multi_select(options: list[str]) -> dict:
    return {"multi_select": {"options": [{"name": o} for o in options]}}


def _text() -> dict:
    return {"rich_text": {}}


def _url() -> dict:
    return {"url": {}}


def _number() -> dict:
    return {"number": {"format": "number"}}


def _date() -> dict:
    return {"date": {}}


def _person() -> dict:
    return {"people": {}}


def _files() -> dict:
    return {"files": {}}


def _title(name: str) -> list[dict]:
    return [{"type": "text", "text": {"content": name}}]


def _deals_properties() -> dict:
    return {
        "Company Name":    {"title": {}},
        "Owner":           _person(),
        "Collaborators":   _person(),
        "Deal Stage":      _select(_DEAL_STAGES),
        "Priority":        _select(_PRIORITIES),
        "Next Step":       _text(),
        "Notes":           _text(),
        "Founder Name":    _text(),
        "Founder LinkedIn": _url(),
        "Company Website": _url(),
        "Intro Source":    _text(),
        "Intro Context":   _text(),
        "Initial Notes":   _text(),
        "Pitch Deck":      _files(),
        "Run Agent":       _select(_RUN_AGENT_OPTIONS),
        "Status":          _select([
            "Idle",
            "Running", "Running: A1", "Running: A2", "Running: A3",
            "Running: A4", "Running: A5", "Running: A6",
            "Running: A7", "Running: A8", "Running: A9",
            "Running: Phase 1", "Running: Phase 2", "Running: Phase 3",
            "Done", "Failed",
        ]),
        "Last Error":      _text(),
        "Agent Progress":  _multi_select(_AGENT_PROGRESS_TAGS),
    }


def _outputs_properties(deals_db_id: str) -> dict:
    return {
        "Title":      {"title": {}},
        "Deal":       {"relation": {"database_id": deals_db_id,
                                     "single_property": {}}},
        "Agent Key":  _select(_AGENT_KEYS),
        "Status":     _select(["Running", "Done", "Failed"]),
        "Run By":     _person(),
        "Started":    _date(),
        "Duration (s)": _number(),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--parent-page-id", required=True,
                    help="Notion page ID that the integration has access to "
                         "(strip hyphens). The two DBs will be created as children.")
    args = ap.parse_args()

    if not nc.is_enabled():
        print("WARNING: NOTION_ENABLED is not 'true'. Bootstrap will still "
              "proceed since this is a one-shot admin script.", file=sys.stderr)

    parent = {"type": "page_id", "page_id": args.parent_page_id}

    print("Creating Deals database...")
    deals_db = nc.create_database(
        parent=parent,
        title=_title("Deals"),
        properties=_deals_properties(),
    )
    deals_db_id = deals_db["id"]
    print(f"  ✓ Deals DB id: {deals_db_id}")

    print("Creating Agent Outputs database...")
    outputs_db = nc.create_database(
        parent=parent,
        title=_title("Agent Outputs"),
        properties=_outputs_properties(deals_db_id),
    )
    outputs_db_id = outputs_db["id"]
    print(f"  ✓ Outputs DB id: {outputs_db_id}")

    print()
    print("Add these to .streamlit/secrets.toml:")
    print()
    print(f'NOTION_DEALS_DB_ID   = "{deals_db_id}"')
    print(f'NOTION_OUTPUTS_DB_ID = "{outputs_db_id}"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
