"""
agents/prompts.py — Backward-compatible re-export shim.

All agent prompts now live in individual files (agent1_precall.py, agent2_diligence_mgmt.py, etc.).
This file re-exports everything so existing imports continue to work:
    from agents.prompts import AGENT1_SYSTEM, agent1_user
"""

from agents.agent1_precall import AGENT1_SYSTEM, agent1_user
from agents.agent2_diligence_mgmt import AGENT2_SYSTEM, agent2_user
from agents.agent3_founder import AGENT3_SYSTEM, agent3_user
from agents.agent4_market import AGENT4_SYSTEM, agent4_user
from agents.agent5_traction import AGENT5_SYSTEM, agent5_user
from agents.agent6_thesis import AGENT6_SYSTEM, agent6_user
from agents.agent7_premortem import AGENT7_SYSTEM, agent7_user
from agents.agent8_ic_sim import AGENT8_SYSTEM, agent8_user
from agents.agent9_ic_memo import AGENT9_SYSTEM, agent9_user
