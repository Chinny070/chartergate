# Appeal model (Stage 6): constitutional appeals and non-controlling dissent

CharterGate now distinguishes three different things a proposer can want after an adverse ruling.

| | What it says | What it changes |
| --- | --- | --- |
| **Repair** (Stage 4) | "The proposal needs to change." | Creates a new immutable revision that is reviewed again. |
| **Appeal** (Stage 6) | "The record stays as it was, but the ruling itself may have been wrong." | Creates an immutable appeal and an immutable appellate decision **above** the original review. Nothing else changes. |
| **Reasoned dissent** (Stage 6) | "A materially defensible alternative reading exists, but it does not control." | Stores one immutable, non-controlling alternative. Nothing that controls changes. |

Every original review is preserved permanently. An appeal never modifies the proposal text, a revision, the charter version, any charter section
revision, the evidence snapshot, the precedent snapshot, the original review, its findings or its hashes. To change the proposal is a repair. New facts
are not an appeal of the old record.

## 1. The closed appellate record

An appeal judges exactly what the original review judged, rebuilt from immutable state by every node and **proven identical** to what the review committed to:

* the original review (id and `review_hash`);
* the exact proposal, or the exact revision, that review judged (`review_revision_ids`, never "whatever is current");
* the historical charter version and the exact revision of every active section that applied;
* the evidence snapshot: the first `evidence_count_at_review` records of the proposal, so `evidence_set_hash` must recompute to the stored value;
* the precedent snapshot the review stored (`review_precedent_refs`), never a fresh selection, so `precedent_set_hash` must recompute to the stored value.

Before any model is called the contract recomputes the original `review_context_hash` from the rebuilt record and requires equality
(`APPEAL_RECORD_MISMATCH` otherwise). Evidence submitted after the review, charter amendments made after the review and precedents created after the review
cannot enter the record. A zero-precedent original stays a zero-precedent appellate record.

## 2. Eligibility

`request_appeal(review_id, ground, statement)` is proposer-only and is checked **before** any nondeterministic work:

| Refusal | When |
| --- | --- |
| `REVIEW_NOT_FOUND`, `NOT_PROPOSER` | unknown review, or the sender is not the proposal's proposer |
| `APPEAL_ALREADY_EXISTS` | the review was already appealed (one appeal per review; there is no appeal of an appeal) |
| `REVIEW_NOT_ADVERSE` | the review is `ELIGIBLE` |
| `REVIEW_NOT_CONTROLLING` | the review is not the latest review of the proposal's current revision |
| `REPAIR_ALREADY_STARTED` | a repair child already exists from this review (repair and appeal are alternatives) |
| `APPEAL_GROUND_INVALID`, `APPEAL_STATEMENT_EMPTY`, `APPEAL_STATEMENT_TOO_LONG` | bad arguments |
| `GROUND_NOT_APPLICABLE` | `PRECEDENT_MISAPPLICATION` for a review that saw no precedent |

Appealable verdicts: `INELIGIBLE`, `REPAIRABLE`, `INSUFFICIENT_EVIDENCE`. Challenges to another proposer's `ELIGIBLE` ruling are outside Stage 6.

## 3. Grounds and the statement

Grounds: `CHARTER_MISINTERPRETATION`, `EVIDENCE_MISAPPLICATION`, `PRECEDENT_MISAPPLICATION`, `PROCEDURAL_ERROR`. The statement is 1 to 1000 characters.
The ground and the statement are **arguments, not evidence**: they are untrusted prompt data and a statement that says "the review was wrong" does not make it so.
Precedent is advisory (Stage 5.1), so a precedent ground cannot change a finding by itself: the appellate findings never depend on precedent.

## 4. The appellate adjudication

Two model steps, exactly the Stage 5.1 structure:

1. **Precedent-free appellate findings** (always). The prompt carries the frozen charter, the frozen proposal or revision, the frozen evidence snapshot, the
   original judgment as quoted untrusted data and the appeal as quoted untrusted data. It contains no precedent at all (not the snapshot, not the original review's
   citations). The model must **independently reconstruct** the judgment: the original rationale is not authority and the appeal statement is not evidence.
   Output uses the same four finding classes (`SATISFIED`, `VIOLATED`, `UNCLEAR`, `NOT_APPLICABLE`) and the same repairability semantics, validated by the same rules as a review.
2. **Precedent-consistency pass** (leader only, only when the frozen snapshot has candidates). Over the FIXED appellate findings, with the same bounds and
   the same deterministic and semantic citation rules as Stage 5.1. It can only add citation metadata.

### Deterministic verdict

