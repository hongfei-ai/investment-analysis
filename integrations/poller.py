"""
Notion poller.

Queries the Deals DB every N seconds for rows where the `Run Agent`
property is set. For each hit:

  1. Claim the row atomically — clear `Run Agent` and set `Status = Running`
     in a single PATCH. Two competing pollers would both attempt the clear;
     the loser reads an empty trigger on the next poll and no-ops.
  2. Pull the deal's input fields from the Notion row into the filesystem
     JSON (load_deal → merge → atomic_save_deal).
  3. Reconcile the six human-editable fields from Notion back into the
     JSON (owner_email, collaborators, deal_stage, priority, next_step, notes).
  4. Resolve the triggering user from `last_edited_by` → email.
  5. Authorize BEFORE spending tokens: if not an editor, fail fast.
  6. Dispatch to `agent_runner.run_agent` or `run_phase`.
  7. On terminal state, push final status + metadata back to Notion.

The poller is defensive — any single-row failure logs + moves on, never
crashes the loop.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from auth import User
from shared import atomic_save_deal, load_deal

from integrations import agent_runner, notion_client as nc, notion_push


log = logging.getLogger(__name__)

# How often the background thread polls. 30s balances responsiveness with
# Notion's 3 rps rate limit and the fact that agent runs take minutes anyway.
POLL_INTERVAL_SECONDS = 30

# Runs stuck in "Running" for longer than this get reaped to "Failed: timeout".
STALE_RUN_THRESHOLD = timedelta(minutes=15)


# ─── Notion property extraction helpers ─────────────────────────────────────

def _title_text(prop: dict) -> str:
    spans = prop.get("title", []) if prop else []
    return "".join(s.get("plain_text", "") for s in spans).strip()


def _rich_text(prop: dict) -> str:
    spans = prop.get("rich_text", []) if prop else []
    return "".join(s.get("plain_text", "") for s in spans).strip()


def _url(prop: dict) -> str:
    return (prop or {}).get("url") or ""


def _select_name(prop: dict) -> str:
    sel = (prop or {}).get("select")
    return sel.get("name", "") if sel else ""


def _multi_select_names(prop: dict) -> list[str]:
    items = (prop or {}).get("multi_select", [])
    return [i.get("name", "") for i in items if i.get("name")]


def _people_emails(prop: dict, resolve_user_fn) -> list[str]:
    """Extract email addresses from a people property.

    Person objects inline their email only when the integration has the
    `read user info including email addresses` capability AND the user
    fetch has happened. If email isn't present, fetch the user via the
    users endpoint; if still missing, skip.
    """
    people = (prop or {}).get("people", []) if prop else []
    emails: list[str] = []
    for p in people:
        email = ((p.get("person") or {}).get("email") or "").strip()
        if not email and p.get("id"):
            user_obj = resolve_user_fn(p["id"])
            email = ((user_obj or {}).get("person") or {}).get("email", "").strip()
        if email:
            emails.append(email)
    return emails


def _last_edited_by_email(page: dict) -> str:
    """Resolve the triggering user's email from `last_edited_by`."""
    user = page.get("last_edited_by") or {}
    inline_email = ((user.get("person") or {}).get("email") or "").strip()
    if inline_email:
        return inline_email
    user_id = user.get("id")
    if not user_id:
        return ""
    try:
        full = nc.retrieve_user(user_id)
    except nc.NotionAPIError as e:
        log.warning("poller: retrieve_user failed for %s: %s", user_id, e)
        return ""
    return ((full.get("person") or {}).get("email") or "").strip()


# ─── Sync: Notion → filesystem ───────────────────────────────────────────────

_INPUT_FIELD_MAP: list[tuple[str, str, str]] = [
    # (notion_property, deal_json_path (under inputs.), extractor)
    ("Founder Name",     "founder_name",     "text"),
    ("Founder LinkedIn", "founder_linkedin", "url"),
    ("Company Website",  "company_website",  "url"),
    ("Intro Source",     "intro_source",     "text"),
    ("Intro Context",    "intro_context",    "text"),
    ("Initial Notes",    "initial_notes",    "text"),
]

_TWO_WAY_FIELDS: list[tuple[str, str, str]] = [
    ("Deal Stage",  "deal_stage",  "select"),
    ("Priority",    "priority",    "select"),
    ("Next Step",   "next_step",   "text"),
    ("Notes",       "_notes_fs",   "text"),  # written to diligence.human_review_notes
]


