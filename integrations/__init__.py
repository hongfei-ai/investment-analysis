"""
integrations/ — Notion and Slack integration layer.

Decoupled from Streamlit: every module here is importable from a background
thread or a future out-of-process worker. The core execution engine
(`shared.py`, `agents/`, `auth.py`) remains integration-free; hooks are
only applied at the `agent_runner` seam so the filesystem primary/Notion
mirror split stays clean.

See /root/.claude/plans/how-about-we-replace-zazzy-brooks.md for the full
architectural rationale.
"""
