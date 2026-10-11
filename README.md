# CharterGate

A DAO stores a natural-language constitution. Proposals are judged against it, using public web evidence and prior rulings, by a GenLayer Intelligent Contract whose result is settled by validator
consensus. Every decision is meant to be inspectable: the clause applied, the evidence used, the timestamp and the validator outcome.

There is **no application backend and no database**: a React frontend talks to the contract through `genlayer-js` and an injected wallet.

## What is implemented

* **Charter** with immutable version history and owner access control (Stage 1).
* **Evidence vault**: validator-agreed structured evidence from public web pages (Stage 2).
* **Constitutional review** against the charter in force at submission (Stage 3), **repair** of repairable proposals (Stage 4), advisory **precedent** under an authority boundary (Stage 5).
* **Appeals** with a non-controlling reasoned dissent. GenVM exposes no validator minority opinion, so a dissent is an AI-generated alternative reading, never a vote (Stage 6).
* **Amendments** (propose, model compatibility advice, owner approval, apply, supersede), a one-way **governance switch**, and **execution accountability** (Stages 7 to 9).
* **Product UI** (Stage 10) and a **release audit** (Stage 11).

There is no voting or treasury execution. Ratification is the owner. Execution reports are self-reported and always `verified: false`. Details: `docs/ARCHITECTURE.md`, `docs/AMENDMENT_MODEL.md`,
`docs/APPEAL_MODEL.md`, `docs/PRECEDENT_MEMORY_MODEL.md`, and what validators do and do not verify: `docs/TRUST_MODEL.md`.

## Evidence status (read this before relying on any claim)

| Claim | Status |
| --- | --- |
| Contract tests, mocked LLM and web (`tests/direct`) | 1551 passed, 0 failed, 0 skipped (these prove contract logic, **not** real model behavior) |
| GLSim integration (`tests/integration`, 6 files) | 26 passed, 9 skipped (the skipped cases need real LLM validators) |
| Frontend (vitest) | 349 passed, 8 skipped; typecheck, lint and production build clean |
| Release-candidate contract on StudioNet | `0xC97b91Bd8ede96533B17EFf86D98cDff6c700736`, deploy tx `0x959d4bd3dd68f846bc50b76bae742297c57a64ed67bb4594e01d7026038ba1b3`, finalized; deployed source hash `ccca5e4d6f00161a401b3e3505f65db4b26ebf50c87948ffb94e076cf4c11a28`, 72 methods |
| Live behavior observed on that contract | amendments proposed, model-evaluated (COMPATIBLE and CONFLICTING), approved, applied, refused as stale or unauthorized; execution reports; an AFFIRMED appeal and a stored dissent. Transaction hashes: `deployments/studionet.json` |
| Live frontend | https://chartergate.vercel.app, built for the contract above |
| **Newer than the deployed contract** | the working tree adds one validator tightening (amendment evaluation also compares the conflicting-section list; source hash `e1041e62…`). It is **not deployed**. The deployed contract runs the older source. |
| Governance switch | **OFF** on the live contract (irreversible; deliberately not activated). Tested on a separate throwaway deployment: `docs/GOVERNANCE_VERIFICATION.md` |
| Not observed live | `MODIFIED` or `REVERSED` appeals, repair after a reversal, validator disagreement on amendment transactions, any account other than the owner on the release contract |
| Canonical deployment | **none** (`canonicalDeployment` is `null`). Every deployment is a verification deployment. |

No independent professional security audit has been performed.

## Repository layout

| Path | Purpose |
| --- | --- |
| `contracts/charter_gate.py` | The Intelligent Contract. |
| `frontend/` | React app (Vite, React 19, genlayer-js 1.1.8). |
| `tests/direct/` | Contract tests in genlayer-test direct mode (web and LLM mocked). |
| `tests/integration/` | GLSim tests; real-LLM cases are skipped unless `CHARTERGATE_REAL_GENVM=1` on StudioNet. |
| `deployments/studionet.json` | Manual deployment records (historical records are kept, never rewritten). |
| `docs/` | Architecture, per-stage models and equivalence notes, trust model, release candidate, governance verification, generated schema. |

## Target network

StudioNet, chain id **61999**, RPC `https://studio.genlayer.com/api`, gasless. The contract address is baked into the frontend build from `VITE_CHARTERGATE_ADDRESS` (see `frontend/.env.example`);
unset means "not deployed" and the UI says so. Writes are blocked unless the wallet is on chain 61999. StudioNet limits reads to about 30 a minute; the app spaces reads and retries transient failures.

## Setup (verified versions)

Python 3.12.10, Node 24.14.0 (npm 11.9.0), `genlayer` CLI 0.39.2. Python tooling is pinned in `requirements-dev.txt`; the frontend is pinned by `frontend/package-lock.json`.

```bash
pip install -r requirements-dev.txt
npm install -g genlayer
cd frontend && npm ci && cp .env.example .env   # set VITE_CHARTERGATE_ADDRESS after a deployment
```

On Windows set `PYTHONIOENCODING=utf-8` before `genvm-lint check` (its success mark crashes a legacy code page).

## Commands

```bash
# frontend (from frontend/)
npm run typecheck && npm run lint && npm test && npm run build

# contract (from the repo root)
genvm-lint check contracts/charter_gate.py
genvm-lint schema contracts/charter_gate.py --json -o docs/charter_gate.schema.json
python -m pytest tests/direct -q                 # about 10 minutes

# integration: use a FRESH simulator for each test file (a second deploy in one GLSim process fails)
glsim --port 4000 --validators 5 --no-browser
gltest tests/integration/test_governance_live.py -q
```

## Deployment

Deployment is manual and deliberate; nothing here deploys automatically. After `genlayer deploy --contract contracts/charter_gate.py --args "<name>" "<description>"`, record the address, transaction,
commit and source hash in `deployments/studionet.json`, then rebuild the frontend with the new `VITE_CHARTERGATE_ADDRESS`. Enabling amendment governance is a separate, one-way, owner decision.

## Roadmap and state

| Stage | Scope | State |
| --- | --- | --- |
| 0 | Foundation, design system, wallet and transaction architecture | done |
| 1 to 5 | Charter, evidence, review, repair, precedent | frozen; deployed as verification deployments |
| 6 | Appeals and reasoned dissent | conditionally accepted (coverage gaps in `docs/STAGE_6_EQUIVALENCE.md`, section 10) |
| 7 to 9 | Amendments, governance guardrails, accountability | implemented; exercised live on the release-candidate verification deployment (see the evidence table) |
| 10 | Product UI | live at https://chartergate.vercel.app |
| 11 | Release audit | audit remediation in progress: one validator fix is local and awaits a redeploy |
