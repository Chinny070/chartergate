# Governance switch: safety verification and demo guide

Updated 2026-10-12. The submission release is `0xc942901dbB024CDb922f9D71B91024ea919a9F94`. Its governance switch is **ON**. The owner-signed GenLayerJS 1.1.8 transaction `0xa20696724c4b39bf04e5162a840766a5274970e2135ec56a0a298c3f384c9272` finalized `MAJORITY_AGREE` with five validator agrees; its activation-time read returned `governance_enabled: true`, activation timestamp `2026-10-12T02:41:08.461235Z`, charter v4, and 3 amendments. The subsequent steward smoke test applied amendment #4, so the current readback is charter v5 with 4 amendments and active section s7 (details below). Five earlier CLI activation submissions finalized `NO_MAJORITY` with no validator rounds or votes. The earlier contract `0xC97b91Bd8ede96533B17EFf86D98cDff6c700736` was only **read** and remains OFF there. The signed same-text `update_charter_section` check finalized `MAJORITY_AGREE` at the consensus layer but the contract execution rolled back with `EXPECTED:AMENDMENT_GOVERNANCE_REQUIRED`. Post-transaction reads confirmed charter version 4 and §1 title/body/active state/timestamps unchanged at that time.

## 1. What activation does (from `contracts/charter_gate.py`)

Owner-controlled charter mutation is a bootstrap mechanism only. The intended normal policy path is amendment governance; after activation, direct owner edits are disabled permanently.

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

## 4. Current submission-release verification

The intended submission release is the verification deployment at `0xc942901dbB024CDb922f9D71B91024ea919a9F94` (StudioNet 61999), source commit `a486010`. It is not a canonical/production contract deployment. Its governance state and direct-edit restriction are verified in the opening record above and in `deployments/studionet.json` (`submission_release_a486010`).

The owner activation transaction `0xa20696724c4b39bf04e5162a840766a5274970e2135ec56a0a298c3f384c9272` finalized `MAJORITY_AGREE`; the subsequent direct `update_charter_section` call `0xf50cc5a16cf2d22c0404fa288dcff5d3ea0f10334181bd43d7734fd693f4a83f` finalized at consensus but reverted in contract execution with `EXPECTED:AMENDMENT_GOVERNANCE_REQUIRED`. Direct reads confirmed charter version 4 and the section unchanged. Five earlier CLI submissions finalized `NO_MAJORITY` with no rounds or votes; those are historical failed attempts, not the final state.

The deployment was later tested through the production frontend with the owner wallet on StudioNet:

| Frontend operation | Result |
| --- | --- |
| Connect wallet and read live state | Owner `0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b`; StudioNet 61999; metadata, charter history, proposals and amendments decoded from the deployed contract. |
| Submit proposal #3 | `0x9ff9db956ea754195476c23a6237186bedbfc595d14590d4f6c37088151ef257`, `FINALIZED`, `MAJORITY_AGREE`, execution `SUCCESS`; readback shows `SUBMITTED`, charter version 4. |
| Verify evidence #1 for proposal #3 | `0xc8235405191a4955514b31296491b26b28ac87a648927bb93f490cd1fad58f6c`, `FINALIZED`, `MAJORITY_AGREE`, execution `SUCCESS`; readback shows `VERIFIED`. |
| Request constitutional review for proposal #3 | `0x8d4e6af40a4f0991ba4f6668a626cf022f7ede7e183c9b878d9f7a3260e1fb7e`, `FINALIZED`, `MAJORITY_DISAGREE`; leader returned `LLM_ERROR:BAD_MISSING_FACT`; no review was stored and proposal remained `SUBMITTED`. This was a no-funding test proposal, which did not fit the active funding rules. |
| Read existing review, appeal and amendment records | Production UI rendered review #001 (`ELIGIBLE`), review #002 (`REPAIRABLE`), appeal #001 (`AFFIRMED`), and amendment #001's `COMPATIBLE` evaluation and applied state. These records were read back; this is not evidence that those writes were initiated by the frontend. |

The frontend refuses to show transaction success from consensus finality alone. It requires `FINALIZED` plus a successful contract execution; rollbacks and contract errors are presented as failures. The focused frontend tests are in `frontend/src/lib/genlayer/txOutcome.test.ts` and `frontend/src/lib/genlayer/live.test.ts`.

The later owner-wallet session also demonstrated these frontend writes on StudioNet:

