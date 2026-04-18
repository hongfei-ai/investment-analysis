"""
shared.py — Shared utilities, knowledge store, and API caller for all agents.
"""

import contextlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

try:
    import fcntl
    _HAS_FCNTL = True
except ImportError:  # Windows
    _HAS_FCNTL = False

load_dotenv(Path(__file__).parent / ".env", override=True)

# Support both .env (local) and Streamlit secrets (cloud)
def _get_api_key():
    # 1. Try environment variable (.env or system)
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    # 2. Try Streamlit secrets (cloud deployment)
    try:
        import streamlit as st
        key = st.secrets["ANTHROPIC_API_KEY"]
        if key:
            return key
    except Exception:
        pass
    return None


# Lazy, thread-safe singleton client — created once, reused across all calls
_client = None
_client_lock = threading.Lock()

def get_client():
    global _client
    if _client is not None:
        return _client
    with _client_lock:
        if _client is not None:          # double-checked locking
            return _client
        key = _get_api_key()
        if not key:
            raise ValueError("No ANTHROPIC_API_KEY found. Set it in .env or Streamlit secrets.")
        _client = anthropic.Anthropic(api_key=key, max_retries=3, timeout=180.0)
        return _client

MODEL = "claude-opus-4-7"
MODEL_SONNET = "claude-sonnet-4-6"

DEALS_DIR = Path("deals")
OUTPUTS_DIR = Path("outputs")
DEALS_DIR.mkdir(exist_ok=True)
OUTPUTS_DIR.mkdir(exist_ok=True)


# ─── Knowledge Store ──────────────────────────────────────────────────────────

def _safe_deal_name(deal_name: str) -> str:
    """Validate a deal name is safe to use as a filesystem path component.

    Rejects empty strings, path separators, parent-directory references, and
    leading dots so a crafted name can't escape DEALS_DIR / OUTPUTS_DIR.
    """
    if not isinstance(deal_name, str) or not deal_name.strip():
        raise ValueError("deal_name must be a non-empty string")
    name = deal_name.strip()
    if "/" in name or "\\" in name or "\x00" in name:
        raise ValueError(f"deal_name contains path separators: {deal_name!r}")
    if name in (".", "..") or name.startswith("."):
        raise ValueError(f"deal_name may not start with '.': {deal_name!r}")
    if ".." in Path(name).parts:
        raise ValueError(f"deal_name may not contain '..': {deal_name!r}")
    return name


class VersionMismatch(RuntimeError):
    """Raised when atomic_save_deal is called with a stale expected_version."""


def _deal_path(deal_name: str) -> Path:
    return DEALS_DIR / f"{_safe_deal_name(deal_name)}.json"


def _lock_path(deal_name: str) -> Path:
    return DEALS_DIR / f".{_safe_deal_name(deal_name)}.lock"


@contextlib.contextmanager
def _file_lock(lock_path: Path):
    """Advisory exclusive file lock. No-op on platforms without fcntl."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if not _HAS_FCNTL:
        yield
        return
    f = open(lock_path, "a")
    try:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        f.close()


def _new_deal_skeleton(deal_name: str) -> dict:
    """Skeleton for a brand-new deal — already includes multi-user fields."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "deal_id": deal_name,
        "company_name": deal_name,
        "date_created": now,
        "updated_at": now,
        "_version": 0,
        "owner_email": "unassigned",
        "collaborators": [],
        "created_by": None,
        "deal_stage": "contacted",
        "priority": None,
        "round_size": None,
        "check_size": None,
        "valuation": None,
        "sector": None,
        "geography": None,
        "next_step": None,
        "next_step_due": None,
        "status": "pre-call",
        "inputs": {
            "founder_name": "",
            "founder_linkedin": "",
            "founder_email": "",
            "company_website": "",
            "pitch_deck_path": "",
            "intro_source": "",
            "intro_context": "",
            "initial_notes": "",
            "deal_champion": "",
        },
        "pre_call": {
            "research_output": {},
            "suggested_questions": [],
            "human_notes": "",
        },
        "call_notes": {
            "raw_transcript_or_notes": "",
            "date_of_call": "",
            "attendees": [],
            "human_annotations": "",
        },
        "diligence": {
            "tracker": {},
            "technical_diligence_required": False,
            "founder_diligence": {},
            "market_diligence": {},
            "reference_check": {},  # Agent 5 output: customer & traction intelligence
            "thesis_check": {},
            "human_review_notes": "",
        },
        "ic_preparation": {
            "pre_mortem": {},
            "ic_simulation": {},
            "ic_memo": {},
            "human_edits": "",
        },
    }


