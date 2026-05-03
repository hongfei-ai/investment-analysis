# Investment Analysis — Current Agent Architecture

> **Purpose of this document.** A self-contained snapshot of the existing
> system's agent orchestration, data flow, and execution model — written so
> it can be pasted into a new Claude chat as the foundation for designing a
> broader investment-evaluation platform (sourcing, portfolio management,
> post-investment tracking, fund-level workflows). The system today covers
> only the **deal-evaluation phase** (sourcing-completed → IC memo
> produced); everything before sourcing and after the investment decision
> is out of scope and is called out explicitly in §13.

---

## 1. System scope (today)

The system runs **9 LLM-backed analysis agents** end-to-end on a single deal,
from "we just got introduced to a founder" through "we have an IC memo
ready." It is a tool for **evaluating one company at a time**.

Out of scope today:
- Sourcing (deal flow, dealer tracking, intro management)
- Comparable-deal memory (no cross-deal pattern recognition)
- Portfolio company tracking (post-investment)
- LP / fund-level reporting
- Term sheet / legal workflow
- Cap table / valuation modeling

These gaps are the natural extension surface and are mapped in §13.

---

## 2. Core abstractions

| Abstraction | Definition |
|---|---|
| **Deal** | A single company under evaluation. Identified by `deal_id` (a slug). All state for a deal lives in one nested JSON document plus two append-only sidecar logs. |
| **User** | An identity (email-only). Permissions are deal-scoped: `owner_email` and `collaborators[]`. |
| **Agent** | A function `(deal) → markdown_output`. Each agent has a system prompt, a per-deal user prompt template, optional tools (web_search), and a target field on the deal where its output is written. Reusable across triggers. |
| **Phase** | A bucket of agents with a strict directional dependency graph. Phase 1 → Phase 2 → Phase 3. |
| **Trigger surface** | Anything that invokes an agent: CLI script, Streamlit button, Notion poller. All three call into the same `shared.py` primitives. |

---

## 3. The deal data model

Every deal is one nested JSON document with this skeleton:

```jsonc
{
  "deal_id": "acme-robotics",         // slug, primary key
  "company_name": "Acme Robotics",
  "owner_email": "ada@example.com",
  "collaborators": ["grace@example.com"],
  "_version": 14,                     // optimistic lock counter
  "date_created": "2026-04-01T10:00Z",
  "updated_at":   "2026-04-22T14:23Z",
  "deal_stage":   "diligence",         // sourced/contacted/met/diligence/ic/term_sheet/invested/passed/tracking
  "status":       "post-diligence",    // pre-call/diligence/post-diligence/ic-prep/complete (agent-pipeline phase)
  "priority":     "H",                 // H / M / L
  "is_active":    true,
  "next_step":    "Schedule technical deep-dive",

  // Inputs collected pre-Phase 1 — drive Agent 1 + downstream
  "inputs": {
    "founder_name":       "Ada Lovelace",
    "founder_linkedin":   "https://linkedin.com/in/ada",
    "company_website":    "https://acme.com",
    "intro_source":       "Grace Hopper",
    "intro_context":      "Worked together at NVIDIA",
    "initial_notes":      "...",
    "deal_champion":      "Hongfei",
    "pitch_deck_path":    "deck.pdf",
  },

  // Phase 1 (Agent 1 only)
  "pre_call": {
    "research_output":     "...markdown...",
    "suggested_questions": [],
    "human_notes":         ""
  },

  // Captured between Phase 1 and Phase 2 (the actual call)
  "call_notes": {
    "raw_transcript_or_notes": "...",
    "date_of_call":            "2026-04-15",
    "attendees":               [],
    "human_annotations":       ""
  },

  // Phase 2 (Agents 2–6)
  "diligence": {
    "tracker":                       "...",   // Agent 2
    "technical_diligence_required":  true,    // parsed from Agent 2 output
    "founder_diligence":             "...",   // Agent 3
    "market_diligence":              "...",   // Agent 4
    "reference_check":               "...",   // Agent 5 (legacy field name; now traction intel)
    "thesis_check":                  "...",   // Agent 6
    "human_review_notes":            ""
  },

  // Phase 3 (Agents 7–9)
  "ic_preparation": {
    "pre_mortem":     "...",  // Agent 7
    "ic_simulation":  "...",  // Agent 8
    "ic_memo":        "...",  // Agent 9
    "human_edits":    ""
  }
}
```

