"""
auth.py — Authentication and authorization helpers.

Wraps Streamlit's native OIDC (`st.login()` / `st.user`) behind a small
surface so the rest of the code stays decoupled from Streamlit specifics
and the pure-logic functions (is_editor, require_editor, domain check)
remain unit-testable without a Streamlit runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional


@dataclass(frozen=True)
class User:
    email: str
    name: str = ""
    picture: str = ""

    @property
    def is_authenticated(self) -> bool:
        return bool(self.email)


class PermissionError(Exception):
    """Raised when an operation requires editor permission the caller lacks."""


def is_allowed_domain(email: str, allowed: str | Iterable[str]) -> bool:
    """Return True iff email's domain matches the allowed domain(s).

    `allowed` may be a single domain string ("example.com") or an iterable
    of domain strings. Matching is case-insensitive. An empty or missing
    email is always rejected.
    """
    if not email or "@" not in email:
        return False
    user_domain = email.rsplit("@", 1)[-1].lower()
    if isinstance(allowed, str):
        allowed_list = [allowed]
    else:
        allowed_list = list(allowed)
    return any(user_domain == d.strip().lower() for d in allowed_list if d)


def is_editor(deal: dict, user: Optional[User]) -> bool:
    """Is this user allowed to mutate this deal?

    Editors: the deal's owner_email, or any address in deal['collaborators'].
    Unassigned deals (owner_email == 'unassigned' or missing) are NOT
    editable by default — claim the deal first.
    """
    if user is None or not user.is_authenticated:
        return False
    owner = (deal.get("owner_email") or "").strip().lower()
    if owner and owner != "unassigned" and owner == user.email.lower():
        return True
    collaborators = deal.get("collaborators") or []
    return user.email.lower() in {c.strip().lower() for c in collaborators if c}


def require_editor(deal: dict, user: Optional[User]) -> None:
    """Raise PermissionError unless `user` may edit `deal`."""
    if not is_editor(deal, user):
        who = user.email if user and user.is_authenticated else "anonymous"
        owner = deal.get("owner_email") or "unassigned"
        raise PermissionError(
            f"User {who!r} is not an editor of deal "
            f"{deal.get('deal_id', '<unknown>')!r} (owner={owner!r})"
        )


# ─── Streamlit integration (not unit-tested; exercised via manual smoke test) ─

def _streamlit_user() -> Optional[User]:
    """Read the currently logged-in user from Streamlit's native OIDC.

    Returns None if unauthenticated, if auth isn't configured (dev mode),
    or if the logged-in email isn't on the allowed domain.
    """
    try:
        import streamlit as st
    except ImportError:
        return None

    try:
        st_user = st.user
        if not getattr(st_user, "is_logged_in", False):
            return None
        email = getattr(st_user, "email", "") or ""
    except Exception:
        return None

    allowed = _allowed_domain_from_secrets()
    if allowed and not is_allowed_domain(email, allowed):
        return None

    return User(
        email=email,
        name=getattr(st_user, "name", "") or "",
        picture=getattr(st_user, "picture", "") or "",
    )


def _allowed_domain_from_secrets() -> str | list[str] | None:
    """Read allowed_domain from Streamlit secrets; None if unset."""
    try:
        import streamlit as st
        return st.secrets.get("allowed_domain")
    except Exception:
        return None


def current_user() -> Optional[User]:
    """Return the authenticated user, or None.

    Thin wrapper so tests can monkeypatch this module-level function.
    """
    return _streamlit_user()


def render_login_gate() -> Optional[User]:
    """Render the login UI and return the User if authenticated, else None.

    Call at the top of a Streamlit page; caller should `st.stop()` on None.
    Handles three states:
      1. Not logged in              → show login button, return None
      2. Logged in, off-domain      → show access-denied, return None
      3. Logged in, on-domain       → return User
      4. Auth not configured        → show setup instructions, return None
    """
    import streamlit as st

    try:
        st_user = st.user
    except Exception:
        st.error(
            "Authentication is not configured. Add an `[auth]` block with "
            "`redirect_uri`, `cookie_secret`, `client_id`, `client_secret`, "
            "and `server_metadata_url` to `.streamlit/secrets.toml`. "
            "See `.streamlit/secrets.toml.example`."
        )
        return None

    if not getattr(st_user, "is_logged_in", False):
        st.title("\U0001f4ca Investment Analysis")
        st.caption("January Capital \u2014 Internal Tool")
        st.write("Sign in with your Google Workspace account to continue.")
        if st.button("Sign in with Google", type="primary"):
            st.login()
        return None

    email = getattr(st_user, "email", "") or ""
    allowed = _allowed_domain_from_secrets()
    if allowed and not is_allowed_domain(email, allowed):
        st.error(
            f"Access denied: {email} is not on the allowed domain. "
            "Contact the workspace admin."
        )
        if st.button("Sign out"):
            st.logout()
        return None

    return User(
        email=email,
        name=getattr(st_user, "name", "") or "",
        picture=getattr(st_user, "picture", "") or "",
    )
