# Stage 5.1: precedent authority boundary and semantic validation

## The invariant

**Charter + current proposal (or revision) + current Evidence Vault snapshot must independently support every current finding.** Precedent may
explain consistency, interpretation, similarity or distinction. It must never make an unsupported finding valid.

Stage 5 could only guard *cited* precedent use, because its single review prompt contained the precedent block: a model could be swayed by a prior
ruling and cite nothing, and the contract could not see it. "Uncited influence cannot be detected" is not an acceptable answer, so Stage 5.1 removes
the possibility structurally instead of adding another instruction.

## The review, step by step (atomic)

1. Snapshot the current evidence (unchanged from Stage 3).
2. Snapshot the precedent candidates from this node's own state (unchanged from Stage 5).
3. **Base adjudication** (LLM call 1). `_build_review_prompt` receives the historical charter, the current proposal/revision and the current Evidence
   Vault snapshot. *Nothing else.* It does not read `precedent_candidates`/`precedent_flat`: the prompt is the Stage 3.1 prompt, byte for byte, whether
   or not candidates exist. This call alone establishes class, repairability, evidence ids, missing_fact and, deterministically, the verdict.
4. The findings are now **fixed**.
5. **Precedent-consistency pass** (LLM call 2, leader only, **only when candidates exist**). Input: the fixed findings, the current case, and the
   candidate snapshot (all untrusted data, defanged and fenced). Output: citations only, `{section_id, review_id, treatment, reason}`. The contract reads
   nothing else from this output: a finding, repairability, evidence id, missing fact or verdict it volunteers is ignored.
6. The leader's citations are validated deterministically (below) and, in consensus, **semantically** by every validator.
7. Only then is the review stored: review, findings, precedent snapshot, citations, index entry. If any of 1 to 6 fails, nothing is stored.

## Deterministic citation rules (unchanged from Stage 5)

Membership in the section's snapshot (this also gives: same exact rule revision, a different proposal lineage, a real finalized review), shape, order and
no duplicates, at most 2 per section, a non-empty reason for `DISTINGUISHED`; `FOLLOWED` needs the same finding class and, for `VIOLATED`, the same
repairability; a `SATISFIED` finding that followed an evidence-backed ruling must itself cite current evidence.

## Semantic validation (new)

Validators check the *leader's chosen* citations. They do not choose citations themselves and they do not run the precedent pass. For each cited
precedent a validator makes one bounded `PRECEDENT CITATION CHECK` call, built from the validator's **own** fixed finding, its own reconstruction of the
current case, the exact charter rule, the cited historical case and the leader's citation:

* `FOLLOWED` is supported only if the prior case is materially comparable on the constitutional issue of the section, not merely the same finding class.
* `DISTINGUISHED` is supported only if the prior case is relevant, **and** the stated difference is real (it appears in the current case data), **and**
  it is material to the constitutional treatment. Cosmetic differences (names, wording, dates, ordering) are not material and an invented difference is
  not real.

An unsupported citation makes the validator disagree, so the leader's result is not accepted and the review is not stored.

## What a real model still decides

The deterministic rules prove structure. Whether two cases are "materially comparable" or a difference is "material" is a semantic judgment made by
a model, so it is nondeterministic and can only be exercised on StudioNet; the direct tests prove the contract acts on that judgment as specified.

## Hashes: no format change

`chartergate.precedents.v1`, `chartergate.reviewcontext.v3` and `chartergate.review.v2` are exactly as in Stage 5. They already bound what Stage 5.1 needs:
the precedent snapshot (and its set hash), the cited review ids with their section association, and FOLLOWED/DISTINGUISHED, with free-form reasons
excluded. The base review is hashed over the same fields as before. Zero-candidate reviews keep `reviewcontext.v1/v2` and `review.v1`.

## LLM call shape (worst case per review)

| Situation | Leader | Each validator |
| --- | --- | --- |
| no candidates (Stage 3/4 behavior) | 1 base + N reference checks | 1 base + N reference checks |
| candidates, no citations | 1 base + 1 precedent pass + N reference checks | 1 base + N reference checks |
| candidates, C citations (C at most 2 per section) | 1 base + 1 precedent pass + N reference checks | 1 base + N reference checks + C citation checks |

N is the number of findings that cite evidence (Stage 3.1). Not optimized yet.

## The edited Stage 3 test

`tests/direct/test_review_hash.py::test_context_hash_commits_to_the_proposal_text_and_evidence_set` was edited in Stage 5 (7 insertions, 1 deletion):

* **Why the old assertion is no longer valid.** It asserted that review 2 of the same DAO carried the Stage 3 `reviewcontext.v1/v2` hash. Under Stage 5 review 2
  has review 1 as a precedent candidate, so its stored context hash is the v3 wrapper by design (it must bind the snapshot).
* **What it protected.** That the context hash commits to the proposal text and the evidence set (changing either changes the hash).
* **How it evolved.** The commitment checks are unchanged. The final assertion now recomputes the v3 string independently and also requires `!= base`.
* **What still protects the v1 format.** `test_a_review_with_no_candidates_uses_the_v1_context_and_v1_result_hash` and the Stage 3 hash tests that review a lone proposal.
* **What protects v3.** `tests/direct/test_precedent_hash.py` (independent recomputation) and `test_precedent_acceptance.py`.

Stage 5.1 changes no hash format, so this test needs no further edit.
