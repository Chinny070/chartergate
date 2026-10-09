# Proposal revision model (Stage 4)

Stage 3 can conclude `REPAIRABLE`. Stage 4 makes that actionable without ever editing history.

```
revision 1 (the original Stage 1 proposal)
   -> review: REPAIRABLE (violated, repairable findings = the repair targets)
   -> revision 2 (repair, admitted by GenLayer consensus)         status REVISED
   -> review of revision 2: ELIGIBLE / INELIGIBLE / REPAIRABLE / INSUFFICIENT_EVIDENCE
        REPAIRABLE -> revision 3 -> ... up to 5 repairs
```

## 1. Repair is versioning, never editing

Never mutated: the original title, description, requested action, `charter_version_at_submission`, the original review, its
findings, its evidence snapshot and every hash. A repair creates a new immutable `ProposalRevision`. The only field of the original
`Proposal` that ever changes is its `status`, as in Stage 3.

The original Stage 1 proposal behaves as **revision 1** without any migration: it is not duplicated into the revision table. A
`ProposalRevision` exists only for revision 2 and later.

## 2. One lineage, one proposal id

Revisions keep the root `proposal_id`. Evidence therefore stays associated with the same lineage and is **not copied**: new evidence
is added with the existing Stage 2 flow and receives new immutable records.

## 3. Storage

`ProposalRevision`: `revision_id` (global counter), `proposal_id`, `revision_number` (2..6), `parent_revision_id` (0 = the original),
`source_review_id`, `proposer`, `title`, `description`, `requested_action`, `charter_version`, `addressed_section_ids`, `created_at`,
`revision_hash`.

Added fields: `proposal_revisions`, `revision_count`, `proposal_revision_ids` (a `DynArray` per proposal), `review_child_revision`
(source review to its one child), `revision_review_ids`, `review_revision_ids` (review to the exact revision it judged, absent for
reviews of the original), `proposal_review_history` (every review of a lineage, oldest first).

## 4. Charter version never moves

A revision inherits `proposal.charter_version_at_submission`. Revisions 2..6 are assessed and reviewed under that charter even if the
current charter is far newer: a repair is not a loophole into an easier constitution. The repair assessment shows the model the
section text as it read at that version, and the revision review rebuilds the historical charter exactly as in Stage 3.

## 5. Who may repair, and when

* only the proposer (checked before any nondeterministic work);
* only when the proposal's **latest** review is `REPAIRABLE` and no repair has been accepted since (status `REPAIRABLE`);
  `ELIGIBLE`, `INELIGIBLE`, `INSUFFICIENT_EVIDENCE` and an unreviewed proposal are refused (`REPAIR_NOT_ALLOWED`). Evidence remediation
  for `INSUFFICIENT_EVIDENCE` is deliberately not in Stage 4;
* **no branching**: an accepted repair sets the status `REVISED`, so a second child of the same parent is impossible, and a
  source-review-to-child map backs it up (`REVISION_ALREADY_EXISTS`);
* **at most 5 repair revisions** after the original (so revision numbers 1 to 6): the bound is conservative storage and review-cost
  control (`REVISION_LIMIT_REACHED`);
* the new text must differ from the current effective text after whitespace normalisation (`REVISION_UNCHANGED`) and obeys the Stage 1
  title, description and action limits.

## 6. Repair targets and admissibility

The targets are the latest review's `VIOLATED` findings with `repairable = true`, with the section text at the historical charter
version and the stored rationale (`get_repair_targets`). Admissibility is a GenLayer judgment derived deterministically from
`same_fundamental_purpose`, `material_scope_change` and `addressed_section_ids`; see `docs/STAGE_4_EQUIVALENCE.md`. A rejected repair
returns `EXPECTED:REPAIR_REJECTED:{PURPOSE_CHANGED|SCOPE_CHANGED|NO_TARGET_ADDRESSED}` and leaves no history.

## 7. Revision hash (`chartergate.revision.v1`, Keccak-256, lines joined by `\n`)

```
chartergate.revision.v1
proposal_id=<id>
revision_number=<n>
parent_revision_id=<id, 0 for the original>
source_review_id=<id>
charter_version=<v>
title=<whitespace-collapsed>
description=<whitespace-collapsed>
requested_action=<whitespace-collapsed>
addressed_sections=<sorted ids joined by ,>
```

It binds a revision to its lineage and text. Excluded on purpose: the model's explanation, the proposer, timestamps and the revision id,
so equivalent assessments with different prose hash the same. Whitespace is collapsed; case is not normalised.

## 8. Re-review

`request_revision_review(revision_id)` runs the **same Stage 3 adjudication** (historical charter, evidence snapshot, structured findings,
deterministic verdict, validator equivalence, prompt boundary, evidence-reference checks), not a weaker "repair review". Proposer only;
once per revision; only the latest revision (`status = REVISED`). The review records which revision it judged (`get_review_revision_id`;
0 means the original) and the proposal's status becomes its verdict.

**Review context hash for a revision** uses a versioned format so it commits to the revision's actual text and identity:

```
chartergate.reviewcontext.v2
proposal_id=<id>
revision_id=<id>
revision_number=<n>
revision_hash=<hash>
title= / description= / requested_action=   (the REVISION's text, whitespace-collapsed)
charter_version=<v>
section=<id>@<revision version>             (one per active section at that version)
evidence_count=<n>
evidence_set_hash=<hash>
```

The review result hash keeps the Stage 3 format (`chartergate.review.v1`) over this context hash, the verdict and the findings. Reviews of
the original proposal keep `chartergate.reviewcontext.v1` exactly as before.

## 9. Evidence across revisions

Each review has its own snapshot of the proposal's evidence at that moment (the first N ids of the append-only list). Review 1's
snapshot never changes; review 2's snapshot is review 1's plus whatever was added since.

## 10. Status transitions

`SUBMITTED` -> (review) a verdict. From `REPAIRABLE`: -> `REVISED` (repair accepted) -> (revision review) a verdict. Every earlier review
stays in the lineage history; the UI never calls an old review "replaced": revision 1 was `REPAIRABLE` and a later revision may be
`ELIGIBLE`, and both facts stand.

## 11. Reads

`get_proposal_revision`, `get_proposal_revision_count`, `get_proposal_revisions_page`, `get_effective_proposal` (the original or the latest
revision's text), `get_review_for_revision`, `get_review_revision_id`, `get_proposal_review_count`, `get_proposal_reviews_page`,
`get_repair_targets`. The Stage 3 reads keep their meaning for the original proposal: `get_review_for_proposal` still returns the review
of the original.

## 12. Not in Stage 4

Precedent retrieval, similar-case search, dissent, appeals, charter-amendment governance, voting, execution guardrails, accountability,
and evidence remediation for `INSUFFICIENT_EVIDENCE`.
