# Stage 5 equivalence principle: precedent-aware review

Stage 5 does not add a nondeterministic call. Precedent is part of the **existing** constitutional review
(`request_constitutional_review` / `request_revision_review`), so the Stage 3 and 3.1 rules in `docs/STAGE_3_EQUIVALENCE.md` still apply in full.
This document says only what is new. The model is in `docs/PRECEDENT_MEMORY_MODEL.md`.

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
| `FOLLOWED` compatibility | a current finding whose class differs from the cited finding, or a `VIOLATED` finding whose repairability differs |
| precedent is not evidence | a `SATISFIED` finding that followed an evidence-backed ruling but cites no current evidence |

Citing a prior case's evidence id as current evidence is rejected by the existing Stage 3 rule that an id must belong to the current snapshot.

## 4. Material agreement is unchanged

The validator runs its own analysis and the Stage 3 comparison is unchanged: the same verdict, the same class for every section, and the same repairability
for violations, plus the Stage 3.1 evidence-reference check. **Citations are not compared.** The validator's own citations are parsed leniently (invalid ones are
dropped, never an `LLM_ERROR`) because it validates the leader's selected subset instead of re-choosing it. This keeps leader rotation no higher than before.

Not compared and not hashed: the `reason` of any citation, any distinction prose, the order of explanations.

## 5. The current finding stays primary

A finding's validity never depends on a citation. Removing all citations leaves the same classes and the same verdict. Precedent explains consistency; it
cannot rescue an unsupported finding.

## 6. Failure paths

A review that fails (malformed output, an invalid citation from the leader, validators disagreeing until the transaction fails) writes nothing: no review id, no
index slot, no snapshot, no citation. The index is appended only after the review is stored.

## 7. Liveness

The leader is strict about its own citations, so a model that cites a non-candidate or follows incompatibly produces an `LLM_ERROR` and a rotation. Stage 3 and 4
live testing already showed rotations and retries for re-reviews; a longer prompt with a precedent block could make that slightly worse. This is an operational
observation to measure on StudioNet, not a relaxation of any rule.

## 8. What is not proven locally

The direct tests mock the LLM. They prove the contract's own rules. They do not prove that a real model reasons sensibly about precedent, how often it cites,
or how often validators agree. That needs StudioNet.
