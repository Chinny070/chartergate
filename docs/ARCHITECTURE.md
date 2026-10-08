# Architecture notes

## Verified in Stage 0 (frontend and SDK)

Source: the installed `genlayer-js@1.1.8` type definitions and bundle (`node_modules/genlayer-js/dist`),
plus `genvm-linter 0.11.0` and `genlayer-test 0.29.2` behaviour run locally. The docs MCP and the
official skills plugin were not available in this session, so docs.genlayer.com was not consulted.

| Item | Finding |
| --- | --- |
| Chain | `studionet` exported from `genlayer-js/chains`; `id: 61999`, native GEN, 18 decimals |
| Client | `createClient({ chain, account?, provider? })`; `account` as an address string routes signing methods via `window.ethereum` |
| Reads | `client.readContract({ address, functionName, args, transactionHashVariant })` |
| Writes | `client.writeContract({ address, functionName, args, value })` returns a tx hash |
| Receipts | `client.waitForTransactionReceipt({ hash, status, interval, retries })`, `client.getTransaction({ hash })` |
| Schema | `client.getContractSchema(address)` |
| Statuses | `TransactionStatus`: PENDING, PROPOSING, COMMITTING, REVEALING, ACCEPTED, UNDETERMINED, FINALIZED, CANCELED, APPEAL_REVEALING, APPEAL_COMMITTING, READY_TO_FINALIZE, VALIDATORS_TIMEOUT, LEADER_TIMEOUT |
| Contract header | `# v0.2.16` + pinned `Depends` hash; lints clean with `genvm-lint` |

## Decisions

- ACCEPTED maps to UI `pending`, not `finalized`: it is still inside the appeal window.
- UNDETERMINED, CANCELED and both timeouts map to `failed` (fail closed).
- Network switching uses standard EIP-3085/3326 wallet requests instead of genlayer-js
  `client.connect()`, because the latter also installs a MetaMask Snap.
- `frontend/src/lib/genlayer/contract.ts` is a generic boundary (`readView`, `submitWrite`) with
  no method names. Named wrappers wait until the deployed schema exists (Stage 8).
- Keep the contract's leading comment block to the two header lines. Longer comment blocks have
  broken GenLayer Studio schema loading before.

## NOT yet verified (needed in later stages)

- GenVM web fetch/render API names (Stage 3)
- `gl.eq_principle` / custom leader-validator API (Stage 4)
- Stage 1 resolved the storage syntax and the contract timestamp source (see Stage 1 below).
- Whether `gltest` integration runs with an empty `tests/integration/` (needs a running Studio)

## Known environment notes

- Windows: `tests/conftest.py` patches a `genlayer-test` direct-mode `os.unlink` PermissionError.
- `genlayer-js` depends on eslint 9, so `@eslint/js` is pinned to `^9`.
- The production bundle is ~790 kB (viem + genlayer-js); code-splitting is a later optimisation.


---

# Stage 1: charter and proposal contract

## What was verified, and against what

Stage 1 contract APIs were checked against three sources, in this order of authority:

1. The **pinned runner's own source**: the `v0.2.16` `genlayer` Python package extracted by
   `genvm-linter` / `genlayer-test` (`~/.cache/gltest-direct/extracted/v0.2.16/...`). This is what the
   contract actually runs on.
2. The official **genlayer-dev skills** v1.1.4 (`write-contract`, `direct-tests`, `genvm-lint`) installed from
   `genlayerlabs/skills`, read from the plugin cache.
3. The official **SDK API reference** (`https://sdk.genlayer.com/main/_static/ai/api.txt`).

The docs MCP server was added to the user's CLI but is not loaded in this desktop session, so it was not used.

