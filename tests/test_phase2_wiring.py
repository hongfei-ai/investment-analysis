"""Regression guards on the Agent 5 wiring.

These tests pin invariants that, if broken, would either
(a) re-enable hallucination mode by turning on web_search, or
(b) break persisted deal JSONs by renaming the storage field.
"""

import sys
import types
from pathlib import Path


def _stub_streamlit_if_missing():
    if "streamlit" in sys.modules:
        return
    st = types.ModuleType("streamlit")
    st.cache_data = lambda *a, **k: (lambda f: f)
    st.cache_resource = lambda *a, **k: (lambda f: f)
    sys.modules["streamlit"] = st


def test_agent5_registry_invariants():
    """Agent 5 must stay closed-book (tools=None) and pinned to Sonnet.

    The registry now lives in pages/deal.py after the M4 navigation split;
    importing it requires a full Streamlit runtime, so the lightweight
    guard here reads the source file and checks the invariants textually.
    """
    src = (Path(__file__).resolve().parent.parent / "pages" / "deal.py").read_text()
    assert '"agent5_reference_check"' in src
    assert '"field": "reference_check"' in src
    # Quick structural check: within the registry block for agent5,
    # `"tools": None` and `"model": MODEL_SONNET` must both appear.
    i = src.index('"agent5_reference_check"')
    window = src[i:i + 500]
    assert '"tools": None' in window
    assert '"model": MODEL_SONNET' in window


def test_run_phase2_agent5_task_tuple():
    src = (Path(__file__).resolve().parent.parent / "run_phase2.py").read_text()
    # the parallel task tuple for agent5 must keep tools=None and stay on Sonnet
    i = src.index('"agent5_refcheck"')
    window = src[i:i + 400]
    assert "MODEL_SONNET" in window
    # tools slot in the tuple: the 7th element. Easier regex-free check:
    assert "None, MODEL_SONNET" in window
