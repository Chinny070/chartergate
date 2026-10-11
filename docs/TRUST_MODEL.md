# Trust model: what validators verify, and what stays advisory

Every nondeterministic path runs the leader once and each validator independently (`gl.vm.run_nondet(leader_fn, validator_fn)`). A leader's output is accepted only if the checks below pass; a failed
leader or an unusable validator output is a rejection, which forces a leader rotation (fail closed). Prose is never compared or hashed.

Last audited against the working tree (source hash differs from the deployed contract only by the amendment conflict-list check, see section 3).

## 1. Per path

| Path | Independently verified by every validator | Advisory or display-only (not validator-agreed) |
| --- | --- | --- |
| Evidence (`submit_evidence`) | protocol identity (proposal, URL, retrieval method, fact key); status; for `VERIFIED`: the quote exists in the validator's own fetch, the canonical value equals its own, and the quote states the value for that fact (semantic binding) | `reason` code; the observed value and quote on a non-`VERIFIED` record (a different fetch may legitimately show other text); whether the source is authoritative (see section 2) |
| Review (`request_constitutional_review`) | identity and context hashes; one finding per active section; each finding's class; repairability of `VIOLATED` findings; the derived verdict; every cited evidence id materially supports its finding (own reading of the immutable records); every precedent citation is supported | `rationale`; `missing_fact` wording (explicitly allowed to differ); which of several valid supporting evidence ids the leader chose |
| Repair (`submit_repair_revision`) | same purpose, scope change, and the exact set of addressed targets | `short_reason` |
| Appeal (`request_appeal`) | everything a review checks, plus the deterministic `decision_kind` | prose |
| Reasoned dissent | the leader's alternative is defensible and its cited evidence supports it; a claim of "no dissent" is accepted only if the validator also finds none; the disagreeing sections are recomputed, never declared | the dissent is non-controlling and AI-generated, never a vote |
| Amendment evaluation | the verdict **and the conflicting-section list** (section ids are identities, compared after normalising to unique and sorted) | the model's prose (none is stored) |

## 2. Known design limits

* **A page that contains a claim is not an authoritative source.** Evidence proves that a fetched page states a value for a fact; it does not prove the page is trustworthy. Review treats `VERIFIED` evidence as
  support, not truth about the world.
* `missing_fact` and `rationale` are prose and are deliberately not compared; a hostile leader can word them misleadingly, but cannot change a class, repairability, verdict or hashed field.
* Execution reports are self-reported by the proposer and always `verified: false`.
* The compatibility evaluation is advice. The owner decides, and a `CONFLICTING` verdict blocks approval.

## 3. Hostile-leader coverage

Direct tests (`tests/direct/`, mocked LLM) replay the real validator against altered leader output: identity swaps, wrong ids, fabricated verified results, different verdicts and classes, unrelated evidence,
unsupported citations, tampered dissents, and (added in this audit) a substituted, omitted, added or duplicated amendment conflict list. These prove the validator logic; they are **not** live consensus evidence.
The amendment conflict-list check was added after the release-candidate deployment, so the deployed contract does not have it until it is redeployed.