| API | Verified form (v0.2.16) | Notes |
| --- | --- | --- |
| Contract base | `class X(gl.Contract)` after `from genlayer import *` | |
| Header | `# v0.2.16` then `# { "Depends": "py-genlayer:1jb45aa8..." }` | pinned; no `latest`/`test` |
| Caller | `gl.message.sender_address` | the skill skeleton also shows `sender_account`, which is not in v0.2.16; ignored |
| Timestamp | `gl.message_raw["datetime"]` (ISO string) | documented as the transaction datetime. `gl.vm.get_timestamp()` is main-branch (v0.3.0) only and does **not** exist in v0.2.16 |
| Errors | `raise gl.vm.UserError("EXPECTED:CODE")` | `UserError(message: str)` in v0.2.16 (the `.data` payload is v0.3.0) |
| Storage dataclass | `@allow_storage` on a class with annotated fields | renamed `gl.storage.allow` in v0.3.0; not used here |
| Collections | `TreeMap[K, V]`, `DynArray[T]`; `.get(k)` returns `None` when absent; `len()`; append | start empty, no init needed |
| Integers | `u256` for ids and counters | explicit overflow guard in `_next` |
| Views / writes | `@gl.public.view`, `@gl.public.write` | views return plain dicts/lists |
| Constructor | `def __init__(self, a: str, b: str)` with **no** `-> None` | a return annotation breaks Studio schema load (project memory) |

## Data model

```
CharterGate (gl.Contract)
  owner: Address                       set to the deployer, never changes
  dao_name, dao_description: str
  charter_version: u256                starts at 1
  created_at, updated_at: str          ISO transaction datetimes
  sections: TreeMap[str, CharterSection]
  section_ids: DynArray[str]           insertion order, for pagination
  proposals: TreeMap[u256, Proposal]
  proposal_count: u256

CharterSection  section_id, title, body, active: bool, created_at, updated_at
Proposal        proposal_id: u256, proposer: Address, title, description, requested_action,
                created_at, charter_version_at_submission: u256, status: str
```

One contract represents one DAO. There is no factory or multi-tenancy.

## Methods (from `docs/charter_gate.schema.json`)

Generated locally with `genvm-lint schema contracts/charter_gate.py --json`; no deployment was needed.

| Method | Kind | Caller |
| --- | --- | --- |
| `constructor(dao_name, dao_description)` | init | deployer becomes owner |
| `add_charter_section(section_id, title, body)` | write | owner |
| `update_charter_section(section_id, title, body)` | write | owner |
| `deactivate_charter_section(section_id)` | write | owner |
| `submit_proposal(title, description, requested_action)` | write | anyone |
| `get_dao_metadata()` | view | |
| `get_charter_version()` | view | |
| `get_charter_section(section_id)` | view | |
| `get_charter_section_count()` | view | |
| `get_charter_section_ids_page(offset, limit)` | view | |
| `get_charter_sections_page(offset, limit)` | view | |
| `get_charter_revision(charter_version)` | view | history (Stage 1.1) |
| `get_charter_section_at_version(section_id, charter_version)` | view | history (Stage 1.1) |
| `get_charter_section_count_at_version(charter_version)` | view | history (Stage 1.1) |
| `get_charter_sections_at_version_page(charter_version, offset, limit)` | view | history (Stage 1.1) |
| `get_proposal(proposal_id)` | view | |
| `get_proposal_count()` | view | |
| `get_proposals_page(offset, limit)` | view | |

Pages are capped at 50. There is deliberately no method that approves, rejects, reviews, edits, cancels
or changes the status of a proposal.

## Access control

- The **owner** is `gl.message.sender_address` at deployment. Only the owner may add, update or deactivate
  charter sections; each such method calls `_require_owner()` first and fails with `EXPECTED:NOT_OWNER`.
- There is **no** ownership transfer, renounce or admin override. This is the Stage 1 bootstrap mechanism
  only; governed amendment is a later stage.
- Anyone may submit a proposal. The proposer is the caller.
- Deactivated sections cannot be edited or re-deactivated (`SECTION_INACTIVE`, `SECTION_ALREADY_INACTIVE`).
  There is no reactivation.

## Charter versioning model

`charter_version` starts at 1 and increases by exactly 1 on every successful add, update or deactivate.
Validation always runs before any write, so a rejected call changes nothing and never consumes a version.

Every proposal records `charter_version_at_submission`. Since Stage 1.1 the exact charter text for any past
version can be reconstructed (see "Immutable charter history" below).

## Timestamps

