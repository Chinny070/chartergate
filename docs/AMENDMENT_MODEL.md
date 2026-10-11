# Amendments, governance guardrails and accountability (Stages 7 to 9)

CharterGate lets a DAO enforce the intent of its constitution. Until Stage 7 the owner edited the charter directly. Stages 7 to 9 give a charter change a recorded, checkable
path, close the direct path on request, and record what happened after a decision. This is the smallest correct version: it reuses the existing charter versioning, the
existing authorities (the owner and each proposal's proposer) and the existing consensus patterns. It adds no voting system, no new role and no outside service.

## 1. What an amendment is

An **amendment** is an immutable record of a proposed charter change:

| Field | Meaning |
| --- | --- |
| `action` | `ADD` a section, `UPDATE` an active section's wording, or `DEACTIVATE` an active section |
| `section_id`, `title`, `body` | the target and the new wording (a deactivation carries no text) |
| `base_version` | the charter version it was written against. It must equal the current version when it is proposed |
| `rationale` | the proposer's argument (1 to 1000 characters). It is data, never evidence |
| `source_proposal_id` | optional: the proposal that prompted it (`0` for none) |
| `status` | `PROPOSED`, `EVALUATED`, `APPROVED`, `APPLIED`, `REJECTED` or `SUPERSEDED` |
| `amendment_hash` | `chartergate.amendment.v1` (section 6) |

Malformed, empty or no-op changes are refused when proposed: an unknown action; an invalid section id; `ADD` of an existing id; `UPDATE` or `DEACTIVATE` of an unknown or inactive section; an
`UPDATE` whose wording equals the current wording; a `DEACTIVATE` that carries text; an empty or over-long title, body or rationale; an unknown source proposal.

## 2. The lifecycle

```
PROPOSED --evaluate--> EVALUATED --approve (owner, COMPATIBLE only)--> APPROVED --apply--> APPLIED
   |                       |                                              |
   +---- reject / withdraw (owner rejects, proposer withdraws) -----------+--> REJECTED
   +---- close_stale_amendment (the charter moved on) --------------------+--> SUPERSEDED
```

| Step | Who | Refused when |
| --- | --- | --- |
| `propose_amendment` | anyone | invalid input, or `base_version` is not the current version (`AMENDMENT_STALE`) |
| `request_amendment_evaluation` | proposer or owner | not `PROPOSED` (once), stale, `NOT_AUTHORIZED` |
| `approve_amendment` | **owner only** | not `EVALUATED`, verdict `CONFLICTING`, stale |
| `apply_amendment` | proposer or owner | not `APPROVED`, stale |
| `reject_amendment` | owner (reject) or proposer (withdraw) | not open |
| `close_stale_amendment` | proposer or owner | not open, or the charter has not moved |

Every check happens before any model call, and every state change happens after it, so a refused or failed step stores nothing.

### Staleness and competing amendments

An amendment applies **only** to the exact charter version it was written against. Two amendments written against the same version compete: the first to apply moves the charter on, and the
other can never apply (`AMENDMENT_STALE`) even if it was approved. It can be closed as `SUPERSEDED`, which records that it was never applied. Nothing silently overwrites a newer charter.

### Applying

An applied amendment goes through the **same internal code path** the owner methods use (`_charter_add`, `_charter_update`, `_charter_deactivate`), so it creates the next charter version, a new
section revision and an append-only history entry. Earlier charter versions are never altered. A proposal is still judged under the charter in force when it was submitted, a review still binds
its historical sections, and an appeal and a precedent snapshot still use the frozen record they always used.

## 3. The compatibility evaluation (advisory)

`request_amendment_evaluation` asks validators whether the change is `COMPATIBLE` with the rest of the active charter and its evident purpose. The prompt carries the current charter (only active
sections, quoted as data), the governance rules, and the proposed change as untrusted, defanged, fenced data. The answer is `{compatible, conflicting_section_ids}`.

* The list of conflicting sections must contain only other active sections, sorted, without duplicates. A compatible verdict carries none.
* Validators rebuild the same context and re-run the evaluation. They require the **same verdict and the same conflicting-section list** (identities, normalised unique and sorted, so wording never matters). A leader cannot substitute, drop or add a section identity. This tightening is in the working tree but **not in the deployed release-candidate contract** (`0xC97b…0736`, source hash `ccca5e4d…`), whose validators compared the verdict only; it takes effect only after a redeploy.
* The result is **advice**: a `COMPATIBLE` verdict approves nothing, and a `CONFLICTING` verdict blocks approval. Nothing in the model's output can approve, apply or change anything else.

## 4. The governance switch (Stage 8)

`enable_amendment_governance()` is owner-only and **one-way**. Before it, the owner's direct methods (`add_charter_section`, `update_charter_section`, `deactivate_charter_section`) work exactly
as in Stage 1, so every earlier behavior and test is unchanged. After it, they refuse with `AMENDMENT_GOVERNANCE_REQUIRED` and the charter changes only through an approved, applied amendment.

### Governance guardrails verified across the contract

* **Authorization is enforced at the contract boundary.** Every public write method is classified in `tests/direct/test_governance_guardrails.py`. A stranger is refused by each restricted method
  and changes nothing, without any model call. The owner is also refused on every proposer-only method, and the proposer on every owner-only method. A newly added write method that is not
  classified fails the completeness test.
* **Once-only operations cannot be replayed** (review, appeal, repair, revision review, amendment steps, execution closing).
* **A stale decision cannot authorize a new action** (an approval is bound to one charter version).
* **Success of the network transaction is not success of the contract execution.** The frontend shows `Finalized` only when the network finalized the transaction AND the contract executed it successfully.
* Earlier guarantees are intact: precedent remains advisory and is never evidence, evidence and charter snapshots are frozen for reviews and appeals.

## 5. Accountability (Stage 9)

### Amendments: verified by the contract

Applying an amendment is a change the contract itself makes, so its record is the contract's own state: who proposed it, the evaluation, who approved it and when, who applied it and when,
the charter version it changed and the version it created, and every lifecycle event with its actor, time and charter version (`get_amendment_accountability`). `APPLIED`,
`APPROVED_NOT_APPLIED`, `APPROVED_BUT_STALE`, `REJECTED`, `SUPERSEDED` and `NOT_APPROVED` are distinct execution states. A refused or failed transaction records nothing.

### Proposals: self-reported, never verified

The contract cannot see an outside payment, transfer or action. For a proposal whose controlling ruling is `ELIGIBLE`, the proposer can append **execution reports**
(`report_execution(proposal_id, outcome, note)`):

* `ATTEMPTED` (optional, at most once), then exactly one closing report: `REPORTED_COMPLETE` or `REPORTED_FAILED`. A closed record accepts nothing more. There is no method that edits or deletes a report.
* Each report stores the reporter, the time, the charter version the decision was made under, the controlling review, the appeal (if the decision is an appellate decision) and the hash of the ruling it answers to.
* Every report is returned with `verified: false`. The frontend labels them self-reported and never says an external action succeeded.

The approved decision, an attempted execution and a (reported) completed execution are three distinct states (`get_proposal_accountability`). An unapproved proposal cannot be reported.

## 6. Hashes (Keccak-256, lines joined by `\n`)

`chartergate.amendment.v1`:

```
chartergate.amendment.v1
action=<ADD|UPDATE|DEACTIVATE>
section_id=<id>
title=<collapsed whitespace>
body=<collapsed whitespace>
rationale=<collapsed whitespace>
base_version=<n>
proposer=<address>
source_proposal_id=<id or 0>
```

`chartergate.amendmentcontext.v1` (the exact charter an evaluation judged):

```
chartergate.amendmentcontext.v1
amendment_hash=<h>
charter_version=<n>
section=<id>@<section revision>      (one line per active section)
```

`chartergate.amendmenteval.v1` (the verdict; the list of conflicting sections is validator-agreed and stored but not hashed, and wording is never hashed):

```
chartergate.amendmenteval.v1
amendment_hash=<h>
context_hash=<h>
verdict=<COMPATIBLE|CONFLICTING>
```

The id and timestamps are not hashed. Whitespace is not material; wording is.

## 7. Contract methods added (all additive; Stage 1 to 6 methods unchanged)

Writes: `enable_amendment_governance`, `propose_amendment`, `request_amendment_evaluation`, `approve_amendment`, `reject_amendment`, `apply_amendment`, `close_stale_amendment`, `report_execution`.
Reads: `get_governance_status`, `get_amendment`, `get_amendment_count`, `get_amendments_page`, `get_amendment_accountability`, `get_proposal_accountability`, `get_precedent_overview`.
The schema grows from 57 to 72 methods; the 57 existing entries are byte-identical.

## 8. Design decisions and limits

* **Ratification is the owner.** The project's established governance authority is the owner, and there is no member registry or token. A voting system was deliberately not invented. The amendment path adds a recorded
  proposal, a compatibility check, a staleness guard and an audit trail around that authority. It does not decentralize it.
* **Anyone can propose.** Proposing costs the contract only a bounded record, and nothing takes effect until the owner approves. A spammer can create many open amendments and request their evaluations;
  there is no rate limit or fee. Recorded as a limitation.
* **The evaluation is a model's advice.** It can be wrong in either direction. The owner decides, and a `CONFLICTING` verdict is a hard block only because the owner cannot approve past it.
* **Execution reports are the proposer's word.** They make a claim visible and attributable; they do not make it true.
* **The one-way switch cannot be undone** and has no recovery path. This is intentional.
* Real model behavior is not proven locally: the direct tests mock the LLM.

Not in Stages 7 to 9: token-weighted voting, a member registry, treasury execution, appeal of an amendment, retroactive application of an amendment, and any off-chain indexer or backend.
