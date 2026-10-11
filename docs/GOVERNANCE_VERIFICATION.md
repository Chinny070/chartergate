# Governance switch: safety verification and demo guide

Date: 2026-10-11. The live release contract `0xC97b91Bd8ede96533B17EFf86D98cDff6c700736` was only **read** during this work; its governance switch is **OFF** (verified by `get_governance_status` after all tests: `governance_enabled: false`, charter v5, 4 amendments).

## 1. What activation does (from `contracts/charter_gate.py`)

* `enable_amendment_governance()` is owner-only (`_require_owner`), sets `governance_enabled = True` and records `governance_enabled_at`. A second call fails with `GOVERNANCE_ALREADY_ENABLED`.
* **Irreversible.** No method sets the flag back to false and no upgrade or ownership-transfer path exists. The owner is permanent.
* After activation `add_charter_section`, `update_charter_section` and `deactivate_charter_section` fail with `AMENDMENT_GOVERNANCE_REQUIRED` (after the owner check). Amendments reach the same internal `_charter_add/_update/_deactivate` code path.
* Unchanged by activation: proposing (anyone), evaluation (proposer or owner), approval (owner only, COMPATIBLE and not stale), apply (proposer or owner, approved and not stale), reject, close-stale, reviews, appeals, dissent, execution reports.

## 2. Lock-out analysis

The owner can always approve and apply, so authority itself cannot be lost. Remaining risks, none fixable without redeploying:

| Risk | Effect | Mitigation |
| --- | --- | --- |
| Every charter change now needs a model evaluation to finalize on StudioNet. `MAJORITY_DISAGREE` rotations have been seen on other LLM transactions (none occurred on any amendment evaluation in these tests). | A change could be delayed, not blocked; retry works. | Retry; keep the evaluation text short and concrete. |
| A CONFLICTING verdict blocks approval, and the owner cannot override it. | A wanted change that the model misjudges cannot be forced. | Rephrase and re-propose against the current version. |
| A competing apply makes other open amendments stale. | They must be re-proposed. | By design; `close_stale_amendment` records it. |
| Owner key loss. | Nobody can approve; the charter freezes. Not caused by the switch (it was already true for direct edits). | Protect the key. |
| Spam proposals (no fee or rate limit). | Noise only; cannot change the charter. | Documented limitation. |

Conclusion: activation cannot lock the owner out of governance, but it makes the model evaluation a mandatory step for every future charter change and cannot be undone.

## 3. Throwaway deployment tests (StudioNet)

Throwaway contract `0xF4A0c02ec41202FA5DFA984b464ECA5a9c3579f0` (deploy tx `0x46a04c02dae80833e563eaf1b14fe0620cd8c2bc82b5e4c58aa1d3937f95a5f8`, FINALIZED, MAJORITY_AGREE, same source hash and 72-method schema). Owner signer `my-studionet-wallet`; stranger signer `gltest-seller-a` (a local test account). Not a release deployment.

Verified live (all FINALIZED, MAJORITY_AGREE):

| Step | Result |
| --- | --- |
| Before activation: stranger `add_charter_section` | refused `NOT_OWNER` |
| Before activation: stranger proposes and evaluates its own amendment | allowed |
| Before activation: stranger `approve_amendment` | refused `NOT_OWNER` |
| Stranger `enable_amendment_governance` | refused `NOT_OWNER` |
| Owner `enable_amendment_governance` | success; `governance_enabled: true` |
| Owner enable again | refused `GOVERNANCE_ALREADY_ENABLED` |
| Owner direct add, update, deactivate | each refused `AMENDMENT_GOVERNANCE_REQUIRED` |
| Stranger direct add | refused `NOT_OWNER` |
| Approved amendment 1 applied after activation | success; charter v3 to v4 |
| Amendment 2 (written against v3) evaluated after v4 | refused `AMENDMENT_STALE`; closed as SUPERSEDED |
| Amendment 3 (UPDATE) proposed, evaluated, approved after activation | success |
| Non-proposer stranger applies amendment 3 | refused `NOT_AUTHORIZED` |
| Owner applies amendment 3 | success; charter v5 |
| State after all refusals | version and amendment count exactly as expected (v5, 3 amendments); no refusal changed state |

Transaction hashes: `deployments/studionet.json`, entry `throwaway_governance_test`.

Not verified live: a DEACTIVATE amendment. The `genlayer` CLI 0.39.1 turns an empty-string argument into a non-string (`INVALID_TYPE:title`), so a DEACTIVATE proposal cannot be sent from the CLI. The browser encoder (`genlayer-js`) sends `""` as a string (checked by encoding and decoding the calldata), and DEACTIVATE is covered by the direct tests. Verify it once in the browser if you want to demo it.

## 4. Local checks (this session)

* Direct tests (governance guardrails, amendment lifecycle and integrity, accountability): 144 passed. Full direct suite earlier today at the release candidate: 1546 passed.
* Frontend: typecheck clean, lint clean, vitest 349 passed and 8 skipped, production build succeeded.
* Live frontend (https://chartergate.vercel.app) read the live contract: constitution (v5, sections s1, s3, s4, history v1 to v5), amendments (4, with the right statuses), accountability (amendments plus case 1 ELIGIBLE), precedent (s1@2, s3@5, s4@4 with 2 reviews each).

## 5. Demo script (live contract; keep the switch OFF unless you decide otherwise)

1. https://chartergate.vercel.app, connect the owner wallet on StudioNet.
2. `/constitution`: charter v5, three sections, version history.
3. `/constitution/amend`: the four recorded amendments (applied, applied, superseded, rejected). Propose a new one, request evaluation (about a minute), approve, apply.
4. `/accountability`: amendments marked contract-verified; open case 1 to see its execution reports, all labelled unverified.
5. `/precedent`: rules and review counts.
6. To show the lock, use a fresh deployment, not the live contract.

## 6. Decision needed before activating on the live contract

Activation is irreversible and makes the model evaluation mandatory for every future charter change. The tests above show it behaves as designed. Say explicitly if and when to activate; it is not done.
