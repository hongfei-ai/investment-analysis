# January Capital — Multi-Agent Investment Analysis System v2.0

## Setup

### 1. Install dependencies
```
pip install -r requirements.txt
```

### 2. Set your API key
Copy `.env.example` to `.env` and fill in your key:
```
ANTHROPIC_API_KEY=your_key_here
```

Get your key from: https://console.anthropic.com

### 3. Folder structure
```
investment-analysis\
  agents\         — one file per agent (do not edit directly)
  inputs\         — drop pitch decks, call notes, etc. here
  outputs\        — all agent outputs saved here
  deals\          — one JSON file per deal (the shared knowledge store)
  run_phase1.py   — Pre-Call Research
  run_phase2.py   — Post-Call Diligence (parallel)
  run_phase3.py   — IC Preparation
```

---

## Usage

### Phase 1 — Before the founder call
```
python run_phase1.py --deal "CompanyName" --founder "Founder Name" --linkedin "https://linkedin.com/in/..."
```
Optional: `--deck inputs/deck.pdf` `--website https://company.com`

Output saved to: `outputs/[CompanyName]/agent1_precall.md`

### Phase 2 — After the founder call
Drop your call notes into `inputs/` as a `.txt` or `.md` file, then:
```
python run_phase2.py --deal "CompanyName" --notes inputs/call_notes.txt
```
Runs Agent 2 (Diligence Mgmt), then launches Agents 3, 4, 5, 6 in parallel.
Output saved to: `outputs/[CompanyName]/agent2_diligence_mgmt.md` + agent3/4/5/6

### Phase 3 — IC preparation
```
python run_phase3.py --deal "CompanyName"
```
Runs Agent 7 (Pre-Mortem) → Agent 8 (IC Simulation) → Agent 9 (IC Memo) in sequence.
Final memo: `outputs/[CompanyName]/agent9_ic_memo.md`

---

## Human checkpoints
- **Checkpoint 1:** Review `agent1_precall.md` before the founder call
- **Checkpoint 2:** Review all Phase 2 outputs before running Phase 3
- **Checkpoint 3:** Review `agent9_ic_memo.md` before distributing
