# Stage 6 equivalence principle: appeals and reasoned dissent

The Stage 3, 3.1, 4 and 5.1 rules in `docs/STAGE_3_EQUIVALENCE.md`, `docs/STAGE_4_EQUIVALENCE.md` and `docs/STAGE_5_EQUIVALENCE.md` still apply. The appellate adjudication is the
review adjudication run on a closed record. The model is in `docs/APPEAL_MODEL.md`. This document says only what is new.

## 1. What every node rebuilds from its own state

Each validator re-executes the transaction, so each rebuilds the closed record from immutable state: the original review, the exact proposal or revision it judged, the historical charter
(and the revision of every active section), the evidence snapshot, the frozen precedent snapshot and the appeal identity. The leader's result is the only thing received from the leader. Every node
also proves, before any model call, that its rebuilt record recomputes the original `review_context_hash`, `evidence_set_hash` and `precedent_set_hash`.

## 2. Exact agreement (protocol identity)

The leader's result must carry the identity this validator reconstructed: proposal id, charter version, evidence count, `evidence_set_hash`, `precedent_set_hash` and the
**appeal context hash** (not the original review's context hash). Any difference is rejected.

## 3. Material agreement

The validator runs the **precedent-free** appellate adjudication itself (no precedent in its prompt, no precedent pass of its own) and requires:

* the same appellate verdict;
* the same finding class for every section;
* the same repairability for every violation;
* the same derived `decision_kind` (a function of exactly those fields and the shared original, so it is implied; it is also compared);
* the Stage 3.1 evidence-reference check on every cited evidence id.

Not compared and not hashed: the rationale and `missing_fact` prose of any finding, the reason of any citation.

## 3a. What "material" means

A finding is materially the same if its class is the same and, for `VIOLATED`, its repairability is the same. Evidence ids and prose are not part of the disposition (evidence ids are still validated for
membership in the frozen snapshot and for support).

## 4. Precedent citations

Exactly as Stage 5.1: a strict leader (an invalid citation is an `LLM_ERROR` and stores nothing), deterministic structural rules against the **frozen** snapshot (a case created after the original review is not a
candidate), and a semantic per-citation check by each validator on the leader's chosen citations. A validator never chooses citations itself.

## 5. LLM call shape (worst case per appeal)

| Situation | Leader | Each validator |
| --- | --- | --- |
| original saw no precedent | 1 appellate adjudication + N reference checks | 1 appellate adjudication + N reference checks |
| original saw precedent, no citations | + 1 precedent pass | no extra |
| C citations (at most 2 per section) | + 1 precedent pass | + C citation checks |

N is the number of appellate findings that cite evidence.

## 6. Reasoned dissent

A dissent is a leader-chosen alternative, so a validator **checks** it instead of re-writing it:

* structure, deterministically: the keys, the identity (appeal id, appeal context hash, decision hash), the complete set of findings under the same rules as a review, a verdict that equals the
  deterministic derivation, and `disagreeing` equal to the sections whose material signature differs from the controlling decision (at least one);
* the Stage 3.1 evidence-reference check;
* one bounded semantic check: is the alternative a materially defensible reading of THIS frozen record (not a reworded majority, not based on facts outside the record)?

If the leader reports that no material dissent exists, the validator accepts only if its **own** pass also finds none. A validator that can write a materially different, structurally valid reading rejects the claim,
which rotates the leader. After consensus, no dissent rolls the transaction back with `EXPECTED:NO_MATERIAL_DISSENT` and stores nothing.

## 7. Failure paths and atomicity

A failure at any step (malformed output, an invalid evidence reference, an invalid or failing precedent pass, a failing citation check, validators disagreeing, a non-material dissent) writes nothing: no appeal
id, no decision, no finding, no citation, no dissent id, no status change, no repair-target change, no index change. All writes follow `run_nondet`.

## 8. Liveness

Stage 3 to 5 live testing showed `BAD_MISSING_FACT` and `MAJORITY_DISAGREE` rotations on reviews. An appeal runs the same kind of adjudication plus, sometimes, a precedent pass and citation checks,
so similar behavior is possible. This is an operational observation to measure on StudioNet, not a relaxation of any rule.

## 9. What is not proven locally

The direct tests mock the LLM. They prove the contract's own rules and the placement of text in each prompt. They do not prove that a real model reconstructs a judgment faithfully, how often it reverses, how
often validators agree, or whether a dissent is genuinely defensible. That needs StudioNet.

## 10. Frozen: live verification status, coverage gaps and backlog

**Stage 6 is CONDITIONALLY ACCEPTED: FROZEN WITH DOCUMENTED COVERAGE GAPS.** It is not an unconditional pass. The distinction between live evidence and direct-test coverage below is deliberate.

Verification contract: `0x050AFCd8B8a74Cbf8aaF682CA113bc510c6269e8` on StudioNet (chain 61999), deployed by `my-studionet-wallet` (`0xaffe15eec45b68835cc9e5b4ab85dd5deae8e70b`) from commit `a9eefbb`.
Deployment tx `0x36d42c2f4e7eb4c3d037e9b407b4cad654f17c1a637ecf25041274f4466b31b7`. Source hash (CRLF to LF, trimmed SHA-256)
`a0defd0d7c81a5cb697d69932e35bfb8e522dd90011771461810119a1187e8b8`. `canonicalDeployment` is `null`. The Stage 1 to 5 deployments are preserved unchanged. The approved
source, prompts, equivalence rules and validation rules are not modified by the freeze. All records are in `deployments/studionet.json`.

### 10.1 Verified live (StudioNet and the browser)

* **Deployment.** FINALIZED, execution SUCCESS, `MAJORITY_AGREE`. The deployed source hash equals the approved hash. The deployed schema (57 methods) is identical to `docs/charter_gate.schema.json`.
* **Four completed live appeals, all `AFFIRMED` / `REPAIRABLE`** (three through the CLI, one through the browser wallet):

  | Appeal | Review (proposal) | Tx | Rounds | What it demonstrated |
  | --- | --- | --- | --- | --- |
  | 1 | 1 (2) | `0xba3f76ec5e2e8e9c5bd400011ad1e6fd42bb52dbfe02b992f7403e8d7fbd9637` | 2 | Evidence #3 submitted AFTER review 1 never entered the appeal (evidence count 0, original evidence-set hash). Charter v4 was used although `s3` had been amended to v5. |
  | 2 | 2 (4) | `0xfe97edf5db24aa3c895961e1e98ab5f7f401f8072e0870f5a8dc36587b8e1e72` | 1 | The frozen precedent snapshot was review 1 only, although reviews 3 to 6 existed. |
  | 3 | 4 (6) | `0xff0f27d49f34d542854655c79929146b794702e53cebbf5c2f21f8a194c592d6` | 4 | Charter v5; the precedent pass cited the frozen candidates (reviews 3 and 2), FOLLOWED and DISTINGUISHED. |
  | 4 | 6 (8) | `0xdffb3fc98d84d9b9fb3a8912c48e12c202228c2a23aa33f72e1476ad9c27b30e` | 1 | Filed from the browser wallet; FOLLOWED on reviews 5, 4 and 3 from the frozen snapshot. |

* **Frozen record.** Evidence, charter version and precedent snapshot of every appeal equal the original review's. Each appeal's `evidence_set_hash`, `original_review_hash`, `charter_version` and
  `evidence_count` equal the review's, and its candidates equal the review's stored candidates.
* **Independent hash recomputation.** With a reference Keccak-256 from the documented formats, every value matched the chain: 6 reviews (set, precedent, context v1/v2/v3 and review v1/v2 hashes), 2 revisions, and appeals 1 to 4
  (`chartergate.appeal.v1`, `chartergate.appealcontext.v1`, `chartergate.appellate.v1`), with every disposition re-derived. Appeal 4: appeal `0x6128dbe8ec6f330894869c75caa2267edc987ff547fcde304b59a55756e723e4`,
  context `0x32b8bd484dea2d7bddc2fe72d5bbedf0d4118e576d5e788b64d73523d4ce8d7e`, decision `0x2280054d13e0003dbbc5cf2b215b97ecb11c7d6dcf94ecb9f33a5bc088ce547e`. The original reviews are unchanged by the appeals.
* **Effective verdict and repair.** `get_effective_ruling` reports the appellate decision and the original verdict side by side. Proposal 2 was repaired after its affirmed appeal (tx
  `0x88e84e3151de3ed79eaeec0a9c49a532e3bc253bb729777d904dc8defe760414`, targets from the appellate findings) and its revision was reviewed as review 5, `ELIGIBLE`
  (tx `0x4ed1c4cf03e139a3f74addd708193cb5c347aa4e8bddef4a2b3ea1020c95eede`).
* **Appeal rejected after repair started.** Proposal 5 was repaired, then an appeal of review 3 was refused with `EXPECTED:REPAIR_ALREADY_STARTED` (tx `0xc2ac70df9e93e8400f8037e9074d8c5a13f07460595f00e077c67a30e6529206`).
* **Other refusals observed live:** `APPEAL_GROUND_INVALID`, `GROUND_NOT_APPLICABLE`, `REVIEW_NOT_FOUND`, `APPEAL_ALREADY_EXISTS`, `APPEAL_NOT_FOUND`.
* **Five no-dissent attempts, four on the CLI and one through the browser, nothing stored** (appeals 1, 2, 1 again, 3 and 4; the browser one is tx
  `0xae196db603f8e1830a83508e4f30eaf1e39cb9103e864fd65f8ecd018d391a81`). Each rolled back with `EXPECTED:NO_MATERIAL_DISSENT`; the browser showed the plain-language message and the failure state.
* **Browser wallet-connected appeal flow: PASS WITH NOTES.** The workspace (frozen record, ground, statement), the appeal, the finalized appellate decision, the three-verdict history, the precedent treatment and the dissent panel were exercised and read.
  Notes: the individual transaction-lifecycle phases were not reported; the appeal was affirmed, so a reversal was not exercised in the browser; the browser dissent request produced the no-dissent rollback, not a stored dissent.

### 10.2 Accepted coverage gaps (limitations, not confirmed defects)

These are **not** live-verified. They are covered by direct tests only, with the live-verification requirement recorded in the backlog.

| Gap | Direct-test coverage |
| --- | --- |
| A stored reasoned dissent was not observed live | `tests/direct/test_dissent.py` (fixture G, material-disagreement derivation, non-controlling guarantee, atomic failure, validator accept and reject paths), `test_appeal_hash.py` (dissent hash) |
| `MODIFIED` and `REVERSED` appellate decisions were not observed live | `tests/direct/test_appeal_semantics.py` (fixtures B and C, the opposite direction, the deterministic disposition) |
| Repair after a reversal was not observed live | `test_appeal_semantics.py` (repair blocked after a reversal to `INELIGIBLE` or `ELIGIBLE`, permitted after `INELIGIBLE` to `REPAIRABLE`, targets from the appellate findings) |
| Stranger authorization and the `ELIGIBLE`-review refusal were not observed live | `tests/direct/test_appeal_authorization.py` (all refusals happen before any model call) |

The real model returned "no materially different reading" in every dissent attempt and "same material findings" in every appeal. No outcome was forced or manufactured, no prompt was changed and no check was weakened.

### 10.3 Backlog (non-blocking; no prompt, equivalence, validator or contract change is implied)

* **S6-G1 Stored dissent not observed live.** Reproduction: request a dissent on an appeal whose closed record admits a genuinely defensible alternative reading (a proposal that is truly borderline on a section). Coverage: direct tests above.
  Future verification: observe one stored dissent live, then check its findings, `disagreeing_section_ids`, and `dissent_hash` recomputed independently, and that the effective verdict, proposal status, repair targets, appellate decision and rule index are unchanged.
* **S6-G2 `MODIFIED` and `REVERSED` not observed live.** Reproduction: appeal a review whose original ruling is genuinely contestable, or one that the model rules differently on a second independent reading. Coverage: `test_appeal_semantics.py`.
  Future verification: observe at least one of each, check the three verdicts, the status, the repair targets and that a modified or reversed original review is excluded from a later review's candidates while still readable.
* **S6-G3 Repair after a reversal not observed live.** Reproduction: needs G2 first. Coverage: `test_appeal_semantics.py`. Future verification: after a reversal to `ELIGIBLE` or `INELIGIBLE` confirm `REPAIR_NOT_ALLOWED`; after `INELIGIBLE` to `REPAIRABLE` confirm repair opens with the appellate targets.
* **S6-G4 Stranger authorization and the `ELIGIBLE` refusal not observed live.** Reproduction: the CLI has one account, so a second funded account is needed for `NOT_PROPOSER`. For `REVIEW_NOT_ADVERSE`, an `ELIGIBLE` review already exists on the verification contract
  (review 5, the revision review of proposal 2), so that refusal can be checked live without any model call. Coverage: `test_appeal_authorization.py`. Future verification: send both refusals and check the expected codes and that nothing is stored.
* **S6-R1 Reliability.** Reviews and appeals can still end `MAJORITY_DISAGREE` with `BAD_EVIDENCE_REF` or `BAD_MISSING_FACT`, as in Stages 3 to 5. Observed in Stage 6: reviews of proposals 1 and 3 (cited evidence) failed twice each and were never reviewed; proposals 6 and 7 failed with
  `BAD_MISSING_FACT`, 6 succeeding on retry and 7 failing twice; appeal 3 and review 4 each needed 4 rounds. Every failure stored nothing and is recorded in `deployments/studionet.json`.
* **S6-L1 Appellate decision is not automatic precedent** (design limitation). A `MODIFIED` or `REVERSED` original is excluded from future candidates, but the controlling appellate decision is not a candidate, because Stage 5 candidates, citations and hashes are keyed by review id. A later stage can add a source-kinded index
  (`source kind`, `source id`, `source hash`, exact rule identity) additively. Not implemented and not to be faked as an ordinary review.
* **S6-L2 Dissent provenance.** GenVM v0.2.16 exposes no authenticated validator-minority opinion to contract code. A reasoned dissent is an AI-generated, non-controlling alternative, never a validator vote. This is a platform fact, not a defect.
* **S6-L3 The case page shows the appellate history of the controlling review only.** An earlier appealed review that was later repaired is on-chain and readable (`get_review_appeal_status`, `get_appeal_record`) but not listed on the page.
* **S6-L4 The `/precedent` route is still a placeholder page.**
* **S6-L5 StudioNet's RPC read limit** makes a case page take roughly 30 to 40 seconds to settle even with request sharing and read spacing (same as S5-R3).
* **S6-L6 CLI blank-statement argument.** The `genlayer` CLI turns a whitespace-only argument into a non-string, so the live attempt failed with `EXPECTED:INVALID_TYPE` instead of exercising `APPEAL_STATEMENT_EMPTY`. A tooling limitation; the empty-statement rule is covered by `test_appeal_authorization.py`.
* **S6-L7 Browser E2E notes.** The transaction-lifecycle phases were not individually reported, and a reversal and a stored dissent were not exercised in the browser.