All timestamps come from `gl.message_raw["datetime"]`, the transaction datetime GenVM supplies. No wall-clock
time, no frontend `Date.now()`, no external time source. The frontend formats the on-chain string for display
and always shows the canonical value beside it.

Test-harness note: `genlayer-test` 0.29.2 direct mode reads `message_raw` once and does not refresh its
datetime on `warp()`. `tests/conftest.py` patches that so tests can control time; real GenVM builds a new
message for every transaction.

## Proposal lifecycle

Only one status exists: `SUBMITTED`. A proposal is created in that status and never changes. Later statuses
(review, verdicts, appeal, execution) are intentionally not defined yet.

## Errors

Deterministic validation errors are `gl.vm.UserError("EXPECTED:<CODE>")`, for example `EXPECTED:NOT_OWNER`,
`EXPECTED:SECTION_ID_EXISTS`, `EXPECTED:SECTION_BODY_EMPTY`. No `EXTERNAL`, `TRANSIENT` or `LLM_ERROR` paths
exist because Stage 1 has no web or LLM calls. No broad `except` is used.

## Not implemented

Evidence, web fetch/render, LLM review, equivalence logic, verdicts, repair, appeals, precedent, amendments,
voting, execution, accountability. The frontend labels these as not implemented.

## Known limits

- Counter overflow is guarded by `_next` but cannot be exercised in a direct test.
- Frontend writes have not been run against a live network; the contract is not deployed.


---

# Stage 1.1: immutable charter history

## Invariant

If proposal P was submitted at charter version 4 and the charter later reaches version 9, the contract can still
return the exact sections in force at version 4. A later adjudicator must read the charter *as of the proposal's
`charter_version_at_submission`*, never the current text. A proposal is never re-bound to a newer version.

## Storage model

Two structures were added next to the existing current-state map; nothing was removed.

```
revisions:        DynArray[CharterRevision]       append-only log, one entry per charter mutation
section_versions: TreeMap[str, DynArray[u256]]    per section: ascending charter versions at which it changed

CharterRevision   section_id, charter_version: u256, title, body, active: bool, changed_at: str
```

`sections` / `section_ids` still hold the *current* state, so existing current-state reads are unchanged.

Why this and not snapshots: a snapshot of the whole charter per version would copy every unchanged section on
every mutation (O(sections x versions) storage). A revision stores only what changed, so storage grows by one
small record per mutation. The trade-off is that reading an old version needs a lookup instead of a direct read;
that lookup is a binary search, so it stays cheap.

## How reconstruction works

Each successful add, update or deactivate increases `charter_version` by exactly 1 and appends exactly one
revision. Therefore **the revision that produced version `v` is `revisions[v - 2]`** (version 1 is the empty
initial charter and has no revision). This gives O(1) access to any revision by version.

- **A section as of version N:** `section_versions[id]` is ascending. Binary-search it for the last entry <= N;
  that entry's revision is the text in force. No such entry means the section did not exist yet
  (`SECTION_NOT_FOUND_AT_VERSION`).
- **The whole charter as of version N:** sections are appended in creation order, which is also charter-version
  order, so the sections that existed at N are always a **prefix** of `section_ids`. That prefix is found with a
  binary search over each section's first version, and then paginated normally. Deactivated sections stay
  listed with `active = false`.
- **Bounds:** `1 <= N <= current charter_version`, otherwise `CHARTER_VERSION_NOT_FOUND`. A future version cannot
  be queried. Pages are capped at 50, so no read is unbounded.

Revisions are only ever appended by the three owner methods. No public method updates, deletes or reorders them;
tests assert both that the methods do not exist and that old revisions are unchanged after later activity.

## Bootstrap owner model

Owner-controlled charter mutation is **bootstrap governance only**. The deployer is the owner and there is no
transfer. It exists so a charter can be created before a constitutional amendment process exists. In a later
stage, governed amendment replaces direct owner modification as the normal policy path. Ownership transfer was
not added because no authoritative spec requires it.

## Timestamp source (re-verified)