---

## 4. Storage layout

Filesystem-primary. One source of truth; everything else (Notion mirror, etc.)
is a derived view.

```
deals/{deal_id}.json           # the deal document above
deals/{deal_id}.runs.jsonl     # append-only: one record per agent run
                               # {ts, agent_key, status, by_user, started_at, ended_at}
deals/{deal_id}.audit.jsonl    # append-only: metadata changes, ownership claims, etc.
                               # {ts, actor, action, details}
outputs/{deal_id}/{agent_key}.md  # rendered markdown per agent (the human-readable artifact)
inputs/{deal_id}/...              # uploaded PDFs / decks / source docs
```

Migrations are lazy and idempotent. `load_deal()` runs every migration on every
read, so old deal JSONs get backfilled with new fields automatically.

---

## 5. The 9 agents

Each agent module exports `AGENTN_SYSTEM` (the role/discipline prompt) and
`agentN_user(deal)` (the per-deal instruction template). Tools and token caps
live next to each agent.

### Phase 1 — Pre-Call

| # | Agent | Role | Model | Tools | Reads | Writes |
|---|---|---|---|---|---|---|
| **1** | `agent1_precall` | Pre-Call Research Brief — 10-section structured brief on founder + venture, before the first call. | Opus 4.7 | web_search | `inputs.*`, `_deck_text` | `pre_call.research_output` |

**Discipline highlights** (Agent 1):
- Strict heading hierarchy (`## N. Major` / `### N.N Subtitle`); H1 and H4 banned.
- Confidence tags (`[HIGH CONFIDENCE]`, `[MEDIUM CONFIDENCE]`, `[LOW CONFIDENCE / INFERRED]`, `[INSUFFICIENT DATA — ...]`) on every inferred claim.
- 10 sections: Founder Profile / Public Voice / Venture Hypothesis / Pitch Deck / Red Flags / Execution Timeline / Already-Known vs Call-Only / Critical Questions / Deal-Breakers / Raw Data Appendix.

### Phase 2 — Post-Call Diligence

Sequential execution of Agent 2 first (downstream agents depend on its
tracker output), then Agents 3–6 in parallel.

| # | Agent | Role | Model | Tools | Reads | Writes |
|---|---|---|---|---|---|---|
| **2** | `agent2_diligence_mgmt` | Reads call notes + brief, generates **P1/P2/P3 questions** ranked by IC-decisiveness; routes each P1 to a downstream agent. | Sonnet 4.6 | none | `pre_call.research_output`, `call_notes.*` | `diligence.tracker` (+ `technical_diligence_required` boolean) |
| **3** | `agent3_founder_diligence` | Founder deep dive. Produces verdict: **High Conviction / Worth Partner Meeting / Pass for Now / Hard Pass**. | Opus 4.7 | none | All Phase 1 + Agent 2 tracker | `diligence.founder_diligence` |
| **4** | `agent4_market_diligence` | TAM/SAM/SOM, competitive landscape, regulatory/timing, APAC dynamics. Material Technical Claims subsection appears iff Agent 2 flagged it. | Opus 4.7 | web_search (25 uses) | All Phase 1 + Agent 2 tracker | `diligence.market_diligence` |
| **5** | `agent5_reference_check` | **Customer & Traction Intelligence** (closed-book; renamed from "reference check"). Sections: traction analysis, data quality, voices already in the record (exclusion set), prioritized profiles to source. **Never invents names** — archetypes only. | Sonnet 4.6 | none | All Phase 1 + Agent 2 tracker | `diligence.reference_check` |
| **6** | `agent6_thesis_check` | Stage / sector / geography / active-theme alignment / portfolio synergies / bias check. Produces explicit verdict: **Strong / Moderate / Weak / No Fit**. | Sonnet 4.6 | none | All Phase 1 + Agents 2–5 | `diligence.thesis_check` |

**Post-save hook on Agent 2**: parses `technical_diligence_required` boolean
from the tracker output → controls Agent 4's behavior on next run.

**Post-save hook on Agent 6**: if all 5 Phase 2 outputs are populated, promotes
`status` from `"diligence"` → `"post-diligence"` (gates Phase 3).

