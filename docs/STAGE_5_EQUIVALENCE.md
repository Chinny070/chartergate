# Stage 5 equivalence principle: precedent-aware review

Precedent is an annotation on the **existing** constitutional review (`request_constitutional_review` / `request_revision_review`). The Stage 3 and 3.1
rules in `docs/STAGE_3_EQUIVALENCE.md` still apply in full: the base adjudication is the Stage 3.1 call and **never sees precedent** (Stage 5.1). After the
findings are fixed, the leader runs one bounded precedent-consistency pass; validators semantically check the leader's chosen citations
(`docs/STAGE_5_1_AUTHORITY_BOUNDARY.md`). This document says only what is new. The model is in `docs/PRECEDENT_MEMORY_MODEL.md`.

## 1. What every node rebuilds from its own state

Each validator re-executes the transaction, so each builds its own review context, including its own precedent snapshot (candidates per section,
newest first, exact rule identity, other lineages only) and its own `precedent_set_hash`. The leader's result is the only thing received from the leader.

## 2. Exact agreement (protocol identity)

In addition to the Stage 3 identity (proposal, charter version, evidence count, evidence-set hash, context hash), the leader's result must carry the
`precedent_set_hash` equal to the validator's own. Because the context hash binds the snapshot, a different candidate set, a different candidate order, or
a different prior review hash is rejected.

## 3. Structural validity of the leader's citations (deterministic)

Every citation in the leader's result is checked against this validator's own snapshot:

| Rule | Rejects |
| --- | --- |
| membership in the section's candidates | a review outside the snapshot, a nonexistent or future review, the current review, an amended-rule review (it is not a candidate), a same-lineage review (it is excluded) |
| shape | missing or extra keys, a non-integer id, a non-list `precedents`, an unknown treatment, an oversized or non-string reason |
| order | unsorted or duplicate citations, more than 2 per section |
| `DISTINGUISHED` | an empty reason |
| `FOLLOWED` compatibility | incompatible citations produced by the leader are omitted before the result is returned; a tampered leader result containing one is still rejected |
| precedent is not evidence | a `SATISFIED` finding that followed an evidence-backed ruling but cites no current evidence |

Citing a prior case's evidence id as current evidence is rejected by the existing Stage 3 rule that an id must belong to the current snapshot.

## 4. Material agreement, then semantic validation of the leader's citations

The validator re-runs the **base adjudication only** (no precedent in its prompt, no precedent pass of its own) and the Stage 3 comparison is unchanged: the
same verdict, the same class for every section, and the same repairability for violations, plus the Stage 3.1 evidence-reference check.

It then makes one bounded `PRECEDENT CITATION CHECK` call for each citation the **leader** chose, built from the validator's own fixed finding, its own
reconstruction of the current case, the exact charter rule, the cited historical case and the citation. `FOLLOWED` must be materially comparable;
`DISTINGUISHED` needs a prior case that is relevant AND a difference that is real (present in the current case) AND material. If any check says unsupported, the
validator disagrees. A validator has no citations of its own to compare, so optional subset choice cannot cause a disagreement.

Not compared and not hashed: the `reason` of any citation, any distinction prose, the order of explanations.

## 5. The current finding stays primary

A finding's validity never depends on a citation, and (Stage 5.1) the finding is produced before the model sees any precedent. Removing all citations leaves the same
classes and the same verdict. Precedent explains consistency; it cannot rescue an unsupported finding.

## 6. Failure paths

A review that fails (malformed output, an invalid reference or treatment, a failing semantic citation check, validators disagreeing until the transaction fails) writes nothing: no review id, no
index slot, no snapshot, no citation. The index is appended only after the review is stored.

## 7. Liveness

An incompatible `FOLLOWED` citation is now omitted deterministically: it cannot veto the fixed constitutional findings. Other malformed citations and references still fail closed, and validators may still reject a citation they find semantically unsupported. This reduces one specific source of leader rotation; it does not guarantee validator agreement on live LLM judgments.

## 8. What is not proven locally

The direct tests mock the LLM. They prove the contract's own rules. They do not prove that a real model reasons sensibly about precedent, how often it cites,
or how often validators agree. That needs StudioNet.

## 9. Frozen: live verification status and backlog

Stage 5 (including Stage 5.1) is complete and frozen. Verification contract: `0x9F846B040DA015F4Aed94467Af065Cd7c84dbeCA` (`canonicalDeployment` is `null`).
Proven live on StudioNet and in the browser (see `deployments/studionet.json`): a first case with no precedent (old hash formats); a FOLLOWED and a DISTINGUISHED
citation; prior evidence never counting as current evidence; amended-rule exclusion (`s3@4` cases are not candidates for `s3@5`); same-lineage exclusion;
snapshot immutability; newest-first candidates capped at 2 per section; independent recomputation of every precedent set hash, context hash and review hash; and
a browser review showing the Precedent Memory panel and the prior-ruling inspector.

Backlog (non-blocking; no prompt, equivalence, validator or contract change is implied):

* **S5-R1** Constitutional reviews can still experience `BAD_MISSING_FACT` / `MAJORITY_DISAGREE` rotations.
* **S5-R2** Precedent consistency and review prose may be returned in a language different from the frontend language.
* **S5-R3** StudioNet's practical RPC read limit makes complex case pages take roughly 30 to 40 seconds to settle even after request deduplication and throttling.
* **S5-R4** Precedent-specific atomic failure was not deliberately forced live; the direct tests prove this path.
* **S5-R5** Precedent poisoning remains only partially mitigated by exact-rule matching, bounded candidates, lineage exclusion, advisory semantics and
  independent current-case adjudication.
