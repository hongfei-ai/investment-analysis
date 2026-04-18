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
    _stub_streamlit_if_missing()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

    # Importing app.py pulls a lot of Streamlit UI; we only need the registry.
    # If the full import fails in the test env, we fall back to reading the
    # source to confirm the invariants.
    try:
        import app
        cfg = app.AGENT_REGISTRY["agent5_reference_check"]
    except Exception:
        src = (Path(__file__).resolve().parent.parent / "app.py").read_text()
        # field and tools invariants visible in the registry block
        assert '"agent5_reference_check"' in src
        assert '"field": "reference_check"' in src
        # confirm no tools wired to Agent 5 (the registry block has tools: None)
        # Quick structural check: within ~8 lines after the agent5 key, "tools": None appears
        i = src.index('"agent5_reference_check"')
        window = src[i:i + 500]
        assert '"tools": None' in window
        assert '"model": MODEL_SONNET' in window
        return

    assert cfg["section"] == "diligence"
    assert cfg["field"] == "reference_check"
    assert cfg.get("tools") is None


def test_run_phase2_agent5_task_tuple():
    src = (Path(__file__).resolve().parent.parent / "run_phase2.py").read_text()
    # the parallel task tuple for agent5 must keep tools=None and stay on Sonnet
    i = src.index('"agent5_refcheck"')
    window = src[i:i + 400]
    assert "MODEL_SONNET" in window
    # tools slot in the tuple: the 7th element. Easier regex-free check:
    assert "None, MODEL_SONNET" in window
