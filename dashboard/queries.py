"""
dashboard/queries.py — Pure-Python read path for the team dashboard.

Functions here scan `deals/*.json`, produce compact per-deal summaries,
and compose filters / aggregates. No Streamlit imports, no network calls,
no writes. All functions are unit-testable with a monkeypatched DEALS_DIR.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import shared


# Canonical agent ordering — index determines the "X/9" progress fraction
# and the UI ordering of the agents-done tooltip.
AGENT_SEQUENCE: list[tuple[str, tuple[str, ...]]] = [
    ("agent1_precall",           ("pre_call", "research_output")),
    ("agent2_diligence_mgmt",    ("diligence", "tracker")),
    ("agent3_founder",           ("diligence", "founder_diligence")),
    ("agent4_market",            ("diligence", "market_diligence")),
    ("agent5_traction",          ("diligence", "reference_check")),
    ("agent6_thesis",            ("diligence", "thesis_check")),
    ("agent7_premortem",         ("ic_preparation", "pre_mortem")),
    ("agent8_ic_simulation",     ("ic_preparation", "ic_simulation")),
    ("agent9_ic_memo",           ("ic_preparation", "ic_memo")),
]

TERMINAL_STAGES = frozenset({"passed", "tracking", "invested"})

# Agent 6's final section reads `### 7. Thesis Fit Verdict (Strong / Moderate / Weak / No Fit)`
# — that header itself contains all four labels inside its parenthetical option
# list, so we deliberately skip it and look for a subsequent `Verdict: <word>`
# or `**Verdict:** <word>` pattern in the body. Matches: "Verdict: Moderate",
# "**Verdict: Moderate**", "Verdict: **No Fit**".
_VERDICT_RE = re.compile(
    r"Verdict[\s:]*[*_]*\s*(Strong|Moderate|Weak|No\s*Fit)\b",
    re.IGNORECASE,
)


@dataclass
class DealSummary:
    deal_id: str
    company_name: str
    owner_email: str
    collaborators: list[str] = field(default_factory=list)
    created_by: str | None = None
    date_created: str = ""
    updated_at: str = ""
    version: int = 0
    deal_stage: str = "contacted"
    status: str = "pre-call"
    is_active: bool = True
    priority: str | None = None
    round_size: str | None = None
    check_size: str | None = None
    valuation: str | None = None
    sector: str | None = None
    geography: str | None = None
    next_step: str | None = None
    next_step_due: str | None = None
    agents_done: int = 0
    agents_total: int = len(AGENT_SEQUENCE)
    agents_done_keys: list[str] = field(default_factory=list)
    thesis_verdict: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.deal_stage in TERMINAL_STAGES


def _is_nonempty(value) -> bool:
    """Treat '', {}, [], None as 'agent did not run'; strings of text as 'done'."""
    if value is None:
        return False
    if isinstance(value, (str, list, dict, tuple, set)):
        return len(value) > 0
    return True


def agent_progress(deal: dict) -> tuple[int, int, list[str]]:
    """Return (done, total, done_keys) for the standard 9-agent pipeline."""
    done_keys: list[str] = []
    for agent_key, (section, field_name) in AGENT_SEQUENCE:
        section_data = deal.get(section) or {}
        if _is_nonempty(section_data.get(field_name)):
            done_keys.append(agent_key)
    return len(done_keys), len(AGENT_SEQUENCE), done_keys


def thesis_verdict(deal: dict) -> str | None:
    """Parse Agent 6's verdict from the thesis_check output, or None."""
    raw = (deal.get("diligence") or {}).get("thesis_check")
    if not _is_nonempty(raw):
        return None
    text = raw if isinstance(raw, str) else str(raw)
    m = _VERDICT_RE.search(text)
    if not m:
        return None
    v = re.sub(r"\s+", " ", m.group(1).strip()).title()
    if v.lower() == "no fit":
        return "No Fit"
    return v