### Phase 3 — IC Preparation

Strictly sequential — each agent depends on the prior one's full output.

| # | Agent | Role | Model | Tools | Reads | Writes |
|---|---|---|---|---|---|---|
| **7** | `agent7_premortem` | **Pre-Mortem.** KILL-vs-MEDIOCRE scenario matrix, observable signals at 6/12/18-month horizons, deal-killer threshold, consistency check vs Agent 6's verdict, shared-blind-spot check. | Sonnet 4.6 | none | All Phase 2 outputs | `ic_preparation.pre_mortem` |
| **8** | `agent8_ic_simulation` | **IC Simulation.** Champion names 3–5 *must-haves* for a 20x outcome; 4 personas (Champion / Skeptic / Domain Expert / Generalist) score those must-haves with rationale per cell. Domain Expert specialized per deal type (DeepTech / B2B SaaS / Consumer / Fintech). Closes with structured recommendation: **INVEST / CONDITIONAL / TRACK / PASS**. | Sonnet 4.6 | none | All Phase 2 + Agent 7 (verbatim) | `ic_preparation.ic_simulation` |
| **9** | `agent9_ic_memo` | **IC Memo.** Synthesizes everything into January Capital institutional voice (third person, bullet-driven). Treats Agent 8's must-haves as Value Creation theses and the Recommended Outcome as the memo's ask. **No** numerical scoring rubrics in the final memo. | Opus 4.7 | none | Everything | `ic_preparation.ic_memo` |

**Post-save hook on Agent 9**: promotes `status` to `"complete"`.

---

## 6. Dependency graph

```
                    ┌─────────────────┐
                    │  Agent 1        │  uses inputs only (founder, LinkedIn, deck, intro)
                    │  pre-call brief │
                    └────────┬────────┘
                             │ pre_call.research_output
                             ▼
                  (human captures call notes)
                             │
                             ▼
                    ┌─────────────────┐
                    │  Agent 2        │  uses brief + call notes
                    │  P1/P2/P3 mgmt  │
                    └────────┬────────┘
                             │ diligence.tracker  (+ technical_diligence_required)
              ┌──────┬───────┼───────┬──────┐
              ▼      ▼       ▼       ▼      ▼
         ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐
         │ A3  │ │ A4  │ │ A5  │ │ A6  │   (parallel)
         │found│ │mkt  │ │trax │ │thesi│
         └─────┘ └─────┘ └─────┘ └─────┘
              │      │      │      │
              └──────┴──────┴──────┘
                          │ all of Phase 2
                          ▼
                    ┌─────────────────┐
                    │  Agent 7        │
                    │  pre-mortem     │
                    └────────┬────────┘
                             │ pre_mortem
                             ▼
                    ┌─────────────────┐
                    │  Agent 8        │
                    │  IC simulation  │
                    └────────┬────────┘
                             │ ic_simulation
                             ▼
                    ┌─────────────────┐
                    │  Agent 9        │
                    │  IC memo        │
                    └─────────────────┘
```

**Critical inter-agent contracts** (worth pinning if you redesign):
- Agent 6's verdict label (`Strong / Moderate / Weak / No Fit`) is consumed verbatim by Agent 7's consistency check.
- Agent 7's section headers (`Scenario Matrix`, `Deal-Killer Threshold`, `Shared Blind Spot Check`) are explicitly referenced in Agent 8's prompt.
- Agent 8's `must-haves` and `Recommended Outcome` (one of INVEST/CONDITIONAL/TRACK/PASS) are explicitly named in Agent 9's prompt as anchors for Value Creation theses and the memo ask.
- Confidence tags propagate from internal-research agents (1–7) but are stripped by Agent 9 (institutional memo voice forbids them).

---

## 7. Models & token economics

| Tier | Agents | Why |
|---|---|---|
| **Opus 4.7** (heavy reasoning) | 1, 3, 9 | Net-new research synthesis (1, 3) or final-output writing in firm voice (9). |
| **Sonnet 4.6** (thinner) | 2, 5, 6, 7, 8 | Ingest already-researched material, structure / score / classify it. |

Total token budget for a complete pipeline:
- Phase 1: ~16k tokens output × 1 agent = ~16k
- Phase 2: ~8k–16k × 5 agents ≈ 50k–60k
- Phase 3: ~8k–12k × 3 agents ≈ ~28k

