"""
Migration 001: add multi-user + pipeline-stage fields to existing deals.

Idempotent and lazy — called from `shared.load_deal` every time a deal is
read. Only populates missing fields; never overwrites existing values.

Design notes:
- `owner_email` defaults to the existing `inputs.deal_champion` string if
  present, else `"unassigned"`. A human name in `deal_champion` is not a
  valid email, so most deals will resolve to `"unassigned"` and surface a
  Claim button on the dashboard (wired in M5).
- `deal_stage` is derived from the existing `status` field via a simple
  mapping. Unknown statuses fall back to `contacted`.
- `status` itself is NOT renamed — it remains the agent-pipeline phase.
  The new `deal_stage` captures the orthogonal business state.
- `updated_at` uses `date_created` as the best-available stand-in; the
  next save_deal call will stamp it fresh.
"""

from __future__ import annotations

from datetime import datetime, timezone

_STATUS_TO_STAGE = {
    "pre-call": "contacted",
    "diligence": "diligence",
    "post-diligence": "diligence",
    "ic-prep": "ic",
    "complete": "ic",
}


def migrate(deal: dict) -> dict:
    """Ensure all multi-user fields are present. Idempotent. Mutates + returns."""
    status = deal.get("status", "pre-call")

    deal.setdefault(
        "owner_email",
        (deal.get("inputs") or {}).get("deal_champion") or "unassigned",
    )
    deal.setdefault("collaborators", [])
    deal.setdefault("created_by", None)
    deal.setdefault("_version", 0)
    deal.setdefault(
        "updated_at",
        deal.get("date_created") or datetime.now(timezone.utc).isoformat(),
    )

    deal.setdefault("deal_stage", _STATUS_TO_STAGE.get(status, "contacted"))

    for k in (
        "priority",
        "round_size",
        "check_size",
        "valuation",
        "sector",
        "geography",
        "next_step",
        "next_step_due",
    ):
        deal.setdefault(k, None)

    return deal