`gl.message_raw["datetime"]` is still used. It matches the pinned v0.2.16 SDK source on disk, where
`MessageRawType.datetime` is documented as the transaction datetime. `datetime.now()` was not used, even though
the direct-test harness warps it: the contract must use protocol time, not process-local wall-clock time. The only
workaround lives in `tests/conftest.py` (test tooling only).

## Frontend guard

`frontend/src/lib/genlayer/charterGate.ts` exports a `CONTRACT_METHODS` table. A vitest test compares it to
`docs/charter_gate.schema.json`, so a renamed method or changed argument count in the contract fails the frontend
tests. The proposal page shows the charter text in force at submission using the historical views.

## Live StudioNet findings (Stage 1.1 verification deployment)

Contract `0x4cF37AEE922c02513E2826FDd613588c2A922E0d` (see `deployments/studionet.json`). This is a verification
deployment, not the canonical one: the owner is permanent.

- **Schema and code:** the deployed schema is identical to `docs/charter_gate.schema.json` (17 methods), and the
  deployed source equals `contracts/charter_gate.py` after normalising line endings.
- **Timestamps:** `gl.message_raw["datetime"]` returned real, increasing transaction times
  (`2026-10-07T16:57:36Z` deploy, `17:05:33Z` s1, `17:06:19Z` s2, `17:09:37Z` proposal, `17:11:18Z` update), so it
  behaves correctly in real GenVM execution.
- **Return decoding (via genlayer-js `readContract`):** dicts arrive as plain JS objects, integers as `number`,
  plus `string`, `boolean` and arrays of objects. The frontend decoders match.
- **View reverts are opaque:** a view that raises (unknown version or section) reaches the SDK only as
  `InvalidInputRpcError: Missing or invalid parameters`; the `EXPECTED:` code is not visible. The UI should treat
  this as "not found or invalid". Write reverts do expose it in the receipt (`rollback`, `EXPECTED:NOT_OWNER`).
- **A finalized transaction can still have failed.** Check `execution_result` of the leader and the result payload.
  Receipts also contain `ERROR` entries with `Validator execution cancelled after quorum`
  (`VALIDATOR_QUORUM_REACHED`); these are benign and appear on successful transactions.
- **No argument type guard (open issue):** GenVM does not enforce annotated argument types. A caller that sends an
  int where a `str` is expected makes the contract raise a raw `TypeError` instead of an `EXPECTED:` error. It fails
  closed (nothing changes), but the error is not clean. Seen via the `genlayer` CLI, which turns numeric-looking
  arguments into ints and cannot send a string such as `"1"`; genlayer-js sends JS strings as strings.

---

# Stage 1.2: argument validation

## Problem

GenVM does not enforce Python annotations at the contract boundary. A caller that sends an integer where a string
is expected reaches `len()` or `.strip()` and raises a raw `TypeError` / `AttributeError`. On the Stage 1.1
verification deployment this happened live (the `genlayer` CLI turns a bare `1` into an int). Direct tests also showed
`ValueError` (non-numeric page offset) and `IndexError` (negative page offset) leaking out.

## Rule

Every argument that reaches a public method is type-checked **before** it is used:

- `_str_arg(name, value)`: must be a `str`, else `EXPECTED:INVALID_TYPE:<name>`.
- `_int_arg(name, value)`: must be an `int` and **not** a `bool`, else `EXPECTED:INVALID_TYPE:<name>`; it must also
  be within 0 to 2^256-1, else `EXPECTED:INTEGER_OUT_OF_RANGE:<name>`.
- `bool` is rejected explicitly because `True == 1` in Python, so `get_proposal(True)` would otherwise return
  proposal 1.
- `<name>` is the parameter name (`section_id`, `title`, `body`, `description`, `requested_action`, `dao_name`,
  `dao_description`, `offset`, `limit`, `charter_version`, `proposal_id`), so a failure points at the bad argument.

Covered: the constructor, all four writes, and every view that takes arguments.

## Order of checks

Caller authorisation comes first (`NOT_OWNER`), then argument types, then value rules (empty, too long, exists,
not found). A stranger sending malformed input therefore gets `NOT_OWNER`.

## Fail-closed

