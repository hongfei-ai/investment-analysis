"""
Slack outbound notifications.

Pure push via an incoming-webhook URL. No slash commands, no bot user,
no signature verification — those are Phase 2. This module stays ~20
LOC and has exactly one job: "agent finished, post a short message."
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

log = logging.getLogger(__name__)

_AGENT_LABELS = {
    "agent1_precall":            "Agent 1: Pre-Call",
    "agent2_diligence_mgmt":     "Agent 2: Diligence Mgmt",
    "agent3_founder_diligence":  "Agent 3: Founder",
    "agent4_market_diligence":   "Agent 4: Market",
    "agent5_reference_check":    "Agent 5: Traction",
    "agent6_thesis_check":       "Agent 6: Thesis",
    "agent7_premortem":          "Agent 7: Pre-mortem",
    "agent8_ic_simulation":      "Agent 8: IC Sim",
    "agent9_ic_memo":            "Agent 9: IC Memo",
}


def _webhook_url() -> str:
    return os.environ.get("SLACK_WEBHOOK_URL", "").strip()


def _post(payload: dict[str, Any]) -> None:
    url = _webhook_url()
    if not url:
        return
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code // 100 != 2:
            log.warning("slack_push: %s returned %s: %s", url, resp.status_code, resp.text[:200])
    except requests.RequestException as e:
        log.warning("slack_push: network error posting to Slack: %s", e)


def notify_agent_done(deal_name: str, agent_key: str, duration_seconds: float) -> None:
    label = _AGENT_LABELS.get(agent_key, agent_key)
    mins = duration_seconds / 60.0
    _post({
        "text": f"✓ {label} finished for *{deal_name}* ({mins:.1f} min)",
    })


def notify_agent_failed(deal_name: str, agent_key: str, error: str) -> None:
    label = _AGENT_LABELS.get(agent_key, agent_key)
    snippet = error[:300] + ("…" if len(error) > 300 else "")
    _post({
        "text": f"✗ {label} failed for *{deal_name}*: {snippet}",
    })