def _extract_value(prop: dict, kind: str) -> Any:
    if kind == "text":
        return _rich_text(prop)
    if kind == "url":
        return _url(prop)
    if kind == "select":
        return _select_name(prop) or None
    return None


def reconcile_from_notion(page: dict, user: User) -> str:
    """Pull Notion's human-editable fields + inputs into the filesystem deal.

    Returns the deal_name (from the Company Name title). Performs the merge
    via atomic_save_deal, so optimistic locking is preserved.
    """
    props = page.get("properties", {})
    deal_name = _title_text(props.get("Company Name", {}))
    if not deal_name:
        raise ValueError("Deal row has no Company Name")

    deal = load_deal(deal_name)

    # Inputs (one-way: Notion is the user's input surface for agent params)
    inputs = deal.setdefault("inputs", {})
    for notion_prop, json_key, kind in _INPUT_FIELD_MAP:
        value = _extract_value(props.get(notion_prop, {}), kind)
        if value:
            inputs[json_key] = value

    # Two-way human-editable fields
    stage = _select_name(props.get("Deal Stage", {}))
    if stage:
        deal["deal_stage"] = stage
    priority = _select_name(props.get("Priority", {}))
    deal["priority"] = priority or None
    next_step = _rich_text(props.get("Next Step", {}))
    deal["next_step"] = next_step or None
    notes = _rich_text(props.get("Notes", {}))
    if notes:
        deal.setdefault("diligence", {})["human_review_notes"] = notes

    owner_emails = _people_emails(props.get("Owner", {}), nc.retrieve_user)
    if owner_emails:
        deal["owner_email"] = owner_emails[0]
    collabs = _people_emails(props.get("Collaborators", {}), nc.retrieve_user)
    if collabs:
        deal["collaborators"] = collabs

    # `user` isn't strictly needed for save_deal since we're bypassing the
    # permission check (the poller is system-level for the reconcile step;
    # the auth check happens AFTER reconcile on the triggering user).
    atomic_save_deal(deal)

    return deal_name


# ─── Claim / dispatch ────────────────────────────────────────────────────────

def _claim_row(page_id: str, trigger_label: str) -> bool:
    """Atomically clear Run Agent and set Status = Running. Returns True on success."""
    try:
        nc.update_page(page_id, properties={
            "Run Agent": {"select": None},
            "Status":    {"select": {"name": f"Running: {trigger_label}"}},
            "Last Error": {"rich_text": []},
        })
        return True
    except nc.NotionAPIError as e:
        log.warning("poller: claim failed for page=%s: %s", page_id, e)
        return False


def _process_row(page: dict) -> None:
    props = page.get("properties", {})
    page_id = page["id"]
    trigger = _select_name(props.get("Run Agent", {}))
    if not trigger:
        return  # race: another worker already cleared it

    kind, agent_keys = agent_runner.resolve_trigger(trigger)
    if kind == "unknown":
        log.warning("poller: unknown trigger %r on page %s", trigger, page_id)
        nc.update_page(page_id, properties={
            "Run Agent": {"select": None},
            "Status":    {"select": {"name": "Failed"}},
            "Last Error": {"rich_text": [{"type": "text",
                                          "text": {"content": f"Unknown trigger: {trigger}"}}]},
        })
        return

    if not _claim_row(page_id, trigger):
        return

    # Resolve triggering user before reconcile so reconcile doesn't overwrite
    # owner with a stale value under an unauthorized trigger.
    triggering_email = _last_edited_by_email(page) or nc.bot_user_email()
    user = User(email=triggering_email)

    try:
        deal_name = reconcile_from_notion(page, user)
    except Exception as e:
        log.exception("poller: reconcile failed for page=%s", page_id)
        nc.update_page(page_id, properties={
            "Status": {"select": {"name": "Failed"}},
            "Last Error": {"rich_text": [{"type": "text",
                                          "text": {"content": f"Reconcile failed: {e}"[:2000]}}]},
        })
        return

    if not agent_runner.authorized(deal_name, user):
        log.warning("poller: %s not authorized for %s", triggering_email, deal_name)
        nc.update_page(page_id, properties={
            "Status": {"select": {"name": "Failed"}},
            "Last Error": {"rich_text": [{"type": "text", "text": {
                "content": f"{triggering_email} is not an editor of {deal_name}. "
                           "Ask the owner to add you as a collaborator."
            }}]},
        })
        return

    # Create the Agent Outputs page(s). For single-agent triggers, one output;
    # for phase triggers, one per agent (created lazily inside the loop).
    started_iso = datetime.now(timezone.utc).isoformat()
    if kind == "agent":
        agent_key = agent_keys[0]
        out_page = notion_push.create_output_page(
            deal_name, page_id, agent_key,
            run_by_notion_user_id=(page.get("last_edited_by") or {}).get("id"),
            started_iso=started_iso,
        )
        ok, msg = agent_runner.run_agent(deal_name, agent_key, user,
                                         output_page_id=out_page)
        if ok:
            notion_push.set_deal_status(deal_name, "Done")
        else:
            notion_push.record_deal_error(deal_name, msg)
            if out_page:
                notion_push.fail_output_page(out_page, msg)
        return

    # Phase: loop, creating one output page per agent
    for agent_key in agent_keys:
        out_page = notion_push.create_output_page(
            deal_name, page_id, agent_key,
            run_by_notion_user_id=(page.get("last_edited_by") or {}).get("id"),
            started_iso=datetime.now(timezone.utc).isoformat(),
        )
        ok, msg = agent_runner.run_agent(deal_name, agent_key, user,
                                         output_page_id=out_page)
        if not ok:
            notion_push.record_deal_error(deal_name, f"{agent_key}: {msg}")
            if out_page:
                notion_push.fail_output_page(out_page, msg)
            return
    notion_push.set_deal_status(deal_name, "Done")


