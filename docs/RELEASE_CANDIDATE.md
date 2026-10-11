# Release candidate: Stages 7 to 11

Status: **locally verified, awaiting manual StudioNet deployment.** Nothing in this document is live evidence. No contract containing Stages 7 to 11 has been deployed,
no wallet signature was requested and nothing was pushed.

## 1. What this candidate adds to the Stage 6 contract

The contract source changed (new storage fields and 15 new methods; three existing owner methods now share one internal code path). A **new deployment is required**: a deployed contract
cannot gain methods or storage. The Stage 6 verification deployment (`0x050AFCd8B8a74Cbf8aaF682CA113bc510c6269e8`) and every earlier deployment stay untouched.

| Item | Value |
| --- | --- |
| Source file | `contracts/charter_gate.py` (ASCII only, `# v0.2.16` runner header unchanged) |
| Source hash (CRLF to LF, trimmed SHA-256) | `ccca5e4d6f00161a401b3e3505f65db4b26ebf50c87948ffb94e076cf4c11a28` |
| Methods | 72 (54 view, 18 write): 57 existing (byte-identical to the Stage 6 schema) plus 15 new |
| Schema | `docs/charter_gate.schema.json`, regenerated with `genvm-lint schema`; additive only |
| Network | StudioNet, chain ID 61999, RPC `https://studio.genlayer.com/api` |
| Deployer | `my-studionet-wallet` (`0xaffe15eec45b68835cc9e5b4ab85dd5deae8e70b`) |
| Constructor | `"Atlas DAO"` and `"A DAO that funds open-source infrastructure."` |

Deployment command (the installed CLI is 0.39.1; it uses the active network and account, so confirm both first with `genlayer network info` and `genlayer account show`):

```powershell
genlayer deploy --contract contracts/charter_gate.py --args "Atlas DAO" "A DAO that funds open-source infrastructure."
```

After deploying: wait for `FINALIZED` with execution `SUCCESS`, check the deployed source hash and schema against the values above, record the address in `deployments/studionet.json`
(keep `canonicalDeployment` as `null`), then set `VITE_CHARTERGATE_ADDRESS=<new address>` in `frontend/.env.local` and rebuild the frontend (the address is baked in at build time).

## 2. Verified locally

| Check | Result |
| --- | --- |
| `genvm-lint check` | passes, 72 methods |
| Direct tests (all stages, mocked LLM) | see the final report for the exact count and result |
| Mutation testing of the Stage 7 to 9 rules | 87 mutants against this exact source hash, 87 killed |
| GLSim integration (fresh process per file) | Stages 2 to 6 and the new governance file pass; skipped cases need real LLM validators |
| Frontend (vitest, typecheck, lint, build) | 349 tests pass, 8 skipped, typecheck, lint and build clean |
| Frontend against the Stage 6 deployment (browser) | the charter version history reads live data and renders; the new pages show a clean read error because that deployment lacks the new methods |
| Mobile width (375 px) | no horizontal overflow on the accountability page |

## 3. Not verified (needs the new deployment)

* Every new method on StudioNet: proposing, the model evaluation, approval, applying, the governance switch, execution reports, and every new read.
* How a real model judges amendment compatibility, how often validators agree, and whether evaluations rotate leaders.
* The new frontend pages and forms with real data and a real wallet (amendments, accountability panel, precedent overview, governance panel).
* The transaction lifecycle of each new write in the browser.

## 4. Manual wallet smoke test (suggested order)

Use a fresh deployment. Step 7 is **irreversible** for that deployment.

1. Connect the wallet on StudioNet. Open `/constitution`, add two or three charter sections as the owner, and confirm the version history lists each version.
2. Open `/constitution/amend`. Propose an `ADD` amendment. Check it is `PROPOSED` and written against the current version.
3. Request the evaluation. It can take a minute or more and may rotate. Check `COMPATIBLE` or `CONFLICTING` and that nothing else changed.
4. As the owner, approve it (only possible if `COMPATIBLE`). Apply it. Check the charter version increased and the amendment shows the version it created.
5. Propose two amendments against the same version, approve and apply one, and confirm the other becomes stale and can be closed as superseded.
6. Submit a proposal, review it to `ELIGIBLE`, and record an `ATTEMPTED` then a closing execution report. Confirm every report is labelled unverified.
7. Turn amendment governance on (one-way). Confirm direct charter edits now fail and the amendment path still works.
8. Confirm the Stage 1 to 6 journeys (evidence, review, repair, precedent, appeal) still behave as before.

## 5. Known limitations and unresolved risks

* Ratification is the owner; there is no voting system or member registry.
* Anyone can propose and request evaluation of their own amendment; there is no rate limit or fee.
* The compatibility evaluation is a model's advice and can be wrong in either direction.
* Execution reports are self-reported and cannot be verified by the contract.
* The governance switch cannot be undone.
* Carried over from earlier stages: reviews and appeals can still end `MAJORITY_DISAGREE` on StudioNet; a stored reasoned dissent, `MODIFIED`/`REVERSED` appellate decisions and repair after a reversal were
  never observed live (`docs/STAGE_6_EQUIVALENCE.md`, section 10); the case page loads slowly because of StudioNet's read limit.
* No independent professional security audit has been performed. The review in this repository is an internal one.