A rejected call raises before any write, so it creates no revision, consumes no proposal id, leaves the charter
version and every timestamp unchanged. 242 direct tests assert this with a full snapshot (metadata, current
sections, every revision, every proposal) taken before and after each rejected call.

## Live verification

On the Stage 1.2 deployment, a CLI call that sends `section_id` as the integer `1` is rolled back with
`EXPECTED:INVALID_TYPE:section_id`, with empty stdout/stderr (no traceback), and the state snapshot is identical
before and after. See `deployments/studionet.json`.

## Notes

- View reverts still reach `genlayer-js` only as a generic `InvalidInputRpcError`; the error code is visible in
  write receipts, not in read results.
- On-chain timestamps vary in sub-second precision (`...19:47:10.102Z` vs `...19:48:13.090065Z`). Both parse with
  `new Date()`, but code must not assume a fixed fractional-second width.
- `my-studionet-wallet` owns both verification deployments permanently. Neither is canonical.

---

# Stage 1.3: finality is not success

## The bug

The Stage 1.2 UI showed `finalized` whenever the network status was `FINALIZED`. In GenLayer that is only
**consensus** finality. A transaction can be `FINALIZED` while the contract **rolled back**: live example,
`offset-bob` calling an owner-only method is FINALIZED with a rollback payload `EXPECTED:NOT_OWNER`, and no state
changes. The UI would have shown a green success.

## Two separate facts

| Question | Where it comes from | Examples |
| --- | --- | --- |
| Consensus: did validators finalize it? | `statusName`, and `result` (number, named by `transactionResultNumberToName`) | PENDING, ACCEPTED, FINALIZED; MAJORITY_AGREE |
| Execution: did the contract succeed? | the leader's receipt (StudioNet) or `txExecutionResultName` (other chains) | SUCCESS / rollback / contract error |

`TxState` keeps both (`networkStatus`, `consensusResult`, `execution`). The UI shows them side by side, for
example `network FINALIZED · consensus MAJORITY_AGREE · execution ROLLED BACK (EXPECTED:NOT_OWNER)`.

## Rule

`classifyTransaction` (in `tx.ts`) is the only place that decides the user-facing outcome:

| Input | Result |
| --- | --- |
| not final (PENDING, PROPOSING, COMMITTING, REVEALING, ACCEPTED, READY_TO_FINALIZE, APPEAL_*) | `pending`. ACCEPTED is pending: it is still inside the appeal window |
| UNDETERMINED, CANCELED, LEADER_TIMEOUT, VALIDATORS_TIMEOUT | `failed` (consensus), immediately |
| FINALIZED, validators did not agree (result not AGREE or MAJORITY_AGREE) | `failed` (consensus) |
| FINALIZED + execution success | **`finalized`, the only success** |
| FINALIZED + rollback | `failed` (`rolled_back`), shows the contract's `EXPECTED:` code |
| FINALIZED + contract crash (e.g. raw TypeError) | `failed` (`contract_error`); stack trace kept in `failure.debug`, not shown |
| anything unrecognised or malformed | `failed` (`unrecognized`): fail closed |

## Verified genlayer-js 1.1.8 facts

- `client.getTransaction({hash})` returns a `GenLayerTransaction`; use it, not `waitForTransactionReceipt`.
  `waitForTransactionReceipt` returns a *simplified* receipt that renames and drops fields (for example
  `statusName` becomes `status_name`); its `fullTransaction` option exists in the code but not in the 1.1.8 types.
- On **StudioNet** the typed `txExecutionResult` / `txExecutionResultName` fields are `undefined`; the SDK fills
  them only on non-Studio chains. `resultName` is also `undefined` on Studio, so the numeric `result` is mapped.
- On StudioNet the execution outcome is in `consensus_data.leader_receipt[]`, the entry with `mode === "leader"`:
  `execution_result` is `"SUCCESS"` or `"ERROR"`; `result.status` is `"return"`, `"rollback"` or
  `"contract_error"`; `result.payload` is the contract's message (for example `EXPECTED:NOT_OWNER`) or, for a crash,
  `exit_code 1` with the traceback in `genvm_result.stderr`.
