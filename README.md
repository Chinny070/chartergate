# CharterGate

A constitutional review layer for DAOs, built on [GenLayer](https://www.genlayer.com).

A DAO stores a natural-language constitution. Proposals are judged against it, using live web
evidence and prior rulings, by an Intelligent Contract whose result is settled by GenLayer's
AI-validator consensus. The goal is for every decision to be inspectable: the clause applied,
the evidence used, the timestamp, the validator outcome.

> **Status: Stage 1 (charter + proposals).** The contract stores a DAO charter (owner-managed
> sections with a version counter) and accepts proposals, recorded as `SUBMITTED`. **Nothing
> reviews, judges or approves proposals yet**: no AI adjudication, web evidence, appeals,
> precedent or voting. Not deployed.

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
| `contracts/` | `charter_gate.py`: the Stage 1 charter and proposal contract. |
| `frontend/` | React app: shell, design tokens, wallet/network layer, transaction state, charter and proposal pages. |
| `tests/direct/` | Fast contract tests (genlayer-test direct mode): access control, validation, versioning, timestamps, acceptance scenario. |
| `tests/integration/` | Consensus/network tests (empty until Stage 3+). |
| `deployments/` | Manual deployment records. `studionet.json` holds the Stage 1.1 and Stage 1.2 verification deployments (neither is canonical). |
| `docs/` | `ARCHITECTURE.md` (verified APIs, data model, access control) and `charter_gate.schema.json` (generated schema). |

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
npm test            # vitest (transaction-state model, contract decoders)
```

Contract (from repo root):

```bash
genvm-lint check contracts/charter_gate.py --json   # lint
genvm-lint schema contracts/charter_gate.py --json -o docs/charter_gate.schema.json   # local schema
python -m pytest tests/direct/ -v                    # direct tests
gltest tests/integration/ -v -s                      # integration tests (none yet)
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
| 2 | Mocked adjudication | planned |
| 3 | Live web evidence | planned |
| 4 | Consensus semantics (leader/validator) | planned |
| 5 | Appeals | planned |
| 6 | Precedent | planned |
| 7 | Frontend feature pages | planned |
| 8 | Schema-driven integration after manual deploy | planned |
| 9 | End-to-end smoke test | planned |

See `docs/ARCHITECTURE.md` for what has and has not been verified against the GenLayer SDK.
