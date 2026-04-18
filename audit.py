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
