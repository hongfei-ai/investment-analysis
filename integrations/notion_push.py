"""
Filesystem → Notion push layer.

Write-only. Called from `agent_runner` after each successful save to mirror
state into Notion. No Notion → filesystem reads happen here; that lives in
`poller.py` for the handful of two-way-synced properties.

Conventions:
- Every function is a no-op when `notion_client.is_enabled()` is False.
- Failures are logged but not raised — Notion drift is never worth crashing
  an agent run for, since the filesystem is the source of truth.
- All markdown-to-blocks conversion lives here; the rest of the codebase
  never touches Notion's block schema.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any

from integrations import notion_client as nc

log = logging.getLogger(__name__)

_NOTION_RICH_TEXT_LIMIT = 2000  # per-rich_text-object hard cap
_AGENT_KEY_TO_PROGRESS_TAG = {
    "agent1_precall":            "A1 ✓",
    "agent2_diligence_mgmt":     "A2 ✓",
    "agent3_founder_diligence":  "A3 ✓",
    "agent4_market_diligence":   "A4 ✓",
    "agent5_reference_check":    "A5 ✓",
    "agent6_thesis_check":       "A6 ✓",
    "agent7_premortem":          "A7 ✓",
    "agent8_ic_simulation":      "A8 ✓",
    "agent9_ic_memo":            "A9 ✓",
}


# ─── Property builders ───────────────────────────────────────────────────────

def _title_prop(text: str) -> dict:
    return {"title": [{"type": "text", "text": {"content": text[:2000]}}]}


def _text_prop(text: str | None) -> dict:
    content = (text or "")[:_NOTION_RICH_TEXT_LIMIT]
    return {"rich_text": [{"type": "text", "text": {"content": content}}]} if content \
        else {"rich_text": []}


def _select_prop(value: str | None) -> dict:
    return {"select": {"name": value}} if value else {"select": None}


def _multi_select_prop(values: list[str]) -> dict:
    return {"multi_select": [{"name": v} for v in values]}


def _url_prop(value: str | None) -> dict:
    return {"url": value or None}


def _number_prop(value: float | int | None) -> dict:
    return {"number": value}


def _date_prop(iso: str | None) -> dict:
    return {"date": {"start": iso}} if iso else {"date": None}


# ─── Markdown → Notion blocks ────────────────────────────────────────────────

_H_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$")
_BULLET_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
_NUMBERED_RE = re.compile(r"^\s*\d+\.\s+(.+?)\s*$")
_FENCE_RE = re.compile(r"^```(\w*)\s*$")


def _rich_text_chunks(text: str) -> list[dict]:
    """Split long text into <=2000-char rich_text objects at word boundaries."""
    if not text:
        return []
    if len(text) <= _NOTION_RICH_TEXT_LIMIT:
        return [{"type": "text", "text": {"content": text}}]

    chunks: list[dict] = []
    remaining = text
    while remaining:
        if len(remaining) <= _NOTION_RICH_TEXT_LIMIT:
            chunks.append({"type": "text", "text": {"content": remaining}})
            break
        split_at = remaining.rfind(" ", 0, _NOTION_RICH_TEXT_LIMIT)
        if split_at <= 0:
            split_at = _NOTION_RICH_TEXT_LIMIT
        chunks.append({"type": "text", "text": {"content": remaining[:split_at]}})
        remaining = remaining[split_at:].lstrip()
    return chunks


def _paragraph(text: str) -> dict:
    return {"object": "block", "type": "paragraph",
            "paragraph": {"rich_text": _rich_text_chunks(text)}}


def _heading(level: int, text: str) -> dict:
    key = f"heading_{min(max(level, 1), 3)}"
    return {"object": "block", "type": key,
            key: {"rich_text": _rich_text_chunks(text)}}


def _bullet(text: str) -> dict:
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": _rich_text_chunks(text)}}


def _numbered(text: str) -> dict:
    return {"object": "block", "type": "numbered_list_item",
            "numbered_list_item": {"rich_text": _rich_text_chunks(text)}}


def _code(text: str, language: str = "markdown") -> dict:
    return {"object": "block", "type": "code",
            "code": {"rich_text": _rich_text_chunks(text), "language": language or "plain text"}}


def markdown_to_blocks(md: str) -> list[dict]:
    """Convert markdown text to a list of Notion block objects.

    Supports H1–H3 headings, bullet and numbered lists, fenced code blocks,
    and plain paragraphs. Markdown tables are rendered as text inside
    paragraphs (Notion's block-schema tables require a separate row-by-row
    build that isn't worth the complexity for MVP).
    """
    if not md:
        return []

    lines = md.splitlines()
    blocks: list[dict] = []
    i = 0
    in_fence = False
    fence_lang = ""
    fence_buf: list[str] = []
    para_buf: list[str] = []

    def flush_para() -> None:
        if para_buf:
            text = " ".join(line.strip() for line in para_buf if line.strip())
            if text:
                blocks.append(_paragraph(text))
            para_buf.clear()

    while i < len(lines):
        line = lines[i]

        # Code fence toggle
        m = _FENCE_RE.match(line)
        if m:
            if in_fence:
                blocks.append(_code("\n".join(fence_buf), fence_lang))
                fence_buf = []
                fence_lang = ""
                in_fence = False
            else:
                flush_para()
                in_fence = True
                fence_lang = m.group(1) or "markdown"
            i += 1
            continue

        if in_fence:
            fence_buf.append(line)
            i += 1
            continue

        # Blank line → paragraph break
        if not line.strip():
            flush_para()
            i += 1
            continue

        # Headings
        mh = _H_RE.match(line)
        if mh:
            flush_para()
            blocks.append(_heading(len(mh.group(1)), mh.group(2)))
            i += 1
            continue

        # Bullets
        mb = _BULLET_RE.match(line)
        if mb:
            flush_para()
            blocks.append(_bullet(mb.group(1)))
            i += 1
            continue

        # Numbered
        mn = _NUMBERED_RE.match(line)
        if mn:
            flush_para()
            blocks.append(_numbered(mn.group(1)))
            i += 1
            continue

        # Plain paragraph line (accumulate)
        para_buf.append(line)
        i += 1

    if in_fence and fence_buf:
        blocks.append(_code("\n".join(fence_buf), fence_lang))
    flush_para()

    return blocks


# ─── Deal metadata push ──────────────────────────────────────────────────────

_DEAL_SCALAR_FIELDS: list[tuple[str, str, str]] = [
    # (notion_property, deal_json_path, prop_kind)
    ("Deal Stage",       "deal_stage",                  "select"),
    ("Priority",         "priority",                    "select"),
    ("Next Step",        "next_step",                   "text"),
    ("Founder Name",     "inputs.founder_name",         "text"),
    ("Founder LinkedIn", "inputs.founder_linkedin",     "url"),
    ("Company Website",  "inputs.company_website",      "url"),
    ("Intro Source",     "inputs.intro_source",         "text"),
    ("Intro Context",    "inputs.intro_context",        "text"),
    ("Initial Notes",    "inputs.initial_notes",        "text"),
]


def _get_path(deal: dict, path: str) -> Any:
    node: Any = deal
    for part in path.split("."):
        if not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def _build_deal_properties(deal: dict) -> dict:
    props: dict[str, Any] = {
        "Company Name": _title_prop(deal.get("company_name") or deal.get("deal_id", "")),
    }
    for prop_name, path, kind in _DEAL_SCALAR_FIELDS:
        value = _get_path(deal, path)
        if kind == "select":
            props[prop_name] = _select_prop(value if value else None)
        elif kind == "text":
            props[prop_name] = _text_prop(value if isinstance(value, str) else None)
        elif kind == "url":
            props[prop_name] = _url_prop(value if isinstance(value, str) and value else None)

    notes = deal.get("call_notes", {}).get("human_annotations") \
        or deal.get("diligence", {}).get("human_review_notes") \
        or ""
    props["Notes"] = _text_prop(notes)

    return props


def _find_deal_page(deal_name: str) -> str | None:
    """Return the Notion page id for a deal by Company Name, or None."""
    try:
        results = nc.query_db(
            nc.deals_db_id(),
            filter={"property": "Company Name", "title": {"equals": deal_name}},
            page_size=1,
        )
    except nc.NotionAPIError as e:
        log.warning("notion_push: query_db failed for %s: %s", deal_name, e)
        return None
    return results[0]["id"] if results else None


def push_deal_metadata(deal: dict) -> str | None:
    """Upsert a Deal row from the filesystem deal JSON. Returns page_id or None."""
    if not nc.is_enabled():
        return None
    try:
        deal_name = deal.get("company_name") or deal.get("deal_id", "")
        props = _build_deal_properties(deal)
        page_id = _find_deal_page(deal_name)
        if page_id:
            nc.update_page(page_id, properties=props)
            return page_id
        page = nc.create_page(
            parent={"database_id": nc.deals_db_id()},
            properties=props,
        )
        return page["id"]
    except nc.NotionAPIError as e:
        log.warning("notion_push.push_deal_metadata failed: %s", e)
        return None


# ─── Per-run status / error / progress ───────────────────────────────────────

def set_deal_status(deal_name: str, status: str, *, clear_run_agent: bool = False) -> None:
    if not nc.is_enabled():
        return
    try:
        page_id = _find_deal_page(deal_name)
        if not page_id:
            return
        props: dict[str, Any] = {"Status": _select_prop(status)}
        if clear_run_agent:
            props["Run Agent"] = _select_prop(None)
        nc.update_page(page_id, properties=props)
    except nc.NotionAPIError as e:
        log.warning("notion_push.set_deal_status failed: %s", e)


def record_deal_error(deal_name: str, message: str) -> None:
    if not nc.is_enabled():
        return
    try:
        page_id = _find_deal_page(deal_name)
        if not page_id:
            return
        nc.update_page(page_id, properties={
            "Status":     _select_prop("Failed"),
            "Last Error": _text_prop(message[:2000]),
            "Run Agent":  _select_prop(None),
        })
    except nc.NotionAPIError as e:
        log.warning("notion_push.record_deal_error failed: %s", e)


def clear_deal_error(deal_name: str) -> None:
    if not nc.is_enabled():
        return
    try:
        page_id = _find_deal_page(deal_name)
        if not page_id:
            return
        nc.update_page(page_id, properties={"Last Error": _text_prop("")})
    except nc.NotionAPIError as e:
        log.warning("notion_push.clear_deal_error failed: %s", e)


def mark_agent_done(deal_name: str, agent_key: str) -> None:
    """Add the agent's progress tag to the Agent Progress multi-select."""
    if not nc.is_enabled():
        return
    tag = _AGENT_KEY_TO_PROGRESS_TAG.get(agent_key)
    if not tag:
        return
    try:
        page_id = _find_deal_page(deal_name)
        if not page_id:
            return
        page = nc.retrieve_page(page_id)
        current = page.get("properties", {}).get("Agent Progress", {}).get("multi_select", [])
        existing = {o["name"] for o in current}
        existing.add(tag)
        nc.update_page(page_id, properties={
            "Agent Progress": _multi_select_prop(sorted(existing)),
        })
    except nc.NotionAPIError as e:
        log.warning("notion_push.mark_agent_done failed: %s", e)


# ─── Agent Outputs row ───────────────────────────────────────────────────────

def create_output_page(deal_name: str, deal_page_id: str, agent_key: str,
                       run_by_notion_user_id: str | None,
                       started_iso: str) -> str | None:
    """Create an Agent Outputs row in Running state. Returns output page id."""
    if not nc.is_enabled():
        return None
    try:
        started_short = started_iso[:16].replace("T", " ")
        title = f"{deal_name} — {agent_key} — {started_short}"
        props: dict[str, Any] = {
            "Title":     _title_prop(title),
            "Deal":      {"relation": [{"id": deal_page_id}]},
            "Agent Key": _select_prop(agent_key),
            "Status":    _select_prop("Running"),
            "Started":   _date_prop(started_iso),
        }
        if run_by_notion_user_id:
            props["Run By"] = {"people": [{"id": run_by_notion_user_id}]}
        page = nc.create_page(
            parent={"database_id": nc.outputs_db_id()},
            properties=props,
        )
        return page["id"]
    except nc.NotionAPIError as e:
        log.warning("notion_push.create_output_page failed: %s", e)
        return None


def finalize_output_page(output_page_id: str, output_md: str,
                         duration_seconds: float) -> None:
    """Append the rendered markdown blocks + flip Status to Done."""
    if not nc.is_enabled() or not output_page_id:
        return
    try:
        blocks = markdown_to_blocks(output_md)
        if blocks:
            nc.append_blocks(output_page_id, blocks)
        nc.update_page(output_page_id, properties={
            "Status":       _select_prop("Done"),
            "Duration (s)": _number_prop(round(duration_seconds, 1)),
        })
    except nc.NotionAPIError as e:
        log.warning("notion_push.finalize_output_page failed: %s", e)


def fail_output_page(output_page_id: str, error_message: str) -> None:
    if not nc.is_enabled() or not output_page_id:
        return
    try:
        nc.append_blocks(output_page_id, [
            _heading(3, "Error"),
            _paragraph(error_message[:2000]),
        ])
        nc.update_page(output_page_id, properties={"Status": _select_prop("Failed")})
    except nc.NotionAPIError as e:
        log.warning("notion_push.fail_output_page failed: %s", e)


def append_heartbeat(output_page_id: str, message: str) -> None:
    """Append a one-line progress block while the agent is running."""
    if not nc.is_enabled() or not output_page_id:
        return
    try:
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        nc.append_blocks(output_page_id, [_paragraph(f"· {ts}  {message}")])
    except nc.NotionAPIError as e:
        log.warning("notion_push.append_heartbeat failed: %s", e)
