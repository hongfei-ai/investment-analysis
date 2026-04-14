"""
run_phase1.py — Phase 1: Pre-Call Research Agent
Usage: python run_phase1.py --deal "CompanyName" --founder "Founder Name" --linkedin "https://..."
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from shared import load_deal, save_deal, save_output, read_pdf, call_claude
from agents.prompts import AGENT1_SYSTEM, agent1_user


def run(args):
    print(f"\n🔍 Phase 1: Pre-Call Research — {args.deal}\n")

    deal = load_deal(args.deal)
    deal["inputs"]["founder_name"] = args.founder
    deal["inputs"]["founder_linkedin"] = args.linkedin
    if args.website:
        deal["inputs"]["company_website"] = args.website
    if args.source:
        deal["inputs"]["intro_source"] = args.source
    if args.context:
        deal["inputs"]["intro_context"] = args.context
    if args.notes:
        deal["inputs"]["initial_notes"] = args.notes

    if args.deck:
        print(f"  Reading pitch deck: {args.deck}")
        deal["_deck_text"] = read_pdf(args.deck)
        deal["inputs"]["pitch_deck_path"] = args.deck

    print("  Running Agent 1: Pre-Call Research...")
    output = call_claude(AGENT1_SYSTEM, agent1_user(deal))

    deal["pre_call"]["research_output"] = output
    deal["status"] = "pre-call"
    save_deal(deal)
    save_output(args.deal, "agent1_precall", output)

    print(f"\n✅ Done. Review output at: outputs/{args.deal}/agent1_precall.md")
    print("   → Review before your founder call (Checkpoint 1)\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--deal", required=True, help="Company name (used as deal ID)")
    parser.add_argument("--founder", required=True, help="Founder full name")
    parser.add_argument("--linkedin", required=True, help="Founder LinkedIn URL")
    parser.add_argument("--website", help="Company website URL")
    parser.add_argument("--deck", help="Path to pitch deck PDF")
    parser.add_argument("--source", help="Intro source")
    parser.add_argument("--context", help="Intro context / notes")
    parser.add_argument("--notes", help="Any initial notes")
    run(parser.parse_args())
