"""
Thin Notion API wrapper.

Exposes a minimal set of functions — query_db, retrieve_page, update_page,
create_page, append_blocks, retrieve_user — backed by raw `requests` calls
to the Notion REST API. No external Notion SDK dependency.

Configuration is read from environment variables (which are populated
from `.streamlit/secrets.toml` at app startup):

    NOTION_TOKEN          — integration secret (required)
    NOTION_DEALS_DB_ID    — Deals database id (required once bootstrapped)
    NOTION_OUTPUTS_DB_ID  — Agent Outputs database id (required once bootstrapped)
    NOTION_ENABLED        — "true" to enable; default false (safe no-op)

All functions return parsed JSON dicts or raise `NotionAPIError` on any
non-2xx response. Callers should catch and log; the poller is defensive
so a single failed call never crashes the loop.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import requests

_NOTION_API = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"

log = logging.getLogger(__name__)


class NotionAPIError(RuntimeError):
    """Raised on any non-2xx response from the Notion API."""

    def __init__(self, status_code: int, body: str, endpoint: str):
        self.status_code = status_code
        self.body = body
        self.endpoint = endpoint
        super().__init__(f"{endpoint} returned {status_code}: {body[:200]}")


def is_enabled() -> bool:
    """Integration is a no-op unless explicitly enabled."""
    return os.environ.get("NOTION_ENABLED", "").strip().lower() == "true"


def _token() -> str:
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        raise NotionAPIError(0, "NOTION_TOKEN is unset", "config")
    return token


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Notion-Version": _NOTION_VERSION,
        "Content-Type": "application/json",
    }


def deals_db_id() -> str:
    db_id = os.environ.get("NOTION_DEALS_DB_ID", "").strip()
    if not db_id:
        raise NotionAPIError(0, "NOTION_DEALS_DB_ID is unset", "config")
    return db_id


def outputs_db_id() -> str:
    db_id = os.environ.get("NOTION_OUTPUTS_DB_ID", "").strip()
    if not db_id:
        raise NotionAPIError(0, "NOTION_OUTPUTS_DB_ID is unset", "config")
    return db_id


def bot_user_email() -> str:
    return os.environ.get("NOTION_BOT_USER_EMAIL", "notion-bot@january.capital").strip()


# ─── HTTP primitives ─────────────────────────────────────────────────────────

def _request(method: str, endpoint: str, **kwargs: Any) -> dict:
    url = f"{_NOTION_API}{endpoint}"
    try:
        resp = requests.request(method, url, headers=_headers(), timeout=30, **kwargs)
    except requests.RequestException as e:
        raise NotionAPIError(0, f"network: {e}", endpoint) from e
    if resp.status_code // 100 != 2:
        raise NotionAPIError(resp.status_code, resp.text, endpoint)
    return resp.json() if resp.content else {}


# ─── Public API ──────────────────────────────────────────────────────────────

def query_db(database_id: str, *, filter: dict | None = None,
             sorts: list[dict] | None = None, page_size: int = 100) -> list[dict]:
    """Return all pages in a database matching the filter (handles pagination)."""
    payload: dict[str, Any] = {"page_size": page_size}
    if filter is not None:
        payload["filter"] = filter
    if sorts is not None:
        payload["sorts"] = sorts

    pages: list[dict] = []
    cursor: str | None = None
    while True:
        if cursor:
            payload["start_cursor"] = cursor
        body = _request("POST", f"/databases/{database_id}/query", data=json.dumps(payload))
        pages.extend(body.get("results", []))
        if not body.get("has_more"):
            break
        cursor = body.get("next_cursor")
    return pages


def retrieve_page(page_id: str) -> dict:
    return _request("GET", f"/pages/{page_id}")


def update_page(page_id: str, *, properties: dict | None = None,
                archived: bool | None = None) -> dict:
    payload: dict[str, Any] = {}
    if properties is not None:
        payload["properties"] = properties
    if archived is not None:
        payload["archived"] = archived
    return _request("PATCH", f"/pages/{page_id}", data=json.dumps(payload))


def create_page(*, parent: dict, properties: dict,
                children: list[dict] | None = None) -> dict:
    payload: dict[str, Any] = {"parent": parent, "properties": properties}
    if children is not None:
        payload["children"] = children
    return _request("POST", "/pages", data=json.dumps(payload))


def append_blocks(page_id: str, children: list[dict]) -> dict:
    """Append block children to a page. Notion caps at 100 children per call."""
    if len(children) <= 100:
        return _request("PATCH", f"/blocks/{page_id}/children",
                        data=json.dumps({"children": children}))
    # Chunk
    last_response: dict = {}
    for i in range(0, len(children), 100):
        batch = children[i:i + 100]
        last_response = _request("PATCH", f"/blocks/{page_id}/children",
                                 data=json.dumps({"children": batch}))
    return last_response


def retrieve_user(user_id: str) -> dict:
    """Returns the user object, including `person.email` if the integration
    has the `read user info including email addresses` capability enabled."""
    return _request("GET", f"/users/{user_id}")


def create_database(*, parent: dict, title: list[dict], properties: dict) -> dict:
    """Used only by bootstrap_notion.py to set up the two DBs."""
    payload = {"parent": parent, "title": title, "properties": properties}
    return _request("POST", "/databases", data=json.dumps(payload))
