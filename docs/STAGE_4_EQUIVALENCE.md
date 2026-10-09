# Stage 4 equivalence principle: repair admissibility

`submit_repair_revision(proposal_id, title, description, requested_action)` runs one non-deterministic block
(`gl.vm.run_nondet(leader_fn, validator_fn)`) that answers ONE question:

> Does this proposed revision preserve the fundamental purpose and identity of the parent proposal while materially addressing
> at least one repairable deficiency identified in the parent review?

It is **not** another constitutional review. Whether the revision now complies with the charter is decided later, by the Stage 3
review of the revision (`request_revision_review`). Repair admission and constitutional compliance are different decisions.
It does not use `strict_eq` on LLM output and never compares prose.

## 1. How validators get their own context

As in Stages 2 and 3, every validator re-executes the transaction against its own copy of contract state. The deterministic
part builds a plain `rctx` from state (the parent revision, the latest review's repairable findings, the charter text at the
proposal's own charter version, the proposed text); the closures passed to `run_nondet` capture only that `rctx`. A validator never
trusts the leader's context: the only thing it receives from the leader is the leader's result.

## 2. Where the repair targets come from

Not from an LLM. They are the **parent review's own `VIOLATED` findings with `repairable = true`**, read from the immutable stored
review, with the section text as it read at the proposal's charter version and the stored rationale. The model is asked only
which of those targets the revision addresses.

## 3. The LLM's structured answer

```
{"same_fundamental_purpose": bool, "material_scope_change": bool, "addressed_section_ids": [...], "short_reason": "..."}
```

* `addressed_section_ids` may contain only repair-target ids. Any other id (a non-target section, an unknown section) makes the
  answer invalid (`LLM_ERROR:BAD_SECTION_REF`): a claim about a section that is not a repair target is not a repair claim.
* Every field is validated; anything else fails closed (`LLM_ERROR:*`) and forces rotation.
* **The LLM never supplies `admissible`.** It is derived by deterministic code, in this precedence:
  1. `same_fundamental_purpose = false` gives `PURPOSE_CHANGED`
  2. otherwise `material_scope_change = true` gives `SCOPE_CHANGED`
  3. otherwise no addressed target gives `NO_TARGET_ADDRESSED`
  4. otherwise admissible

An inadmissible result rolls the transaction back with `EXPECTED:REPAIR_REJECTED:<REASON>`. Because it is a rollback, no revision,
no revision id and no status change survives. Partial repair is allowed: addressing only some targets is admissible.

## 4. Exact agreement (protocol-critical identity)

A validator rejects unless the leader's result equals what the validator reconstructed:

| Field | Must equal |
| --- | --- |
| `proposal_id` | the proposal being repaired |
| `parent_revision_id` | the current effective revision (0 = the original proposal) |
| `source_review_id` | the proposal's latest review |
| `charter_version` | the proposal's charter version at submission (never the current charter) |
| `target_ids` | the repair-target section ids derived from the parent review |

## 5. Structural validity

Exactly the documented keys; booleans are booleans; `addressed_section_ids` is a sorted, duplicate-free list of repair-target ids;
`short_reason` at most 300 characters. The agreed result is checked once more after consensus.

## 6. Material semantic agreement

After the checks above, the validator runs its own analysis (same prompt, built from its own `rctx`) and requires:

1. the same `same_fundamental_purpose`
2. the same `material_scope_change`
3. the same set of addressed repair-target sections (so whether any target was addressed also agrees)

Not compared: `short_reason` wording. If the validator's own analysis fails for any reason it **rejects**, and a failed leader is
always rejected, which forces rotation. Two nodes that agree the repair is inadmissible agree on the rejection too.

## 7. Prompt boundary

The Stage 3.1 rule holds. The prompt's GOVERNANCE RULES section is the only place that instructs the model. The charter sections the
parent fails are passed as quoted constitutional content in a `<<<DATA ... DATA>>>` block; the parent review's rationales, the parent
proposal and the proposed revision are untrusted DATA blocks. Fence markers inside any of it are neutralised. Nothing in them can
instruct the model, and nothing can set admissibility because it is derived. Evidence is not part of the repair prompt at all.

## 8. Failure paths and liveness

A failed repair writes nothing. Stage 3 live testing already showed that LLM-backed agreement can need several rounds or a fresh
transaction; requiring exact agreement on three semantic facts is strict and may rotate often. That is a reliability observation,
not a relaxation of the rules (see the Stage 3 reliability backlog).

## 9. What is NOT proven locally

The direct tests mock the LLM. They prove these rules and how the contract handles any structured answer. They do not prove that a
real model separates a repair from a replacement, nor how often validators agree. That needs StudioNet.

## 10. Frozen: live verification status and backlog

Stage 4 is complete and frozen. Verification contract: `0xF7370b75a34D23F715E936317C3f4793188cB59d` (`canonicalDeployment` is `null`).
Proven live on StudioNet and in the browser (see `deployments/studionet.json`): valid full repair then ELIGIBLE; an unrelated replacement
rejected with `REPAIR_REJECTED:PURPOSE_CHANGED` and no revision created; a partial repair admitted then REPAIRABLE; a further repair then
ELIGIBLE; and a browser repair admitted then REPAIRABLE. Transaction success, repair admissibility and constitutional compliance are three
different results, and all three were observed to differ.

The missing browser repair transaction hash is accepted as a documentation gap: the revision exists on-chain, its hash recomputes
independently, and review #7 judged it.

Backlog (non-blocking; no prompt, equivalence, validator or contract change is implied):

* **S4-R1** Re-review consensus can require multiple rotations or retries, including `BAD_EVIDENCE_REF`, `BAD_MISSING_FACT` and `BAD_FINDINGS`.
* **S4-R2** Revision-limit enforcement is directly tested but was not exercised live on StudioNet.
* **S4-R3** LLM rationale and `missing_fact` language is not guaranteed to match the UI language; one live review returned Chinese text. These
  prose fields stay outside consensus and hash identity.
* **S4-R4** The repair-editor UX should keep making it obvious that users are editing the current proposal and not accidentally replacing
  important existing context (a live browser repair replaced the description with only the budget line).