The model never supplies the trusted verdict: any non-repairable `VIOLATED` is `INELIGIBLE`; otherwise any `VIOLATED` is `REPAIRABLE`; otherwise any `UNCLEAR` is
`INSUFFICIENT_EVIDENCE`; otherwise `ELIGIBLE` (the Stage 3 derivation).

### Deterministic disposition (`decision_kind`)

A finding's **material signature** is its class and, for `VIOLATED`, whether it is repairable. Evidence ids and prose are not material.

* `REVERSED`: the appellate verdict differs from the original verdict;
* else `MODIFIED`: the verdict is the same but at least one section's material signature differs;
* else `AFFIRMED`.

The model never supplies this field.

## 5. Storage

* `Appeal`: `appeal_id`, `review_id`, `proposal_id`, `revision_id` (0 = original), `appellant`, `ground`, `statement`, `original_verdict`, `original_review_hash`,
  `charter_version`, `evidence_count`, `evidence_set_hash`, `precedent_set_hash`, `created_at`, `appeal_hash`.
* `AppellateDecision`: `appeal_id`, `review_id`, `verdict`, `decision_kind`, `finding_count`, `appeal_context_hash`, `decision_hash`, `created_at`
  (findings in `appeal_findings`, precedent treatment in `appeal_precedent_citations`).
* `ReasonedDissent`: `dissent_id`, `appeal_id`, `decision_hash`, `verdict`, `disagreeing_section_ids`, `finding_count`, `created_at`, `dissent_hash`
  (findings in `dissent_findings`).

An appeal and its decision are written in one transaction, atomically: if consensus, the model output or a citation fails, **nothing** is stored and no id is consumed.

## 6. Effective verdict, status, repair

`get_effective_ruling(proposal_id)` answers "what currently controls this proposal": the latest review, or its appellate decision if it was appealed. The original review's
`verdict` field is never mutated; both are reported. The proposal's `status` reflects the controlling verdict.

| Original | Appeal | Effective | Repair |
| --- | --- | --- | --- |
| `REPAIRABLE` | `AFFIRMED` | `REPAIRABLE` | still possible, from the appellate findings |
| `REPAIRABLE` | `MODIFIED` (still `REPAIRABLE`) | `REPAIRABLE` | possible; the targets are the **appellate** violations, not the overturned ones |
| `REPAIRABLE` | `REVERSED` to `ELIGIBLE` | `ELIGIBLE` | not possible; the original still reads `REPAIRABLE` |
| `REPAIRABLE` | `REVERSED` to `INELIGIBLE` | `INELIGIBLE` | not possible (an appeal is adjudication, not a guaranteed benefit) |
| `INELIGIBLE` | `REVERSED` to `REPAIRABLE` | `REPAIRABLE` | possible |

`get_repair_targets` and repair admission (`submit_repair_revision`) use the controlling ruling: the appellate findings when the review was appealed. A repair child still records the original
`source_review_id`.

## 7. Precedent after an appeal

* `AFFIRMED`: the original review stays eligible for Stage 5 automatic precedent.
* `MODIFIED` or `REVERSED`: the original review is **excluded from future automatic candidate selection** (it no longer states the controlling reading). It stays in the audit history, in the
  rule index, and inspectable through `get_precedent_case`. Exclusion consumes one scan slot like any other skipped review. Frozen snapshots of earlier reviews are never altered.

**Limitation (design issue, not implemented):** the controlling appellate decision does not become automatic precedent. Stage 5 candidates, citations, the `precedent.v1`, `reviewcontext.v3` and
`review.v2` hashes and `get_precedent_case` are keyed by review id. Presenting an appellate decision as a candidate would need a new source kind in each of them, or would fake an appellate decision as an
ordinary review, which would break frozen Stage 5 semantics. A later stage can add a source-kinded index (`source kind`, `source id`, `source hash`, exact rule identity) additively.

## 8. Reasoned dissent

### Runtime capability finding

GenVM (runner `py-genlayer` v0.2.16) gives contract code `gl.vm.run_nondet(leader_fn, validator_fn)`. The leader's value is returned only if validation passes; a validator that disagrees ends the
execution with a disagreement. There is **no API** that exposes a validator's opinion, a minority vote or any authenticated per-validator output to contract code. Therefore an
authenticated validator-minority dissent is **not available**, and nothing in Stage 6 claims to be one.

### What is stored

A **reasoned dissent**: an AI-generated, immutable, inspectable, non-controlling alternative reading of the **same closed record**. It is not another appeal, not a vote, not an authenticated validator
minority, not evidence, not precedent and not controlling law. The user interface says so.

