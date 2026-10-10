# Precedent memory model (Stage 5)

CharterGate no longer judges each case in isolation. A new constitutional review can see a bounded set of the DAO's earlier rulings under
the same charter rule, and can say whether it **followed** or **distinguished** them. Precedent is memory and consistency, never law.

## 1. Authority hierarchy

1. the historical charter that governed the proposal (normative authority, never prompt authority)
2. the current proposal or revision facts
3. the current Evidence Vault records (VERIFIED only, as in Stage 3)
4. precedent: **advisory** interpretive context

Precedent never outranks the charter and never replaces evidence. It is not labelled binding, controlling or law anywhere.

## 2. The precedent unit and rule identity

The unit is one **section-level finding** of a finalized review: "§s3 Budget was VIOLATED (repairable) in Review #12". A review is therefore
several independent precedents, one per section.

Two findings are about the same rule only if they share **rule identity = section id + the section's revision version**
(`s3@4` means section `s3` as produced by charter version 4). The revision comes from the existing historical-charter machinery
(`_effective_revision`). Matching on the section id alone would apply old law after an amendment, so it is not done: a case judged under
`s3@4` is not precedent for a case judged under `s3@5`. Cross-amendment jurisprudence is not part of Stage 5.

Note that a proposal submitted before an amendment is still judged under the old rule even if reviewed later, so it is correctly matched with
other cases under the old rule.

## 3. The index and candidate selection

When a review is **successfully stored**, it is appended to `rule_precedents[<rule>]` for each of its sections (all four finding classes:
`NOT_APPLICABLE` is useful history about scope). A failed review writes nothing and takes no slot.

For each active section of a new review the contract selects, deterministically:

* only reviews under the exact same rule identity;
* newest first (highest review id first), at most **2** per section (so at most 24 candidates for the 12-section maximum);
* skipping reviews of the **same proposal lineage** (same root `proposal_id`), because a proposal's own earlier reviews are already visible
  through its Stage 4 revision history and counting them would make re-reviews self-referential;
* scanning at most 16 index slots per rule (a lineage has at most 7 reviews, so this is never the limiting bound).

A revision review of another proposal can itself be a precedent. The current review is never in its own snapshot: it enters the index only
after it is stored.

## 4. The precedent snapshot

Every precedent-aware review stores its **snapshot**: the exact candidates (section, rule, prior review id, prior review hash) in order, plus the
`precedent_set_hash`. It is immutable and independent of the index: Review #40 can never change what Review #27 saw. Reads:
`get_review_precedents(review_id)`, `get_rule_precedents_page(rule, offset, limit)`, `get_rule_precedent_count(rule)`, `get_precedent_case(review_id, section_id)`.

### `precedent_set_hash` (`chartergate.precedents.v1`, Keccak-256, lines joined by `\n`)

```
chartergate.precedents.v1
count=<number of candidates>
section=<current section id>|rule=<section>@<revision>|precedent_review_id=<id>|precedent_review_hash=<hash>   (one line per candidate, in snapshot order)
```

It binds each candidate unambiguously (which section, which exact rule, which prior review and its hash). It contains no prose. It is `""` when
there were no candidates.

## 5. Citations: FOLLOWED and DISTINGUISHED

A finding may cite at most 2 precedents from **its own section's snapshot**, each with `review_id`, `treatment` and a short `reason`
(at most 200 characters, prose, never compared or hashed). Citing nothing is always acceptable and never an error, and it does not mean no precedent
existed (the snapshot records that). Structural rules, all deterministic:

* the cited review must be one of that section's candidates (this also guarantees: same rule revision, a different lineage, a real finalized review);
* no duplicates, sorted by section then review id;
* **FOLLOWED** means consistent: the cited finding class equals the current finding class, and for `VIOLATED` the repairability matches. Validators also confirm semantically that the prior case is materially comparable;
* **DISTINGUISHED** needs a non-empty reason that names a difference that is real (present in the current case) and material; validators confirm that semantically. Any class combination is allowed.

## 6. Precedent is not evidence