Cost is dominated by Phase 2 (5 agents, two of them on Opus). Prompt caching
with `cache_control: ephemeral` cuts repeat-cost ~30–50% within a 5-min window.

---

## 8. Trigger surfaces

The same agent code can be invoked three independent ways. All three end up
calling identical primitives in `shared.py`.

| Surface | Code | User context | Trigger model |
|---|---|---|---|
| **CLI** | `run_phase1.py`, `run_phase2.py`, `run_phase3.py` | `--user <email>` arg | Manual; ThreadPoolExecutor inside Phase 2 for the 4-way fan-out. |
| **Streamlit** (out of scope here) | `pages/deal.py` | `session_state.current_user_email` | Click "Run Agent N" or "Run Phase N" button. Streams tokens live into per-section cards. |
| **Notion poller** | `integrations/poller.py` (background thread in `app.py`) | resolved from Notion `last_edited_by` → email | Poll Deals DB every 30 s for rows where `Run Agent` property is set. Claim atomically by clearing the property. |

The Notion path is a polling worker, **not** webhooks — works on Notion free
tier and is naturally idempotent (clearing the trigger property is the
dequeue). The poller also reconciles 6 human-editable fields back from Notion
into the JSON: `deal_stage`, `priority`, `next_step`, `owner_email`,
`collaborators`, `notes`.

---

## 9. Auth & permissions

Deal-scoped, not project-scoped. Three roles:

| Role | Definition | Can |
|---|---|---|
| **Owner** | `deal.owner_email == user.email` | Run agents, edit metadata, change ownership |
| **Collaborator** | `user.email in deal.collaborators` | Run agents, edit metadata |
| **Viewer** | Authenticated but not owner/collaborator | Read everything, run nothing, edit nothing |
| **Unassigned** | `deal.owner_email == "unassigned"` | Anyone authenticated can **claim** the deal → becomes owner |

Enforcement is at the storage layer:
- `shared.save_deal(deal, user)` → calls `require_editor(deal, user)` → raises `PermissionError` if not allowed
- `shared.save_output(deal_name, agent_key, content, user)` → same gate
- The Notion poller does an explicit `is_editor()` check **before spending tokens** so unauthorized triggers fail fast.

The auth module (`auth.py`) is Streamlit-decoupled — `User`, `is_editor`,
`require_editor` are pure functions and importable from headless contexts.

---

## 10. Concurrency

- **Optimistic locking** via `_version`: every save bumps the counter. Two
  simultaneous saves: the second wins; a `VersionMismatch` is raised if the
  caller passed an `expected_version`.
- **Atomic writes**: `fcntl.flock` advisory lock + tmp file + `os.replace`.
  The on-disk file is never partially written.
- **Phase 2 parallelism**: 4 agents (3, 4, 5, 6) run in threads, each writing
  to a different field. Their saves serialize on the file lock but don't
  conflict (different fields).
- **Append-only logs** (`runs.jsonl`, `audit.jsonl`) — no locking needed; OS
  guarantees atomic line appends.

---

## 11. Observability

- **`runs.jsonl`** records every agent invocation: started, ended, status
  (`running`/`done`/`error`), by_user. Status updates are written at start
  AND end so a crashed run is visible as a `running` entry that never got a
  matching `done` — picked up by the stale-run reaper.
- **`audit.jsonl`** records human actions: ownership claims, metadata edits,
  collaborator changes, deal creation.
- **Activity feed** (in the UI, out of scope here) merges the two and renders
  newest-first.
- The Notion poller pushes status (`Running` / `Done` / `Failed`) to the deal
  row's Status property and a one-line error to the Last Error property when
  things blow up.

---

## 12. Extension principles (non-obvious)

1. **Filesystem stays primary.** Any new storage destination (Notion,
   Postgres, vector DB) is a *mirror*. Optimistic locking and atomic writes
   are not negotiable.
2. **Agents never call each other.** They read state from the deal JSON.
   Orchestration lives in the runner, not in the prompts.
3. **Each agent has exactly one target field.** No agent writes to two
   places. This is what makes Phase 2 parallelism safe.
4. **Post-save hooks are the state machine.** `status` only changes via
   post-save callbacks. There's no separate state-machine module — the
   agents' completion drives state transitions.