* Separate write path: `request_reasoned_dissent(appeal_id)`, proposer-only, after an appellate decision exists, **one per appeal**. An optional dissent can never block an appeal from finalizing.
* The dissent prompt carries the frozen charter, the frozen proposal or revision, the frozen evidence snapshot and the controlling appellate decision. Not the appeal statement, not later evidence, not a later charter.
  The precedent snapshot is bound by the context hash but, per the Stage 5.1 authority boundary, precedent text is not shown to the model that decides findings.
* It must disagree **materially** with the controlling decision: at least one section whose class or repairability differs (a different final verdict implies this). The disagreeing sections are
  **derived**, not declared. If none, the transaction rolls back with `EXPECTED:NO_MATERIAL_DISSENT` and nothing is stored.
* It never changes the effective verdict, the proposal status, the repair targets, the precedent index, the appeal disposition or the evidence state, and it is never selected as automatic precedent.

## 9. Hashes (Keccak-256, lines joined by `\n`)

`chartergate.appeal.v1`:

```
chartergate.appeal.v1
review_id=<id>
review_hash=<original review hash>
proposal_id=<id>
revision_id=<0 for the original proposal>
appellant=<address>
ground=<GROUND>
statement=<statement with whitespace collapsed>
charter_version=<n>
evidence_set_hash=<hash>
precedent_set_hash=<hash, empty when the review saw no precedent>
```

The timestamp and the appeal id are deliberately **not** hashed: the id is derivable (one appeal per review) and the timestamp is metadata, so the hash is reproducible from the record alone.

`chartergate.appealcontext.v1` commits to the closed record being reconsidered:

```
chartergate.appealcontext.v1
appeal_hash=<h>
review_id=<id>
review_hash=<h>
review_context_hash=<h>
proposal_id=<id>
revision_id=<id>
charter_version=<n>
section=<id>@<revision>      (one line per active section)
evidence_count=<n>
evidence_set_hash=<h>
precedent_set_hash=<h or empty>
```

`chartergate.appellate.v1` (the decision):

```
chartergate.appellate.v1
appeal_context_hash=<h>
verdict=<appellate verdict>
decision_kind=<AFFIRMED|MODIFIED|REVERSED>
section=<id>|finding=<class>|repairable=<bool>|evidence=<ids>       (one line per section)
precedent=section=<id>|review=<id>|treatment=<FOLLOWED|DISTINGUISHED>   (one line per citation)
```

`chartergate.dissent.v1`:

```
chartergate.dissent.v1
appeal_id=<id>
decision_hash=<controlling decision hash>
verdict=<alternative verdict>
section=<id>|finding=<class>|repairable=<bool>|evidence=<ids>       (one line per section)
disagrees=<comma-separated section ids>
```

Free-form prose (rationales, missing-fact wording, citation reasons) is excluded from every hash, so equivalent judgments with different wording hash identically. The existing Stage 3 to 5 formats are unchanged.

## 10. Contract methods added (all additive; Stage 1 to 5 methods unchanged)

Writes: `request_appeal(review_id, ground, statement)`, `request_reasoned_dissent(appeal_id)`.
Reads: `get_appeal`, `get_appeal_count`, `get_appeal_id_for_review`, `get_appellate_decision`, `get_appeal_findings_page`, `get_review_appeal_status`, `get_appeal_record` (the whole record in one read),
`get_reasoned_dissent`, `get_effective_ruling` (what controls a proposal, with its findings, in one read).

## 11. Prompt boundary

Untrusted data, defanged and fenced in `<<<DATA ... DATA>>>` blocks under a GOVERNANCE RULES section that is the only instruction zone: the appeal statement, the proposal and revision text, the original rationale and
`missing_fact`, evidence claims, quotes, values and facts, historical precedent text and the appellate rationale shown to a dissent. The charter is quoted constitutional content, not prompt authority.
Historical precedent is **absent** from the base appellate prompt (proven by test) and defanged where it appears (the consistency pass).

## 12. Limits and known issues

The frozen live-verification status, the accepted coverage gaps and the backlog (S6-G1 to S6-L7) are in `docs/STAGE_6_EQUIVALENCE.md`, section 10.

* Real model behavior is not proven locally: the direct tests mock the LLM and prove the contract's own rules.
* The appellate decision is not yet automatic precedent (section 7).
* The case page shows the appellate history of the **controlling** review; an earlier appealed review that was later repaired is still on-chain and readable (`get_review_appeal_status`, `get_appeal_record`) but is not listed in the case page.
* A dissent is as strong as the model that wrote it. It exists to make a defensible alternative inspectable, not to settle anything.

Not in Stage 6: charter amendment governance, voting, ratification, treasury execution, accountability.