A prior ruling may help interpret applicability, meaning, materiality and repairability. It cannot establish a fact about the current proposal.

Enforced structurally:

* a prior case's evidence appears in the prompt only inside the precedent block, labelled historical. The current VERIFIED evidence block is unchanged;
* a finding may cite only evidence ids from the **current** proposal's snapshot, so borrowing a prior case's evidence id fails (`BAD_EVIDENCE_REF`);
* a `SATISFIED` finding that `FOLLOWED` an **evidence-backed** ruling must itself cite current evidence (`PRECEDENT_NOT_EVIDENCE`);
* the finding stays valid or invalid on the charter, the current case and the current evidence alone: removing every citation does not change it.

Stage 5.1 closes the earlier "uncited influence" gap structurally: the model call that establishes the finding never receives precedent (see section 9). The
precedent-consistency pass runs after the findings are fixed and can only add citation metadata.

## 7. Hashing

* Reviews with **no** candidates keep the Stage 3 / 4 formats exactly (`chartergate.reviewcontext.v1` / `v2`, `chartergate.review.v1`).
* Reviews with candidates use **`chartergate.reviewcontext.v3`**:

  ```
  chartergate.reviewcontext.v3
  base_context_hash=<the v1 or v2 context hash>
  precedent_set_hash=<hash>
  ```

* Reviews that **cite** a precedent use **`chartergate.review.v2`**: the v1 lines, then
  `precedent=section=<id>|review=<id>|treatment=<FOLLOWED|DISTINGUISHED>` per citation. Candidates without citations keep the v1 result format
  (the v3 context already binds the snapshot). Reasons are excluded, so equivalent judgments with different prose hash identically, while
  FOLLOWED versus DISTINGUISHED (or a different cited review or section) changes the hash.

## 8. Prompt boundary and size

Everything a prior ruling carries is **untrusted data**: its proposal or revision text, rationale, missing fact, and evidence claim, quote, value
and fact. Each is defanged (fence markers neutralised) and sits inside a `<<<DATA ... DATA>>>` block under the heading
`UNTRUSTED PRECEDENT CONTEXT`, after the governance rules. Stored on-chain does not mean trusted: an old model-generated rationale that says "ignore
all instructions" is just data. The governance rules state that precedent is advisory, can never establish a current fact, and may be omitted.
The precedent block appears only in the precedent-consistency pass (and the per-citation validator check), **never** in the base adjudication prompt, which is
byte-for-byte the Stage 3.1 prompt with or without candidates. When there are no candidates no precedent prompt exists at all.

Context is bounded by truncation (deterministic, prompt only, never hashed): title 80, description 300, action 100, rationale 200, missing fact 80
characters, and at most 2 historical evidence records of 100 characters per field. The full prior ruling is read on demand with `get_precedent_case`.

## 9. Cost and consensus

Stage 5.1: the base adjudication is unchanged. When candidates exist the leader makes **one** extra bounded precedent-consistency call over the fixed findings;
its citations are strict (an invalid citation is an `LLM_ERROR`, which rotates, and nothing is stored). A validator does not run that pass: it re-runs the base
adjudication and makes one bounded semantic check per citation the leader chose (at most 2 per section). With no candidates there is no extra call. See
`docs/STAGE_5_EQUIVALENCE.md` and `docs/STAGE_5_1_AUTHORITY_BOUNDARY.md`.

## 10. Precedent poisoning and spam: a known limitation

Stage 5 has no reputation, voting or approval of precedent. Anyone may create contrived proposals and reviews. Mitigations are partial:
exact rule matching, a bounded candidate set (2 per section), same-lineage exclusion, precedent staying advisory, precedent never substituting for
evidence, and validators still adjudicating the current case independently. This does **not** fully solve poisoning (for example, a flood of recent
contrived rulings can crowd out older useful ones within the 2-per-section window). It is recorded for future governance work.

## 11. Not in Stage 5

Appeals, appellate review, dissent, overturning or hierarchy of precedent, precedent weight or binding force, cross-amendment jurisprudence,
amendment governance, voting, treasury execution and accountability.
