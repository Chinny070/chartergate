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
2. for every section, **exactly the same finding class**: `SATISFIED`, `VIOLATED`, `UNCLEAR` or `NOT_APPLICABLE`. The four classes
   have distinct constitutional meanings and are never treated as equivalent (Stage 3.1 removed the earlier rule that let
   `SATISFIED` and `NOT_APPLICABLE` stand in for each other):
   * `SATISFIED`: this section applies and its requirement is met
   * `NOT_APPLICABLE`: this section does not govern this proposal
   * `VIOLATED`: this section applies and the proposal materially conflicts with it
   * `UNCLEAR`: this section applies but a fact needed to decide is not verified
3. for every `VIOLATED` section, the same `repairable` value
4. every evidence id the leader stored in a finding must **materially support that finding**, by this validator's own reading
   of the immutable evidence records (section 4a). Findings that cite no evidence need no such check.

If the validator's own analysis fails for any reason (`LLM_ERROR`, unusable JSON, unusable references), it **rejects**. A failed
leader is always rejected, which forces rotation.

### 4a. Evidence-reference check (Stage 3.1)

A stored reference must be defensible for *that finding*, not merely exist, be `VERIFIED`, and sit in the snapshot. For each leader
finding that cites evidence, the validator makes one extra LLM call, "EVIDENCE REFERENCE CHECK", built only from the immutable
`EvidenceRecord`s, the one charter section, the proposal text and the finding. It returns `{"supporting_ids": [...]}` and the
validator requires **every** cited id to be in that list:

* `SATISFIED` / `VIOLATED`: a record supports the finding only if it is `VERIFIED` and its fact and value materially bear on whether
  that section is satisfied or violated by this proposal. A `VERIFIED` record about an unrelated fact does not.
* `UNCLEAR`: a record qualifies only if it is an attempt to establish the missing fact the finding names.
* An unusable answer rejects.

This is not a second Stage 2: nothing is fetched and no record is re-verified. The check reasons over what the vault already holds.
Findings grounded in the proposal text alone, and `NOT_APPLICABLE`, cite nothing and trigger no check. The structural rule in
section 3 still refuses non-`VERIFIED` evidence as support for `SATISFIED` / `VIOLATED` regardless of what the check says.

## 5. What is deliberately not compared

`rationale` wording, `missing_fact` wording, punctuation, the order the LLM listed findings (findings are normalised to charter
order and evidence ids to ascending order), extra evidence a validator cites in its own analysis beyond the leader's (only the
leader's stored references are checked), and any "verdict" the LLM volunteers (it is ignored; the verdict is derived).

## 6. The two cases from the brief

* leader `ELIGIBLE`, validator finds section 2 violated: **rejected** (adverse class differs).
* leader "The disclosure requirement is satisfied.", validator "Verified evidence demonstrates the required disclosure.",
  same section judgments, same evidence, same verdict: **accepted**.
* leader `SATISFIED`, validator `NOT_APPLICABLE` (or the reverse; or `UNCLEAR` / `VIOLATED` against `NOT_APPLICABLE`): **rejected**.
  `SATISFIED` with different prose on each side, or `NOT_APPLICABLE` on both: **accepted**.
* leader cites a `VERIFIED` record about an unrelated fact for `SATISFIED` or `VIOLATED`: **rejected** (section 4a).

## 7. Why the verdict is derived and the INSUFFICIENT_EVIDENCE rule

Validators agree on structured findings, not on a free-form verdict. `INSUFFICIENT_EVIDENCE` therefore always has at least one
`UNCLEAR` finding that names a missing fact. A leader that says `UNCLEAR` when VERIFIED evidence resolves the question is
rejected by a validator whose own analysis says `SATISFIED` for that section (adverse class differs).

## 8. Failure paths and liveness

A review that fails (malformed output, validators disagree until the transaction fails) writes nothing: no review id is consumed,
the proposal status is unchanged, and the charter and evidence are untouched. Real StudioNet already needed leader rotation on
2 of 8 Stage 2 LLM submissions (operational observation, cause unconfirmed); a longer, multi-section Stage 3 prompt may rotate
more. Requiring exact finding classes and a per-finding reference check makes agreement stricter, so rotation may become more
likely, and each validator makes one extra LLM call per finding that cites evidence (at most one per section, so at most 12).
That is a liveness and cost trade-off, not a safety weakening, and the rules above were not relaxed for it.

## 9. What is NOT proven locally

The direct tests mock the LLM. They prove these rules and the contract's handling of any structured answer. They do not prove a
real model reaches sensible findings, nor how often real validators agree. That requires the StudioNet adjudication run.
