"""
run_phase3.py — Phase 3: IC Preparation (sequential)
Usage: python run_phase3.py --deal "CompanyName"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from shared import load_deal, save_deal, save_output, call_claude, MODEL_SONNET
from agents.prompts import (
    AGENT7_SYSTEM, agent7_user,
    AGENT8_SYSTEM, agent8_user,
    AGENT9_SYSTEM, agent9_user,
)


def run(args):
    print(f"\n🧠 Phase 3: IC Preparation — {args.deal}\n")

    deal = load_deal(args.deal)

    if deal["status"] not in ("post-diligence", "ic-prep", "complete"):
        print("Warning: Phase 2 may not be complete for this deal.")
        print("Proceeding anyway — some inputs may be missing.\n")

    # Agent 7: Pre-Mortem
    print("  Running Agent 7: Pre-Mortem / Devil's Advocate...")
    agent7_out = call_claude(AGENT7_SYSTEM, agent7_user(deal), model=MODEL_SONNET)
    deal["ic_preparation"]["pre_mortem"] = agent7_out
    save_deal(deal)
    save_output(args.deal, "agent7_premortem", agent7_out)

    # Agent 8: IC Simulation (needs Agent 7 output)
    print("  Running Agent 8: IC Simulation...")
    agent8_out = call_claude(AGENT8_SYSTEM, agent8_user(deal))
    deal["ic_preparation"]["ic_simulation"] = agent8_out
    save_deal(deal)
    save_output(args.deal, "agent8_ic_simulation", agent8_out)

    # Agent 9: IC Memo (needs all prior outputs)
    print("  Running Agent 9: IC Memo Creation...")
    agent9_out = call_claude(AGENT9_SYSTEM, agent9_user(deal), max_tokens=12000)
    deal["ic_preparation"]["ic_memo"] = agent9_out
    deal["status"] = "complete"
    save_deal(deal)
    save_output(args.deal, "agent9_ic_memo", agent9_out)

    print(f"\n✅ Phase 3 complete.")
    print(f"   Final IC Memo: outputs/{args.deal}/agent9_ic_memo.md")
    print("   → Review memo before distributing to IC (Checkpoint 3)\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--deal", required=True, help="Company name (same as used in Phase 1 & 2)")
    run(parser.parse_args())