def load_deal(deal_name: str) -> dict:
    """Load deal context from JSON, or create a new one.

    Lazily runs pending migrations on existing files so old deals pick up
    multi-user fields without an explicit batch job.
    """
    deal_name = _safe_deal_name(deal_name)
    path = _deal_path(deal_name)
    if not path.exists():
        return _new_deal_skeleton(deal_name)
    deal = json.loads(path.read_text())
    # Local import avoids a circular dependency at module load time.
    from migrations import run_all
    return run_all(deal)


def atomic_save_deal(deal: dict, expected_version: int | None = None) -> dict:
    """Persist a deal with optimistic locking and atomic replace.

    If `expected_version` is provided, the on-disk `_version` must match
    or VersionMismatch is raised. On success, `_version` is bumped and
    `updated_at` is stamped in UTC. The file is rewritten via a tmp +
    `os.replace()` pair so a reader can never see a half-written file.

    Returns the deal dict after the write (with updated `_version` and
    `updated_at`) so callers can continue to mutate without re-reading.
    """
    deal_id = _safe_deal_name(deal["deal_id"])
    path = _deal_path(deal_id)
    lock_path = _lock_path(deal_id)

    with _file_lock(lock_path):
        current_version = 0
        if path.exists():
            try:
                current_version = int(json.loads(path.read_text()).get("_version", 0))
            except (json.JSONDecodeError, ValueError, TypeError):
                current_version = 0

        if expected_version is not None and current_version != expected_version:
            raise VersionMismatch(
                f"Deal {deal_id!r} version mismatch: expected "
                f"{expected_version}, found {current_version}. Reload and retry."
            )

        deal["_version"] = current_version + 1
        deal["updated_at"] = datetime.now(timezone.utc).isoformat()

        tmp_path = path.with_suffix(path.suffix + ".tmp")
        tmp_path.write_text(json.dumps(deal, indent=2), encoding="utf-8")
        os.replace(tmp_path, path)

    return deal


def save_deal(deal: dict):
    """Back-compat wrapper around `atomic_save_deal` with no version check.

    Kept for existing callers in run_phase*.py and app.py. Milestone 5 will
    require passing `expected_version` (via atomic_save_deal directly) so
    concurrent writers can't clobber each other.
    """
    atomic_save_deal(deal, expected_version=None)


def record_run(
    deal_name: str,
    agent_key: str,
    status: str,
    by_user: str | None,
    started_at: str | None = None,
    ended_at: str | None = None,
) -> None:
    """Append one agent-run record to `deals/{name}.runs.jsonl`.

    `status` is typically 'running', 'done', or 'error'. Any string is
    allowed; the file is append-only so a caller can write a 'running'
    row first and a 'done' row when the agent finishes.
    """
    name = _safe_deal_name(deal_name)
    path = DEALS_DIR / f"{name}.runs.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "agent_key": agent_key,
        "status": status,
        "by_user": by_user,
        "started_at": started_at,
        "ended_at": ended_at,
    }
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def read_runs(deal_name: str) -> list[dict]:
    """Return run records in append order (oldest first), or [] if none."""
    name = _safe_deal_name(deal_name)
    path = DEALS_DIR / f"{name}.runs.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def save_output(deal_name: str, agent_key: str, content: str):
    """Save agent output as markdown and return the path."""
    deal_name = _safe_deal_name(deal_name)
    out_dir = OUTPUTS_DIR / deal_name
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{agent_key}.md"
    path.write_text(content, encoding="utf-8")
    print(f"  ✓ Saved: {path}")
    return path


# ─── PDF Reader ───────────────────────────────────────────────────────────────

def read_pdf(path: str) -> str:
    """Extract text from a PDF file."""
    try:
        import PyPDF2
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            return "\n\n".join(
                page.extract_text() for page in reader.pages if page.extract_text()
            )
    except Exception as e:
        return f"[Could not read PDF: {e}]"


# ─── DOCX Reader ────────────────────────────────────────────────────────────

def read_docx(path: str) -> str:
    """Extract text from a DOCX file."""
    try:
        from docx import Document
        doc = Document(path)
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    except Exception as e:
        return f"[Could not read DOCX: {e}]"


