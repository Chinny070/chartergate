# Stage 3 equivalence principle: constitutional review

`request_constitutional_review(proposal_id)` runs one non-deterministic block (`gl.vm.run_nondet(leader_fn, validator_fn)`).
This document says exactly what validators must agree on, what they may differ on, and why. It does not use `strict_eq` on
LLM output, and it never compares prose.

## 1. How validators get their own context

GenVM validators re-execute the whole transaction. The deterministic part of `request_constitutional_review` therefore runs on
every node against that node's own copy of contract state, and each node builds its own `ctx` (proposal, historical charter,
evidence snapshot, hashes) **from state, never from the leader**. The closures passed to `run_nondet` capture only that plain
`ctx` (they are pickled; they never capture storage). The leader's returned result is the only thing a validator receives from
the leader, and it is checked against the validator's own `ctx`.

Verified: the pinned runner (`py-genlayer:1jb45aa8…`, header `# v0.2.16`) and the existing Stage 2 contract use this pattern;
Stage 3 reuses it unchanged. The direct harness replays the validator closure captured from the leader run, so its
tests tamper with the leader's *result* to prove identity checks, rather than with the validator's state.

## 2. Exact agreement (protocol-critical identity)

A validator rejects unless the leader's result equals what the validator reconstructed:

| Field | Must equal |
| --- | --- |
| `proposal_id` | the proposal being reviewed |
| `charter_version` | `proposal.charter_version_at_submission` (never the current charter) |
| `evidence_count` | number of evidence records the proposal had at review time |
| `evidence_set_hash` | the validator's own hash of that snapshot |
| `context_hash` | the validator's own context hash (proposal text + historical charter revisions + snapshot) |

## 3. Structural validity (checked on the leader's result, by the validator, against its own state)

* exactly the keys `proposal_id, charter_version, evidence_count, evidence_set_hash, context_hash, verdict, findings`
* `findings` has **one finding per active section of the historical charter, in charter order**; none omitted, none repeated,
  none for a section that did not exist or was inactive at that version
* `finding` is one of `SATISFIED, VIOLATED, UNCLEAR, NOT_APPLICABLE`
* `repairable` is a boolean and `true` only on `VIOLATED`
* `evidence_ids`: at most 5, strictly increasing integers, each in the proposal's evidence snapshot (so never another
  proposal's, never future, never nonexistent); a `SATISFIED` or `VIOLATED` finding may cite only `VERIFIED` evidence;
  `NOT_APPLICABLE` cites nothing; `UNCLEAR` may cite a non-verified record as a failed attempt
* `rationale` at most 300 characters; `missing_fact` non-empty (at most 100) exactly when the finding is `UNCLEAR`
* at least one finding is `SATISFIED`, `VIOLATED` or `UNCLEAR` (an all-`NOT_APPLICABLE` review is refused)
* `verdict` equals the verdict **derived** from the findings (section 5 of `docs/CONSTITUTIONAL_REVIEW_MODEL.md`)

## 4. Material semantic agreement

After the checks above, the validator runs its own LLM analysis (the same prompt, built from its own `ctx`), validates it
the same way, and requires:

1. the same overall verdict
2. for every section, the same **adverse class**: `VIOLATED`, `UNCLEAR`, or non-adverse (`SATISFIED` and `NOT_APPLICABLE` are
   interchangeable)
3. for every `VIOLATED` section, the same `repairable` value
4. for every `VIOLATED` section where the leader cited evidence, the validator's finding for that section must cite at least
   one of the same evidence ids (a violation the leader grounds in evidence #4 is not accepted by a validator that does not rely
   on #4)

If the validator's own analysis fails for any reason (`LLM_ERROR`, unusable JSON, unusable references), it **rejects**. A failed
leader is always rejected, which forces rotation.

## 5. What is deliberately not compared

`rationale` wording, `missing_fact` wording, punctuation, the order the LLM listed findings (findings are normalised to charter
order and evidence ids to ascending order), whether a benign section is `SATISFIED` or `NOT_APPLICABLE`, extra evidence a
validator cites beyond the leader's, and any "verdict" the LLM volunteers (it is ignored; the verdict is derived).

## 6. The two cases from the brief

* leader `ELIGIBLE`, validator finds section 2 violated: **rejected** (adverse class differs).
* leader "The disclosure requirement is satisfied.", validator "Verified evidence demonstrates the required disclosure.",
  same section judgments, same evidence, same verdict: **accepted**.

## 7. Why the verdict is derived and the INSUFFICIENT_EVIDENCE rule

Validators agree on structured findings, not on a free-form verdict. `INSUFFICIENT_EVIDENCE` therefore always has at least one
`UNCLEAR` finding that names a missing fact. A leader that says `UNCLEAR` when VERIFIED evidence resolves the question is
rejected by a validator whose own analysis says `SATISFIED` for that section (adverse class differs).

## 8. Failure paths and liveness

A review that fails (malformed output, validators disagree until the transaction fails) writes nothing: no review id is consumed,
the proposal status is unchanged, and the charter and evidence are untouched. Real StudioNet already needed leader rotation on
2 of 8 Stage 2 LLM submissions (operational observation, cause unconfirmed); a longer, multi-section Stage 3 prompt may rotate
more. That is a liveness cost, not a safety weakening, and the rules above were not relaxed for it.

## 9. What is NOT proven locally

The direct tests mock the LLM. They prove these rules and the contract's handling of any structured answer. They do not prove a
real model reaches sensible findings, nor how often real validators agree. That requires the StudioNet adjudication run.
