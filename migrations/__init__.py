"""Deal migrations.

Numbered modules (e.g. `001_add_owner_and_stage.py`) can't be imported with
`from migrations.001_... import ...` because Python syntax doesn't allow a
leading digit. Each migration is loaded here via importlib and re-exported
under a stable name.
"""

from __future__ import annotations

import importlib


def _load(name: str):
    return importlib.import_module(f"migrations.{name}")


migrate_001 = _load("001_add_owner_and_stage").migrate


def run_all(deal: dict) -> dict:
    """Apply every migration in order. Each migration is idempotent."""
    deal = migrate_001(deal)
    return deal