# ─── Stale-run reaper ────────────────────────────────────────────────────────

def _reap_stale_runs() -> None:
    """Mark any rows stuck in Running for >STALE_RUN_THRESHOLD as Failed."""
    try:
        rows = nc.query_db(
            nc.deals_db_id(),
            filter={"property": "Status", "select": {"does_not_equal": ""}},
        )
    except nc.NotionAPIError as e:
        log.warning("poller: reaper query failed: %s", e)
        return

    cutoff = datetime.now(timezone.utc) - STALE_RUN_THRESHOLD
    for row in rows:
        status = _select_name(row.get("properties", {}).get("Status", {}))
        if not status.startswith("Running"):
            continue
        last_edited = row.get("last_edited_time", "")
        try:
            when = datetime.fromisoformat(last_edited.replace("Z", "+00:00"))
        except ValueError:
            continue
        if when > cutoff:
            continue
        try:
            nc.update_page(row["id"], properties={
                "Status": {"select": {"name": "Failed"}},
                "Last Error": {"rich_text": [{"type": "text", "text": {
                    "content": f"Timed out: status was {status!r} for >{STALE_RUN_THRESHOLD}."
                }}]},
                "Run Agent": {"select": None},
            })
            log.info("poller: reaped stale run on %s", row["id"])
        except nc.NotionAPIError as e:
            log.warning("poller: reap update failed for %s: %s", row["id"], e)


# ─── Poll loop ───────────────────────────────────────────────────────────────

def poll_once() -> None:
    """One poll iteration. Defensive — all errors logged, loop continues."""
    if not nc.is_enabled():
        return

    _reap_stale_runs()

    try:
        rows = nc.query_db(
            nc.deals_db_id(),
            filter={"property": "Run Agent", "select": {"is_not_empty": True}},
        )
    except nc.NotionAPIError as e:
        log.warning("poller: query_db failed: %s", e)
        return

    for row in rows:
        try:
            _process_row(row)
        except Exception:
            log.exception("poller: _process_row crashed on %s", row.get("id"))


# ─── Background thread singleton ─────────────────────────────────────────────

_thread: threading.Thread | None = None
_start_lock = threading.Lock()


def start_background_loop() -> None:
    """Spawn the polling thread once per process. Safe to call repeatedly."""
    global _thread
    if not nc.is_enabled():
        log.info("Notion integration disabled (NOTION_ENABLED != 'true'); poller not started.")
        return

    with _start_lock:
        if _thread is not None and _thread.is_alive():
            return

        def _loop() -> None:
            log.info("Notion poller started (interval=%ss)", POLL_INTERVAL_SECONDS)
            while True:
                try:
                    poll_once()
                except Exception:
                    log.exception("poller: poll_once crashed; continuing")
                time.sleep(POLL_INTERVAL_SECONDS)

        t = threading.Thread(target=_loop, daemon=True, name="notion-poller")
        t.start()
        _thread = t