def extract_file_text(file_bytes: bytes, filename: str) -> str:
    """Extract text from an uploaded file based on its extension."""
    import tempfile
    name_lower = filename.lower()

    if name_lower.endswith((".txt", ".md", ".csv")):
        return file_bytes.decode("utf-8", errors="replace")

    def _via_tempfile(suffix: str, reader):
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        try:
            tmp.write(file_bytes)
            tmp.flush()
            tmp.close()
            return reader(tmp.name)
        finally:
            try:
                os.unlink(tmp.name)
            except OSError:
                pass

    if name_lower.endswith(".pdf"):
        return _via_tempfile(".pdf", read_pdf)

    if name_lower.endswith((".docx", ".doc")):
        return _via_tempfile(".docx", read_docx)

    return f"[Unsupported file type: {filename}]"


# ─── Diligence Tracker Parsers ───────────────────────────────────────────────

def parse_technical_diligence_required(output: str) -> bool:
    """Extract the `technical_diligence_required` flag from Agent 2 output text.

    Agent 2 emits a line like:
        `technical_diligence_required: true`
    (optionally wrapped in backticks). Returns True only if the value is
    explicitly "true" — everything else (including missing / malformed) is
    treated as False so downstream agents default to market-only diligence.
    """
    m = re.search(
        r"technical_diligence_required\s*:\s*`?\s*(true|false)",
        output or "",
        re.IGNORECASE,
    )
    if not m:
        return False
    return m.group(1).strip().lower() == "true"


# ─── API Caller ───────────────────────────────────────────────────────────────

def _cached_system(system_prompt: str) -> list[dict]:
    """Wrap the system prompt in a cache_control block.

    Agent system prompts are static across runs, so marking them ephemeral
    lets repeated calls (debug loops, per-section reruns, retries within
    the cache TTL) pay only ~10% of the input-token cost on cache hits.
    For prompts under the model's minimum cacheable length the marker is
    a silent no-op, so it's safe to apply universally.
    """
    return [{"type": "text", "text": system_prompt,
             "cache_control": {"type": "ephemeral"}}]


def call_claude(system_prompt: str, user_message: str, max_tokens: int = 8000,
                tools: list | None = None, model: str | None = None) -> str:
    """Call Claude and return the text response.

    When tools are provided (e.g. web_search), the response may contain
    multiple content blocks (tool results + text). We extract and concatenate
    all text blocks.
    """
    kwargs = dict(
        model=model or MODEL,
        max_tokens=max_tokens,
        system=_cached_system(system_prompt),
        messages=[{"role": "user", "content": user_message}],
    )
    if tools:
        kwargs["tools"] = tools
    response = get_client().messages.create(**kwargs)

    # Extract text from all content blocks (server tools add non-text blocks)
    final_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_text += block.text
    return final_text


def stream_claude(system_prompt: str, user_message: str, max_tokens: int = 8000,
                  tools: list | None = None, model: str | None = None):
    """Stream Claude response, yielding text deltas as they arrive.

    When tools are provided (e.g. web_search), the stream handles server-side
    tool execution transparently — text_stream yields only the text deltas.
    """
    kwargs = dict(
        model=model or MODEL,
        max_tokens=max_tokens,
        system=_cached_system(system_prompt),
        messages=[{"role": "user", "content": user_message}],
    )
    if tools:
        kwargs["tools"] = tools
    with get_client().messages.stream(**kwargs) as stream:
        for text in stream.text_stream:
            yield text


# ─── UI Helpers ──────────────────────────────────────────────────────────────

def list_deals() -> list[str]:
    """Return sorted list of deal names from deals/ folder."""
    return sorted(
        p.stem for p in DEALS_DIR.glob("*.json")
    )



def read_output(deal_name: str, agent_key: str) -> str | None:
    """Load a saved agent markdown output, or None if not found."""
    deal_name = _safe_deal_name(deal_name)
    path = OUTPUTS_DIR / deal_name / f"{agent_key}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


OUTPUT_FORMAT_INSTRUCTIONS = """
Output format standards (apply to every section):
- Structured markdown with clear headers
- All claims must cite source URL or document
- Use [HIGH CONFIDENCE], [MEDIUM CONFIDENCE], [LOW CONFIDENCE / INFERRED] where inference is involved
- Separate factual findings from analytical judgments
- Begin with a 3-5 sentence executive summary
- Use [INSUFFICIENT DATA — requires manual input] rather than fabricating content
"""