5. **Prompts encode contracts, not just style.** Section names and verdict
   labels are protocol — downstream agents reference them by name.
6. **Confidence tags propagate**, but Agent 9 strips them (institutional
   memo). Anything that surfaces externally bypasses the tagged version.
7. **Two-way sync only on the six fields humans naturally edit.** Outputs
   are one-way push.

---

## 13. What's NOT in the system today (extension surface)

This is where the next conversation should focus. Each of these is a coherent
feature area the current architecture *doesn't* address.

### Pre-evaluation: Sourcing & deal flow

The system today starts at "we're already evaluating this deal." It assumes
someone manually created a deal record. Missing:

- **Inbox / intro tracking.** Where do deals come from? Who introduced? When?
  Is there a follow-up obligation?
- **Source-quality scoring.** Which intro sources have historically led to
  invested deals?
- **Founder cold-outreach.** Outbound sourcing pipeline.
- **Deal velocity tracking.** How long has a deal been at each stage?
  Stalled-deal detection beyond the simple `>14 days no update` rule.
- **Sourcing-stage agents** (e.g., "Agent 0: Triage" — does this fit the
  thesis enough to spend Phase 1 tokens on?).
- **De-duplication / fuzzy matching.** If "Acme" and "Acme Robotics" are the
  same company in different intro contexts, they're separate deals today.

### Cross-deal memory

The system has zero cross-deal awareness today. Every deal is evaluated in
isolation. Missing:

- **Comparable-deal retrieval.** "We saw a similar founder/market combo last
  year — what did we decide?"
- **Pattern recognition.** "We've passed on 3 fintechs in the last 6 months
  citing regulatory risk. What's our actual track record on that prediction?"
- **Thesis evolution.** Active themes change; old deals were evaluated under
  old thesis. There's no notion of "what would Agent 6 say about this deal
  today vs. when we evaluated it?"
- **Embedding / vector search** over outputs for "find me deals where the
  founder had a similar profile to X."
- **Pass-decision retrospectives.** Did any deal we passed on become a
  unicorn? Why did we pass? What signal would have flipped us?

### Reference call execution & evidence collection

Agent 5 *suggests* people to talk to but doesn't track the outcome. Missing:

- **Reference call log.** Who did we actually talk to? When? What did they
  say? (As structured data, not free-form notes.)
- **Quote bank.** Specific quotes attached to scenarios in Agent 7's matrix.
- **Evidence ledger.** "This claim is supported by [reference call X], [data
  room doc Y], [LinkedIn search Z]." Inverse of the current "Sources Evaluated"
  prose section.
- **Customer reference workflow.** Schedule, prepare questions, capture,
  attribute.

### Investment decision & post-IC

The pipeline ends at "memo produced." Missing:

- **IC vote tracking.** Who voted yes/no/abstain? With what comments?
- **Term sheet drafting.** No legal-doc workflow.
- **Cap table / valuation.** No quant model.
- **Decision execution.** "We decided to invest $X — now what?"

### Post-investment / portfolio

Once a deal becomes `invested`, the system stops paying attention. Missing:

- **Portfolio company state.** Stage, round, ARR, headcount, runway.
- **KPI tracking.** Monthly metrics ingestion (manual or via API).
- **Board meeting prep.** Recurring agent that synthesizes the last quarter.
- **Pre-mortem auditing.** Agent 7 emitted observable signals at 6/12/18-month
  horizons. Did they fire? Are we tracking?
- **Re-up evaluation.** When a portfolio company raises again, run a Phase
  2-style refresh.
- **Founder communication log.** Updates received, asks made, intros given.

### Fund-level

The system has no concept of "fund" or "fund vintage." Missing:

- **Capital deployment tracking.** How much have we deployed? At what pace?
- **Concentration limits.** Sector caps, stage caps, geo caps.
- **LP reporting artifacts.** Quarterly reports, partner letters.
- **Committee composition.** IC quorum rules, partner approval thresholds.
- **Multi-fund deals.** Same deal evaluated for two different funds with
  different theses.

### Cross-cutting infrastructure gaps

- **Search.** No full-text or semantic search across outputs today.
- **Notification routing.** Slack notifications are global (one channel);
  no per-user / per-deal routing rules.
