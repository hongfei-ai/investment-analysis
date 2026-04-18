"""
audit.py — Append-only audit trail per deal.

Writes one JSON record per line to `deals/{deal_name}.audit.jsonl` whenever
someone mutates a deal (metadata save, agent run, stage change, ownership
claim). Pure stdlib; no Streamlit or API dependencies.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import shared


def _audit_path(deal_name: str) -> Path:
    name = shared._safe_deal_name(deal_name)
    return shared.DEALS_DIR / f"{name}.audit.jsonl"


def append_audit(
    deal_name: str,
    actor: str,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Append one audit record. Always stamps a UTC ISO-8601 timestamp."""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "details": details or {},
    }
    path = _audit_path(deal_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def read_audit(deal_name: str) -> list[dict[str, Any]]:
    """Return audit records in append order (oldest first), or [] if none."""
    path = _audit_path(deal_name)
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def read_activity(deal_name: str) -> list[dict[str, Any]]:
    """Merge audit entries and agent runs, newest first.

    Returns a list of uniform dicts with keys: ts, kind ("audit"|"run"),
    actor, action, details. This is the single source the UI reads to
    render the activity feed.
    """
    entries: list[dict[str, Any]] = []
    for r in read_audit(deal_name):
        entries.append({
            "ts":      r.get("ts", ""),
            "kind":    "audit",
            "actor":   r.get("actor") or "",
            "action":  r.get("action") or "",
            "details": r.get("details") or {},
        })

    for r in shared.read_runs(deal_name):
        entries.append({
            "ts":      r.get("ts") or r.get("started_at") or "",
            "kind":    "run",
            "actor":   r.get("by_user") or "",
            "action":  f"agent_run:{r.get('status', '?')}",
            "details": {
                "agent_key": r.get("agent_key"),
                "started_at": r.get("started_at"),
                "ended_at":   r.get("ended_at"),
            },
        })

    entries.sort(key=lambda e: e.get("ts") or "", reverse=True)
    return entries