- The SDK's own types are wrong for StudioNet: `LeaderReceipt.result` is typed `string` but is an object, and
  `execution_result` is typed `string`, not an enum. Every field is therefore read as `unknown` and validated.
- `consensus_data.final` is `undefined` on StudioNet and is not used.
- Validators' receipts may show `ERROR` / `Validator execution cancelled after quorum`; these are benign and ignored.
  Only the leader's receipt decides.

## Polling

`watchTransaction` (`watch.ts`) polls `getTransaction` every 3 s, up to about 15 minutes. It waits one interval
before the first read, so SUBMITTED stays visible until the network reports the transaction (then PENDING). It
stops at once on CANCELED / UNDETERMINED / timeouts instead of polling to a retry limit, tolerates transient read
errors (5 in a row ends it with the error surfaced), and on timeout reports a failure that says the transaction
"may still complete".

## Failure messages

Rollback codes are mapped to short text (`EXPECTED:NOT_OWNER` becomes "Only the contract owner can do this.",
`EXPECTED:INVALID_TYPE:body` becomes `The value for "body" has the wrong type.`); unknown codes are shown verbatim,
truncated. Stack traces are never shown in the normal UI. This relies on the leader receipt exposing the payload,
which StudioNet does; it is not guaranteed on other chains, where the code is empty and a generic message is shown.

## Tests

`txOutcome.test.ts` and `watch.test.ts` use `__fixtures__/live-txs.json`: real `getTransaction()` results from
StudioNet, used unmodified for the success and rollback cases. Statuses that could not be captured on demand
(PENDING, ACCEPTED, CANCELED, UNDETERMINED, timeouts, non-Studio fields) are derived from a real fixture and marked
DERIVED in the tests. `live.test.ts` is an opt-in network check (`CHARTERGATE_LIVE=1`) that runs known live
transactions through the real transaction layer; it sends nothing and is skipped by default.

---

# Stage 2: evidence vault and live web provenance

Design: `docs/STAGE_2_EQUIVALENCE.md`. Data model, hash and limits: `docs/EVIDENCE_MODEL.md`. This section records what was
verified and what was learned while building it.

## Verified APIs (pinned runner v0.2.16)

Verified in the pinned SDK source (extracted by genvm-linter / genlayer-test), the official `write-contract` skill, and the
official docs and SDK reference.

| Need | API | Notes |
| --- | --- | --- |
| static / API fetch | `gl.nondet.web.get(url, headers=)` -> `Response(status, headers, body)` | the pinned SDK says `.status`; main-branch docs say `.status_code` |
| JS rendering | `gl.nondet.web.render(url, mode=, wait_after_loaded=)` -> `str` for `text`/`html`, `Image` for `screenshot` | only `text` is used |
| LLM | `gl.nondet.exec_prompt(prompt, response_format='json')` | |
| consensus | `gl.vm.run_nondet(leader_fn, validator_fn)` | validator runs in a sandbox; closures are pickled with cloudpickle, so they capture plain values only |
| failed fetch / LLM call | `gl.nondet.NondetException` | |
| hashing | `Keccak256` (exported by `genlayer`) | `hashlib` is not verified inside GenVM, so it is not used |
| time | `gl.message_raw["datetime"]` | `gl.vm.get_timestamp()` does not exist in v0.2.16 |

There are no timeout, size or redirect parameters on `web.get` or `web.render`, so the contract bounds what it
*processes* itself. Only `re` and `json` from the standard library are used (both appear in the official skill).

## What was learned

- **Floats cannot cross the GenVM calldata boundary.** A JSON float from the LLM reaches the contract as `None`. The
  contract treats that as `LLM_ERROR:NOT_AN_OBJECT` (fail closed). Integers are accepted and coerced.
- **A rule is only tested if a test fails without it.** Mutation checks on the validator showed that "the leader's quote
  must appear in the validator's own fetch" was initially untested (every fabricated-quote test was also caught by
  another rule). A test was added that only that rule can fail; with the rule removed it now fails.
