# CharterGate

A constitutional review layer for DAOs, built on [GenLayer](https://www.genlayer.com).

A DAO stores a natural-language constitution. Proposals are judged against it, using live web
evidence and prior rulings, by an Intelligent Contract whose result is settled by GenLayer's
AI-validator consensus. The goal is for every decision to be inspectable: the clause applied,
the evidence used, the timestamp, the validator outcome.

> **Status: Stage 6 (appeals and reasoned dissent), local only.** The contract stores a DAO charter with immutable history, accepts proposals and **public web
> evidence** verified through validator consensus, records an immutable **constitutional review** of each proposal against the charter in force when it was
> submitted, lets a `REPAIRABLE` proposal be repaired as an immutable revision with a full re-review, and now gives reviews **constitutional memory**: a bounded set
> of earlier rulings under the exact same charter rule, cited as followed or distinguished. Precedent is advisory and never replaces the charter or current evidence: the findings are produced by a model call that never sees precedent (Stage 5.1).
> Stage 6 adds **appeals**: the proposer can challenge an adverse ruling on the closed record it judged (appeal is not repair), which creates an immutable appellate decision above the original review, and an
> optional, truthfully labelled, non-controlling **reasoned dissent** (GenVM exposes no validator minority opinion, so it is an AI-generated alternative, not a vote).
> **Nothing handles voting or execution yet.** The Stage 6 contract is not deployed; the Stage 1 to 5 verification deployments are recorded in
> `deployments/studionet.json` (`canonicalDeployment` is still `null`). See `docs/PRECEDENT_MEMORY_MODEL.md`, `docs/STAGE_5_EQUIVALENCE.md` and `docs/STAGE_5_1_AUTHORITY_BOUNDARY.md`, `docs/APPEAL_MODEL.md` and `docs/STAGE_6_EQUIVALENCE.md`.

## Architecture

```
frontend (React + TypeScript + Vite)
   -> genlayer-js 1.1.8
   -> injected wallet (window.ethereum)
   -> GenLayer (StudioNet, chain id 61999)
   -> Intelligent Contract (Python, GenVM)
```

There is **no application backend and no database**. No Supabase, Firebase, Postgres, API
server or indexer. Persistent protocol state belongs in the contract; the frontend only reads
and writes through `genlayer-js`. Browser storage may only hold harmless UI preferences.

## Repository layout

| Path | Purpose |
| --- | --- |
| `contracts/` | `charter_gate.py`: the charter, proposal and evidence-vault contract. |
| `frontend/` | React app: shell, design tokens, wallet/network layer, transaction state, charter, proposal and evidence-vault pages. |
| `tests/direct/` | Fast contract tests (genlayer-test direct mode, web and LLM mocked): access control, validation, versioning, evidence, validator equivalence. |
| `tests/integration/` | Real-network evidence tests (GLSim and StudioNet). See `docs/ARCHITECTURE.md` for what GLSim can and cannot run. |
| `deployments/` | Manual deployment records. `studionet.json` holds the Stage 1.1 and Stage 1.2 verification deployments (neither is canonical). |
| `docs/` | `ARCHITECTURE.md` (verified APIs, per-stage notes), `STAGE_2_EQUIVALENCE.md` (how validators agree on web evidence), `EVIDENCE_MODEL.md` (record, statuses, hash, limits) and `charter_gate.schema.json` (generated schema). |

## Target network

- StudioNet, chain id **61999**, gasless (a 0 GEN balance is normal).
- Contract address is supplied via `VITE_CHARTERGATE_ADDRESS` (see `frontend/.env.example`).
  Unset means "not deployed"; the UI says so. After you deploy manually, put the address in `frontend/.env`.

## Setup

Requirements: Node 20+, Python 3.12+.

```bash
# tooling (one-time)
npm install -g genlayer
pip install genvm-linter genlayer-test

# frontend
cd frontend
npm install
cp .env.example .env   # optional until a contract is deployed
```

## Commands

Frontend (from `frontend/`):

```bash
npm run dev         # local dev server
npm run build       # typecheck + production build
npm run typecheck
npm run lint
npm test            # vitest (transaction layer, decoders, evidence components)
```

Contract (from repo root):

```bash
genvm-lint check contracts/charter_gate.py --json   # lint
genvm-lint schema contracts/charter_gate.py --json -o docs/charter_gate.schema.json   # local schema
python -m pytest tests/direct/ -v                    # direct tests

# integration: start a FRESH local simulator first (a second deploy in one GLSim process fails)
glsim --port 4000 --validators 5 --no-browser
gltest tests/integration/ -v -s                      # real web.get tests; real-GenVM cases are skipped
CHARTERGATE_REAL_GENVM=1 gltest tests/integration/ -v -s --network studionet   # LLM + render smoke cases
```

## Deployment

Deployment is **manual and deliberate**. Nothing in this repo deploys automatically, and CI must
not. When a stage is ready, you deploy with the GenLayer CLI, then record the address, tx hash,
commit and source hash in `deployments/studionet.json`.

## Roadmap

| Stage | Scope | State |
| --- | --- | --- |
| 0 | Foundation: structure, design system, wallet/tx architecture, tooling | done |
| 1 | Deterministic contract: charter sections, versioning, immutable history, proposals, owner access control, argument validation | done (verification deployments only; no canonical deployment) |
| 2 | Evidence vault: `web.get` / `web.render`, validator-agreed structured evidence, protocol timestamps, normalised-evidence hash | done locally (not deployed; live StudioNet validation pending) |
| 3 | Constitutional review of proposals | planned |
| later | Proposal repair, precedent, appeals, amendment governance, voting, execution, accountability | planned |

See `docs/ARCHITECTURE.md` for what has and has not been verified against the GenLayer SDK.