- **Scheduling.** No "remind me in 2 weeks if this hasn't moved."
- **Document versioning.** Outputs are overwritten on re-run. The runs.jsonl
  records *that* an agent ran but not the previous output.
- **Compare-runs.** No way to diff Agent 6 output from 30 days ago vs. today.

---

## 14. Open architectural questions

Specific decisions that the next phase will need to make:

1. **Storage migration.** When the system grows past ~500 deals, scan-on-load
   becomes visible. Should the next storage be Postgres? SQLite? A vector DB
   for semantic search? What about a hybrid?

2. **Sourcing → Evaluation handoff.** Where does a deal exist *before* it's
   in the deals/ directory? Is there a "lead" stage that's lighter-weight
   than a full deal?

3. **Agents that work across deals.** Today every agent is `(deal) →
   markdown`. A "thesis update" agent or a "comparable deals" agent needs
   `(deals[]) → ...`. What's the right contract?

4. **Human-in-the-loop checkpoints.** Today agents either complete or fail.
   No agent says "wait, I need an answer to X before I continue." Should
   they?

5. **Agent versioning.** When Agent 6's prompt changes, are old `thesis_check`
   outputs still meaningful? Should outputs carry a prompt-version stamp?

6. **Multi-tenancy / multi-fund.** January-Capital-specific theses are
   currently hardcoded. If the same codebase served a different VC, how
   would that work?

7. **Real-time vs. batch.** Most agents take 30s–5min and are async-friendly.
   But IC meetings happen at scheduled times — should there be
   pre-warming / batch-mode runs the night before?

8. **Evidence addressing.** Right now claims live inside paragraphs. Should
   every claim be a first-class object with an ID, so reference calls can
   later confirm/refute specific claims?

---

## 15. File layout (current)

```
investment-analysis/
├── agents/
│   ├── _common.py              # OUTPUT_FORMAT_INSTRUCTIONS shared by all agents
│   ├── prompts.py              # re-export shim for AGENT_N_SYSTEM + agent_n_user
│   ├── agent1_precall.py       # AGENT1_TOOLS, AGENT1_MAX_TOKENS, system + user
│   ├── agent2_diligence_mgmt.py
│   ├── agent3_founder.py
│   ├── agent4_market.py        # AGENT4_TOOLS, AGENT4_MAX_TOKENS
│   ├── agent5_traction.py
│   ├── agent6_thesis.py
│   ├── agent7_premortem.py
│   ├── agent8_ic_sim.py
│   └── agent9_ic_memo.py
├── auth.py                     # User dataclass, is_editor, require_editor (Streamlit-free)
├── audit.py                    # append_audit, read_audit, read_activity (merges with runs.jsonl)
├── shared.py                   # call_claude, stream_claude, save_deal, save_output, etc.
├── migrations/
│   └── 001_add_owner_and_stage.py  # lazy idempotent schema migration
├── integrations/               # Notion + Slack push/poll layer (zero Streamlit deps)
│   ├── notion_client.py
│   ├── notion_push.py
│   ├── poller.py
│   ├── agent_runner.py         # headless registry; mirrors pages/deal.py::AGENT_REGISTRY
│   ├── slack_push.py
│   └── bootstrap_notion.py     # one-shot Notion DB schema creator
├── run_phase1.py               # CLI entry: run Agent 1 on a deal
├── run_phase2.py               # CLI entry: run Agents 2–6 (2 sequential, 3–6 parallel)
├── run_phase3.py               # CLI entry: run Agents 7–9 sequentially
├── pages/                      # Streamlit UI (out of scope for this doc)
├── ui/                         # Streamlit UI components (out of scope)
├── tests/                      # 156 tests as of writing; pytest
└── deals/, outputs/, inputs/   # runtime data — gitignored
```

---

## 16. TL;DR

The current system is **a directed acyclic graph of 9 LLM agents** that runs
once per deal, from intro to IC memo. It's clean, well-decoupled, and has
two solid invariants: **filesystem-primary storage with optimistic locking**,
and **agents never call each other — they communicate via the deal JSON**.

What it lacks is everything *around* the evaluation phase: sourcing inputs,
cross-deal memory, evidence collection, decision execution, post-investment
tracking, and fund-level operations. Those are the surface area for the next
architectural pass.