- **Closures must be picklable.** The direct tests turn on `direct_vm.check_pickling` for a submission, so a closure that
  captured storage or a compiled-object problem would warn.

## Testing

- Direct tests mock `web.get`, `web.render` and `exec_prompt`; no real network is used. `direct_vm.run_validator` replays the
  real validator against changed mocks to test the equivalence rules.
- `tests/integration/test_evidence_live.py` uses real network access through GLSim, with five validators that re-fetch
  independently. Four tests run (real 404, real HTML sent as an API, protocol time and provenance, an invalid-input revert).
  Four more need **real GenVM** and are gated behind `CHARTERGATE_REAL_GENVM=1` (the StudioNet smoke cases).

### GLSim limitations found (verified against the frozen Stage 1.2 contract as a control)

1. GLSim returns an **empty schema** for this contract, so `gltest` hands back a contract object with no methods. The
   fixture binds the deployed address to the official schema from `genvm-lint` instead.
2. Deploying the same contract class **a second time in one GLSim process fails** ("class is not marked for usage within
   storage"). The frozen Stage 1.2 contract behaves identically. Start a fresh GLSim for each run.
3. GLSim has **no LLM** here (its providers need `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`) and **no browser** (no Playwright), so
   it renders with a plain HTTP GET and returns text even for an unreachable host. Real GenVM raises on a failed render.
   `VERIFIED` / `UNVERIFIABLE` records and real `web.render` therefore cannot be proven locally and are StudioNet smoke cases.

## Frontend

The Evidence Vault is in `/evidence`, `/evidence/:id` and the proposal page. It reuses the Stage 1.3 transaction layer, so
FINALIZED alone is never shown as success. `lib/evidence.ts` holds the wording ("JAVASCRIPT RENDER" is always shown for a
render), the status explanations, and a client-side URL pre-check that mirrors the contract (tested against the same
cases). `charterGate.ts` decodes `evidence_count` as optional so the UI still works against a pre-Stage-2 contract.

---

# Stage 2.1: fact binding and a claim-bound hash

Two invariants were tightened before any live deployment of Stage 2. Details: `docs/STAGE_2_EQUIVALENCE.md` (sections 4a, 5, 7, 10, 12)
and `docs/EVIDENCE_MODEL.md`.

## The problem

In Stage 2 the `fact` label was whatever the leader's LLM chose, and validators only had to agree on the **value**. A page that says
`Team: 46%` and `Community: 46%` could therefore have produced two extractions that agreed on `46%` while describing different facts.

## The fix (smallest mechanism that closes it)

1. **Fact identity is the submitted, canonicalised fact key** (`submit_evidence` gained a `fact_key` argument; the schema now has 6 parameters).
   One explicit normalisation (case, whitespace, hyphens), no aliases, no fuzzy matching, no ontology. The LLM no longer names facts.
2. **A focused binding check**: "does this exact quote state the value of this fact (and not another subject)?". It runs in the leader's pipeline,
   in every validator's own pipeline, and **a validator also runs it on the leader's quote**. A quote about the wrong subject is `UNVERIFIABLE`
   (`NOT_BOUND`) and nothing is stored.
3. **A result about any fact other than the submitted one is rejected**, by validators and again by the contract after consensus.
4. **The claim joined the canonical hash** and the format became `chartergate.evidence.v2`.

## Testing

Each rule was removed from the contract on its own (mutation testing) and the tests that fail are the ones written for it. See the Stage 2.1
report. The hash tests recompute the expected hash independently from the documented string with the SDK's keccak, pin a golden byte-for-byte
vector, and check the keccak primitive against known Ethereum test vectors. A test also recomputes every stored record's hash from the record alone.

## Things learned

- The `genlayer` package is importable in a test only after the direct harness has loaded a contract, so any test that uses the SDK directly must
  depend on a contract fixture.
- A mock-based LLM test must register an answer for **every** prompt the contract can send; the binding check is a second prompt, so the replay helper
  also answers "does the leader's quote state the fact?".
- Residual risk is documented, not hidden: the binding check is an LLM judgment (a single model error is not enough to verify, but a coordinated one
  could be), and the fact key and claim are both the submitter's words.
