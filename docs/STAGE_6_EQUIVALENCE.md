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
