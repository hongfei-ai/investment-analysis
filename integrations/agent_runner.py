"""
Headless agent runner.

One function per agent invocation, plus phase-level orchestrators. Reuses
`shared.py` / `agents/` / `auth.py` directly — no Streamlit dependency.
All post-save bookkeeping (status transitions, technical-diligence-required
flag parsing, status promotion to post-diligence/complete) happens here,
inline, so `pages/deal.py`'s versions don't need to change.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from typing import Any

from auth import User, is_editor
from shared import (
    MODEL_SONNET,
    call_claude,
    load_deal,
    parse_technical_diligence_required,
    record_run,
    save_deal,
    save_output,
)

from agents.agent1_precall import AGENT1_TOOLS, AGENT1_MAX_TOKENS
from agents.agent4_market import AGENT4_TOOLS, AGENT4_MAX_TOKENS
from agents.prompts import (
    AGENT1_SYSTEM, agent1_user,
    AGENT2_SYSTEM, agent2_user,
    AGENT3_SYSTEM, agent3_user,
    AGENT4_SYSTEM, agent4_user,
    AGENT5_SYSTEM, agent5_user,
    AGENT6_SYSTEM, agent6_user,
    AGENT7_SYSTEM, agent7_user,
    AGENT8_SYSTEM, agent8_user,
    AGENT9_SYSTEM, agent9_user,
)

from integrations import notion_push, slack_push


log = logging.getLogger(__name__)


# ─── Agent configuration ─────────────────────────────────────────────────────
# Headless-only view of the registry. Fields are intentionally a subset of
# pages/deal.py::AGENT_REGISTRY — no UI-specific labels or streaming flags.

AGENT_CONFIG: dict[str, dict] = {
    "agent1_precall": {
        "system": AGENT1_SYSTEM, "user_fn": agent1_user,
        "section": "pre_call", "field": "research_output",
        "max_tokens": AGENT1_MAX_TOKENS, "tools": AGENT1_TOOLS,
    },
    "agent2_diligence_mgmt": {
        "system": AGENT2_SYSTEM, "user_fn": agent2_user,
        "section": "diligence", "field": "tracker",
        "max_tokens": 8000, "model": MODEL_SONNET,
    },
    "agent3_founder_diligence": {
        "system": AGENT3_SYSTEM, "user_fn": agent3_user,
        "section": "diligence", "field": "founder_diligence",
        "max_tokens": 16000,
    },
    "agent4_market_diligence": {
        "system": AGENT4_SYSTEM, "user_fn": agent4_user,
        "section": "diligence", "field": "market_diligence",
        "max_tokens": AGENT4_MAX_TOKENS, "tools": AGENT4_TOOLS,
    },
    "agent5_reference_check": {
        "system": AGENT5_SYSTEM, "user_fn": agent5_user,
        "section": "diligence", "field": "reference_check",
        "max_tokens": 8000, "model": MODEL_SONNET,
    },
    "agent6_thesis_check": {
        "system": AGENT6_SYSTEM, "user_fn": agent6_user,
        "section": "diligence", "field": "thesis_check",
        "max_tokens": 8000, "model": MODEL_SONNET,
    },
    "agent7_premortem": {
        "system": AGENT7_SYSTEM, "user_fn": agent7_user,
        "section": "ic_preparation", "field": "pre_mortem",
        "max_tokens": 8000, "model": MODEL_SONNET,
    },
    "agent8_ic_simulation": {
        "system": AGENT8_SYSTEM, "user_fn": agent8_user,
        "section": "ic_preparation", "field": "ic_simulation",
        "max_tokens": 8000, "model": MODEL_SONNET,
    },
    "agent9_ic_memo": {
        "system": AGENT9_SYSTEM, "user_fn": agent9_user,
        "section": "ic_preparation", "field": "ic_memo",
        "max_tokens": 12000,
    },
}


# Maps Notion "Run Agent" select option → agent key (or list for phases).
SHORT_KEY_TO_AGENT: dict[str, str] = {
    "A1": "agent1_precall",
    "A2": "agent2_diligence_mgmt",
    "A3": "agent3_founder_diligence",
    "A4": "agent4_market_diligence",
    "A5": "agent5_reference_check",
    "A6": "agent6_thesis_check",
    "A7": "agent7_premortem",
    "A8": "agent8_ic_simulation",
    "A9": "agent9_ic_memo",
}

PHASE_TO_AGENTS: dict[str, list[str]] = {
    "Phase 1": ["agent1_precall"],
    "Phase 2": [
        "agent2_diligence_mgmt",
        "agent3_founder_diligence",
        "agent4_market_diligence",
        "agent5_reference_check",
        "agent6_thesis_check",
    ],
    "Phase 3": [
        "agent7_premortem",
        "agent8_ic_simulation",
        "agent9_ic_memo",
    ],
}


# ─── Post-save hooks (inlined from pages/deal.py) ────────────────────────────

def _apply_post_save(agent_key: str, deal_name: str, output: str, user: User) -> None:
    """Per-agent post-save bookkeeping. Mirrors pages/deal.py post_save hooks."""
    if agent_key == "agent2_diligence_mgmt":
        deal = load_deal(deal_name)
        deal["diligence"]["technical_diligence_required"] = (
            parse_technical_diligence_required(output)
        )
        save_deal(deal, user)
        return

    if agent_key == "agent6_thesis_check":
        deal = load_deal(deal_name)
        dil = deal["diligence"]
        all_done = all(
            isinstance(dil.get(f), str) and dil[f].strip()
            for f in ("tracker", "founder_diligence", "market_diligence",
                      "reference_check", "thesis_check")
        )
        if all_done:
            deal["status"] = "post-diligence"
            save_deal(deal, user)
        return

    if agent_key == "agent9_ic_memo":
        deal = load_deal(deal_name)
        deal["status"] = "complete"
        save_deal(deal, user)
        return


# ─── Core runner ─────────────────────────────────────────────────────────────

def run_agent(
    deal_name: str,
    agent_key: str,
    user: User,
    *,
    output_page_id: str | None = None,
) -> tuple[bool, str]:
    """Execute one agent end-to-end. Returns (success, output_or_error).

    Writes to filesystem first (source of truth), then mirrors to Notion.
    Records a runs.jsonl entry in both the started and the terminal state.
    """
    cfg = AGENT_CONFIG.get(agent_key)
    if cfg is None:
        return False, f"Unknown agent_key: {agent_key!r}"

    started = datetime.now(timezone.utc).isoformat()
    record_run(deal_name, agent_key, "running", user.email, started_at=started)

    if output_page_id:
        notion_push.append_heartbeat(
            output_page_id,
            f"Calling Claude ({cfg.get('model') or 'opus'}, "
            f"max_tokens={cfg['max_tokens']}, tools={'yes' if cfg.get('tools') else 'no'})",
        )

    t0 = time.time()
    try:
        deal = load_deal(deal_name)
        output = call_claude(
            cfg["system"],
            cfg["user_fn"](deal),
            max_tokens=cfg["max_tokens"],
            tools=cfg.get("tools"),
            model=cfg.get("model"),
        )
    except Exception as e:
        ended = datetime.now(timezone.utc).isoformat()
        record_run(deal_name, agent_key, "error", user.email,
                   started_at=started, ended_at=ended)
        log.exception("run_agent failed: deal=%s agent=%s", deal_name, agent_key)
        slack_push.notify_agent_failed(deal_name, agent_key, str(e))
        return False, str(e)

    duration = time.time() - t0

    try:
        deal[cfg["section"]][cfg["field"]] = output
        save_deal(deal, user)
        save_output(deal_name, agent_key, output, user)
        _apply_post_save(agent_key, deal_name, output, user)
    except Exception as e:
        ended = datetime.now(timezone.utc).isoformat()
        record_run(deal_name, agent_key, "error", user.email,
                   started_at=started, ended_at=ended)
        log.exception("run_agent save-path failed: deal=%s agent=%s", deal_name, agent_key)
        slack_push.notify_agent_failed(deal_name, agent_key, f"Save failed: {e}")
        return False, f"Save failed: {e}"

    ended = datetime.now(timezone.utc).isoformat()
    record_run(deal_name, agent_key, "done", user.email,
               started_at=started, ended_at=ended)

    if output_page_id:
        notion_push.finalize_output_page(output_page_id, output, duration)
    notion_push.mark_agent_done(deal_name, agent_key)
    notion_push.push_deal_metadata(load_deal(deal_name))

    slack_push.notify_agent_done(deal_name, agent_key, duration)

    return True, output


def run_phase(deal_name: str, phase_label: str, user: User) -> tuple[bool, str]:
    """Run a full phase. Sequential — no concurrency for MVP simplicity."""
    agent_keys = PHASE_TO_AGENTS.get(phase_label, [])
    if not agent_keys:
        return False, f"Unknown phase: {phase_label!r}"

    failures: list[str] = []
    for key in agent_keys:
        ok, msg = run_agent(deal_name, key, user)
        if not ok:
            failures.append(f"{key}: {msg}")
            break  # stop on first failure; downstream agents depend on upstream output

    if failures:
        return False, "; ".join(failures)
    return True, f"{phase_label} complete: {len(agent_keys)} agents"


def resolve_trigger(short_key: str) -> tuple[str, list[str]]:
    """Map a Notion 'Run Agent' option to (kind, agent_keys).

    kind is "agent" for single-agent triggers and "phase" for phase-level.
    """
    if short_key in SHORT_KEY_TO_AGENT:
        return "agent", [SHORT_KEY_TO_AGENT[short_key]]
    if short_key in PHASE_TO_AGENTS:
        return "phase", list(PHASE_TO_AGENTS[short_key])
    return "unknown", []


def authorized(deal_name: str, user: User) -> bool:
    """Pre-flight auth check — mirrors `require_editor` but returns bool."""
    deal = load_deal(deal_name)
    return is_editor(deal, user)
