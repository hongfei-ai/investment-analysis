"""
run_phase2.py — Phase 2: Post-Call Diligence (parallel execution)
Usage: python run_phase2.py --deal "CompanyName" --notes inputs/call_notes.txt
"""

import argparse
import sys
import concurrent.futures
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from shared import load_deal, save_deal, save_output, call_claude
from agents.prompts import (
    AGENT2_SYSTEM, agent2_user,
    AGENT3_SYSTEM, agent3_user,
    AGENT4_SYSTEM, agent4_user,
    AGENT5_SYSTEM, agent5_user,
    AGENT6_SYSTEM, agent6_user,
)


def run_agent2(deal):
    """Run Diligence Management Agent (must complete before parallel agents)."""
    print("  Running Agent 2: Diligence Management...")
    output = call_claude(AGENT2_SYSTEM, agent2_user(deal))

    # Parse deal mode from output
    mode = "A"
    lower = output.lower()
    if "mode b" in lower and "mode a" in lower:
        mode = "A+B"
    elif "mode b" in lower:
        mode = "B"

    deal["diligence"]["tracker"] = output
    deal["diligence"]["deal_mode"] = mode
    save_deal(deal)
    save_output(deal["deal_id"], "agent2_diligence_mgmt", output)
    print(f"  ✓ Agent 2 complete. Deal Mode: {mode}")
    return deal


def run_parallel_agents(deal):
    """Run Agents 3, 4, 5, 6 in parallel using threads."""
    tasks = {
        "agent3_founder": (AGENT3_SYSTEM, agent3_user(deal), "diligence", "founder_diligence", "agent3_founder_diligence"),
        "agent4_market":  (AGENT4_SYSTEM, agent4_user(deal), "diligence", "market_diligence",  "agent4_market_diligence"),
        "agent5_refcheck":(AGENT5_SYSTEM, agent5_user(deal), "diligence", "reference_check",   "agent5_reference_check"),
        "agent6_thesis":  (AGENT6_SYSTEM, agent6_user(deal), "diligence", "thesis_check",      "agent6_thesis_check"),
    }

    agent_labels = {
        "agent3_founder":  "Agent 3: Founder Diligence",
        "agent4_market":   "Agent 4: Market Diligence",
        "agent5_refcheck": "Agent 5: Reference Check",
        "agent6_thesis":   "Agent 6: Thesis Check",
    }

    results = {}

    def run_one(key):
        system, user_msg, section, field, filename = tasks[key]
        label = agent_labels[key]
        print(f"  → Starting {label}...")
        output = call_claude(system, user_msg)
        results[key] = (section, field, filename, output)
        print(f"  ✓ {label} complete")
        return key

    print("\n  Launching parallel diligence agents (this takes a few minutes)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(run_one, key): key for key in tasks}
        for future in concurrent.futures.as_completed(futures):
            key = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"  ✗ {agent_labels[key]} failed: {e}")

    # Write all results to deal store
    for key, (section, field, filename, output) in results.items():
        deal[section][field] = output
        save_output(deal["deal_id"], filename, output)

    save_deal(deal)
    return deal


def run(args):
    print(f"\n📋 Phase 2: Post-Call Diligence — {args.deal}\n")

    deal = load_deal(args.deal)

    # Load call notes
    notes_path = Path(args.notes)
    if not notes_path.exists():
        print(f"Error: Notes file not found: {args.notes}")
        sys.exit(1)

    deal["call_notes"]["raw_transcript_or_notes"] = notes_path.read_text()
    if args.annotations:
        deal["call_notes"]["human_annotations"] = args.annotations
    deal["status"] = "diligence"
    save_deal(deal)

    # Step 1: Agent 2 (must complete first — produces diligence tracker + deal mode)
    deal = run_agent2(deal)

    # Step 2: Agents 3, 4, 5, 6 in parallel
    deal = run_parallel_agents(deal)

    deal["status"] = "post-diligence"
    save_deal(deal)

    print(f"\n✅ Phase 2 complete. All outputs in: outputs/{args.deal}/")
    print("   → Review all outputs before running Phase 3 (Checkpoint 2)\n")
    print("   Files:")
    print(f"     outputs/{args.deal}/agent2_diligence_mgmt.md")
    print(f"     outputs/{args.deal}/agent3_founder_diligence.md")
    print(f"     outputs/{args.deal}/agent4_market_diligence.md")
    print(f"     outputs/{args.deal}/agent5_reference_check.md")
    print(f"     outputs/{args.deal}/agent6_thesis_check.md\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--deal", required=True, help="Company name (same as used in Phase 1)")
    parser.add_argument("--notes", required=True, help="Path to call notes file (.txt or .md)")
    parser.add_argument("--annotations", help="Deal champion post-call annotations (inline text)")
    run(parser.parse_args())