| Frontend operation | Result |
| --- | --- |
| Submit proposal #5 for steward appeal-flow verification | `0x9bf7938f2e7635fecb4346cf307f5048e8e3c38a52be39b052dfd0d0d42765d2`, `FINALIZED`, `MAJORITY_AGREE`, execution `SUCCESS`; readback `SUBMITTED` at charter v4. Explicitly non-binding, with no payment or execution request. |
| Verify Salesforce evidence #2 for proposal #5 | `0x9dd8471d8d62a8b38a318c894aff27039a130aa9518cca76b91ebda4355c9f4a`, `FINALIZED`, `MAJORITY_AGREE`, execution `SUCCESS`; readback `VERIFIED`, retrieval time `2026-10-12T05:45:30.169307Z`, content hash `0x12c7b2ab…f01833`. |
| Request review #3 for proposal #5 | `0x0e087673d61b0852789f9f56edd9ed7cf360e558136041c291778d7a7eb248f3`, `FINALIZED`, `MAJORITY_AGREE`, execution `SUCCESS`; readback `INELIGIBLE` at charter v4. §s1 was nonrepairable; §s3 and §s4 were repairable. |
| File appeal #1 against review #3 | `0x79e3301584b5a68a70fb27d677db6d0a261c56f7ceb407ea9ae82f7d91c4ced5`, `FINALIZED`, `MAJORITY_AGREE`, execution `SUCCESS`; readback `AFFIRMED`, so the effective verdict remains `INELIGIBLE`. |
| Submit test amendment `s7` from the frontend | `0xac32e2a29e7df4f01123de044c95218ec405d6d9c5efa9d32d630781862fc24d`, `FINALIZED`, `MAJORITY_AGREE`, execution `SUCCESS`; receipt calldata identifies `propose_amendment` to the CharterGate contract at v4. Rabby's preview showed misleading `Send Token` wording, but the finalized receipt confirms the actual contract target and method. |
| Request evaluation for amendment #4, first CLI attempt | `0xf5fe2e8d8fec79cc282334d935bbe75fc6cbd881a90be725b497734883788ce8`, `FINALIZED`, `NO_MAJORITY`, **zero rounds and zero validator votes**. Receipt showed leader execution `UNKNOWN`; stdout/stderr were empty. This is not an evaluation verdict. The CLI trace API returned `Method not found: gen_dbg_traceTransaction`; fee estimation returned `Method not found: sim_getFeeConfig`. |
| Request evaluation for amendment #4 through the production frontend | `0x6ed388b8170346d115ea1cccc791d54c19f7f45b7442e791465f0fa5c9b099d4`, `FINALIZED`, `MAJORITY_AGREE`, GenVM execution `SUCCESS`; returned `compatible: true`, no conflicting sections, context hash `0x0346a78cdec754a2821752ae110ae4285abd8d9415ef5e6821a9d036050a724c`. |
| Owner approved amendment #4 | `0x19f28164ba7443148051b2186eaa8639202c88b42724cd7622f5aa5cf038310a`, `FINALIZED`, consensus `ACCEPTED`, GenVM execution `SUCCESS`; readback records the owner decision at `2026-10-12T08:58:09.698792Z`. |
| Owner applied amendment #4 | `0x615a75a621df5939b466829ab95bcc316121db2240ab960d7fb603d989c5c951`, `FINALIZED`, consensus `ACCEPTED`, GenVM execution `SUCCESS`; readback records application at `2026-10-12T09:10:25.480529Z`, applied version 5. |
| Read back amendment #4 and current charter | GenLayerJS 1.1.8 `LATEST_FINAL` reads returned amendment status `APPLIED`, verdict `COMPATIBLE`, owner approval and application metadata; governance remains ON, amendment count 4, charter version 5, active sections s1/s3/s4/s7. `get_charter_section("s7")` and the paginated section list returned the active “Steward verification” section with the exact non-binding test text and protocol timestamps. |

**Steward-requested frontend write-through is complete for the verified test lifecycle:** wallet connection, proposal, evidence, review, appeal, amendment proposal, amendment evaluation, owner approval, amendment application, and authoritative state readback all have finalized receipts or read results recorded above and in `deployments/studionet.json`. The failed CLI evaluation attempt is documented separately from the successful frontend transaction. Amendment #4 changed the verification deployment's charter from v4 to v5 by adding the explicitly non-binding test section s7; this remains a verification deployment, not a canonical production contract.

## 5. Historical activation attempts and wallet connection

On 2026-10-12, five CLI attempts to call `enable_amendment_governance` finalized `NO_MAJORITY` with zero validator rounds and votes. The final successful activation was a separate injected-wallet GenLayerJS 1.1.8 transaction, hash `0xa20696724c4b39bf04e5162a840766a5274970e2135ec56a0a298c3f384c9272`, signed by `my-studionet-wallet`. The live `get_governance_status` read returned `governance_enabled: true` and activation timestamp `2026-10-12T02:41:08.461235Z`.

An earlier attempt to connect through the CLI browser-wallet bridge stopped at MetaMask's unsafe-site warning. That was not the final browser test: the production frontend was subsequently connected to the owner wallet, and the proposal/evidence transactions above were signed and finalized. The Codex in-app browser used for the current review is a separate walletless browser and cannot sign those writes.
