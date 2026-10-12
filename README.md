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

An `ELIGIBLE` verdict means only that constitutional review passed. It is not a DAO vote, proposal ratification, or execution authorization. Proposal voting and treasury execution are not implemented. Execution reports are self-reported and always `verified: false`; the contract cannot verify that an outside payment, transfer, or deliverable happened. Amendment ratification is owner approval, not DAO voting. Details: `docs/ARCHITECTURE.md`, `docs/AMENDMENT_MODEL.md`,
`docs/APPEAL_MODEL.md`, `docs/PRECEDENT_MEMORY_MODEL.md`, and what validators do and do not verify: `docs/TRUST_MODEL.md`.

## Evidence status (read this before relying on any claim)

| Claim | Status |
| --- | --- |
| Contract tests, mocked LLM and web (`tests/direct`) | 1551 passed, 0 failed, 0 skipped (these prove contract logic, **not** real model behavior) |
| GLSim integration (`tests/integration`, 6 files) | 26 passed, 9 skipped (the skipped cases need real LLM validators) |
| Frontend (vitest) | 349 passed, 8 skipped; typecheck, lint and production build clean |
| **Submission release (intended)** | `0xc942901dbB024CDb922f9D71B91024ea919a9F94` on StudioNet, deploy tx `0x90181a7c05c41d0adbb9af4072461a23ce9f755dec1081e3a3adf42d858d219a`, FINALIZED, `MAJORITY_AGREE`. Deployed source = `contracts/charter_gate.py` at commit `a486010`, SHA-256 `e1041e625bccf8316f979d247d425e29036ec398b299a9321e0737b39ecbd64e`, 72 methods, schema identical to `docs/charter_gate.schema.json`. Explorer: https://explorer-studio.genlayer.com/address/0xc942901dbB024CDb922f9D71B91024ea919a9F94 |
| Live behavior observed on that contract | Amendment #001 was evaluated COMPATIBLE, owner-approved and applied (charter v3→v4); #002 was evaluated CONFLICTING with `[s3]` and rejected; #003 was superseded. Steward test amendment #004 was evaluated COMPATIBLE, owner-approved and applied (charter v4→v5), adding explicitly non-binding section s7. Reviews #001 (ELIGIBLE), #002 (REPAIRABLE), and #003 (INELIGIBLE), plus appeal #001 (AFFIRMED), are recorded. Exact hashes and readbacks: `deployments/studionet.json`. |
| Frontend write-through coverage | The production frontend and owner wallet completed the StudioNet lifecycle: wallet connection, proposal submission (#3 and #5), evidence verification (#1 and #2), successful constitutional review (#3), appeal (#1), amendment proposal and compatibility evaluation (#4), owner approval, amendment application, and authoritative state readback. Each successful write listed in `docs/GOVERNANCE_VERIFICATION.md` finalized with successful GenVM execution. The separate CLI evaluation attempt finalized `NO_MAJORITY` with zero rounds and is not counted as successful; a separate review attempt rolled back without storing state. |
| Live frontend | https://chartergate.vercel.app, built for the contract above only |
| Earlier release-candidate contract | `0xC97b91Bd8ede96533B17EFf86D98cDff6c700736` (source `ccca5e4d…`, before the conflict-list check). Kept unchanged as history and superseded by the row above. |
| Governance switch | **ON** on the submission release. Owner activation `0xa20696724c4b39bf04e5162a840766a5274970e2135ec56a0a298c3f384c9272` finalized `MAJORITY_AGREE`; the live read returns `governance_enabled: true`. A signed same-text direct edit `0xf50cc5a16cf2d22c0404fa288dcff5d3ea0f10334181bd43d7734fd693f4a83f` rolled back with `EXPECTED:AMENDMENT_GOVERNANCE_REQUIRED`; charter and §1 were unchanged by that refused write. Current charter is v5 after amendment #004 was applied. Owner-controlled charter mutation is bootstrap governance only. See `docs/GOVERNANCE_VERIFICATION.md` for details. |
| Not observed live | a stored reasoned dissent on the submission release (two attempts returned `NO_MATERIAL_DISSENT`; one was stored on the earlier contract), `MODIFIED` or `REVERSED` appeals, repair after a reversal, a DEACTIVATE amendment, and wallet rejection or wrong-network handling in a real wallet. Validator disagreement and leader rotation have now been observed; the browser no-funding review attempt is recorded above. |
| Canonical deployment | **none** (`canonicalDeployment` is `null`). Every deployment is a verification deployment. |

No independent professional security audit has been performed.

Evidence assessment has a deterministic **30,000-character text cap per evidence item** after retrieval and normalization. The assessor and validators see the same prefix; text after that boundary is not examined and cannot substantiate a verified fact. A direct adversarial test places a decision-critical claim only after the boundary and confirms it remains `UNVERIFIABLE:NOT_GROUNDED`. This does not establish that the unexamined tail contains no contradictory information. See `docs/EVIDENCE_MODEL.md` and `tests/direct/test_evidence.py`.

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

Deployment is manual and deliberate; nothing here deploys automatically. After `genlayer deploy --contract contracts/charter_gate.py --args "<name>" "<description>"`, record the address, transaction, commit and source hash in `deployments/studionet.json`, then rebuild the frontend with the new `VITE_CHARTERGATE_ADDRESS`. The submission release is a verification deployment with amendment governance ON. Five earlier CLI activation attempts finalized `NO_MAJORITY`; the injected-wallet GenLayerJS call succeeded. Activation is irreversible. The live status and direct-edit rejection were verified on-chain. Owner-controlled charter mutation is bootstrap governance only; the intended normal policy path is amendment-enforced.

## Roadmap and state

| Stage | Scope | State |
| --- | --- | --- |
| 0 | Foundation, design system, wallet and transaction architecture | done |
| 1 to 5 | Charter, evidence, review, repair, precedent | frozen; deployed as verification deployments |
| 6 | Appeals and reasoned dissent | conditionally accepted (coverage gaps in `docs/STAGE_6_EQUIVALENCE.md`, section 10) |
| 7 to 9 | Amendments, governance guardrails, accountability | implemented; amendment proposal, evaluation, approval, application, governance guard, and readback exercised on StudioNet verification deployment |
| 10 | Product UI | implemented and live at https://chartergate.vercel.app; wallet-driven StudioNet lifecycle smoke test recorded above |
| 11 | Release audit | completed for the verification release; this is not a canonical production deployment, and remaining unverified behaviors are listed above |