def _summary_from_deal(deal: dict) -> DealSummary:
    done, total, done_keys = agent_progress(deal)
    return DealSummary(
        deal_id=deal.get("deal_id", ""),
        company_name=deal.get("company_name", deal.get("deal_id", "")),
        owner_email=deal.get("owner_email", "unassigned") or "unassigned",
        collaborators=list(deal.get("collaborators") or []),
        created_by=deal.get("created_by"),
        date_created=deal.get("date_created", ""),
        updated_at=deal.get("updated_at", "") or deal.get("date_created", ""),
        version=int(deal.get("_version", 0) or 0),
        deal_stage=deal.get("deal_stage", "contacted") or "contacted",
        status=deal.get("status", "pre-call") or "pre-call",
        is_active=bool(deal.get("is_active", True)),
        priority=deal.get("priority"),
        round_size=deal.get("round_size"),
        check_size=deal.get("check_size"),
        valuation=deal.get("valuation"),
        sector=deal.get("sector"),
        geography=deal.get("geography"),
        next_step=deal.get("next_step"),
        next_step_due=deal.get("next_step_due"),
        agents_done=done,
        agents_total=total,
        agents_done_keys=done_keys,
        thesis_verdict=thesis_verdict(deal),
    )


def scan_deals() -> list[DealSummary]:
    """Load every deal JSON in DEALS_DIR and return summary records.

    Non-deal files (*.runs.jsonl, *.audit.jsonl, hidden files) are skipped.
    Files that fail to parse are skipped silently — the dashboard must not
    fall over on one corrupt deal.
    """
    deals_dir: Path = shared.DEALS_DIR
    if not deals_dir.exists():
        return []

    summaries: list[DealSummary] = []
    for path in sorted(deals_dir.glob("*.json")):
        if path.name.startswith("."):
            continue
        try:
            deal = shared.load_deal(path.stem)
        except Exception:
            continue
        summaries.append(_summary_from_deal(deal))
    return summaries


def _iso_to_datetime(iso_str: str) -> datetime | None:
    """Parse an ISO-8601 timestamp to a tz-aware datetime; None on failure."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def days_since_activity(summary: DealSummary, now: datetime | None = None) -> float | None:
    """Days elapsed since `updated_at`. None if timestamp is missing/unparseable."""
    dt = _iso_to_datetime(summary.updated_at)
    if dt is None:
        return None
    ref = now or datetime.now(timezone.utc)
    if ref.tzinfo is None:
        ref = ref.replace(tzinfo=timezone.utc)
    return (ref - dt).total_seconds() / 86400.0


def stalled_deals(
    summaries: Iterable[DealSummary],
    threshold_days: int = 14,
    now: datetime | None = None,
) -> list[DealSummary]:
    """Deals with no activity for > threshold_days, excluding terminal stages."""
    out: list[DealSummary] = []
    for s in summaries:
        if s.is_terminal:
            continue
        days = days_since_activity(s, now=now)
        if days is not None and days > threshold_days:
            out.append(s)
    return out


def filter_deals(
    summaries: Iterable[DealSummary],
    *,
    owner_email: str | None = None,
    my_email: str | None = None,
    active_only: bool = False,
) -> list[DealSummary]:
    """Apply dashboard filters to a list of DealSummary.

    `owner_email` matches deals whose owner is that email (case-insensitive).
    `my_email` is the "My deals" filter: owner OR collaborator.
    `active_only` keeps only deals with is_active=True.
    """
    owner_lc = owner_email.lower() if owner_email else None
    my_lc = my_email.lower() if my_email else None

    out: list[DealSummary] = []
    for s in summaries:
        if active_only and not s.is_active:
            continue
        if owner_lc and (s.owner_email or "").lower() != owner_lc:
            continue
        if my_lc:
            collaborators_lc = {c.lower() for c in s.collaborators}
            if (s.owner_email or "").lower() != my_lc and my_lc not in collaborators_lc:
                continue
        out.append(s)
    return out


def summary_tiles(summaries: Iterable[DealSummary]) -> dict:
    """Aggregate counts for the top-of-dashboard tile row.

    Returns a dict with two keys:
      total_deals      — every deal in DEALS_DIR, regardless of stage
      total_agents_run — sum of agents_done across all deals
    """
    summaries = list(summaries)
    return {
        "total_deals": len(summaries),
        "total_agents_run": sum(s.agents_done for s in summaries),
    }
