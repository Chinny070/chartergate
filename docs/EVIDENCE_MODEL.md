# Evidence model (Stage 2)

The Evidence Vault answers one question: **what evidence was checked, where did it come from, when was it
checked, and what stable facts were extracted?** It does not decide whether a proposal complies with the
charter (that is Stage 3). Its design rationale is in `docs/STAGE_2_EQUIVALENCE.md`.

## One record

| Field | Who supplies it | Meaning |
| --- | --- | --- |
| `evidence_id` | contract | 1, 2, 3 ... in submission order. A failed submission never consumes an id |
| `proposal_id` | submitter | the proposal the evidence belongs to (must exist) |
| `submitter` | contract | the caller. Only the proposal's proposer may submit |
| `source_url` | submitter | public `http(s)` URL, trimmed, at most 500 characters |
| `source_kind` | submitter | `STATIC_WEB`, `DYNAMIC_WEB` or `API` |
| `retrieval_method` | **contract** | `GET` (static and API) or `RENDER_TEXT` (dynamic). Derived from `source_kind` |
| `claim` | submitter | what the source should show, at most 500 characters |
| `status` | **contract + validators** | see below |
| `status_reason` | **contract + validators** | short code, e.g. `SUPPORTED`, `HTTP_404`, `NOT_GROUNDED` |
| `normalized_fact` | **contract + validators** | snake_case label, at most 64 characters; empty if nothing was extracted |
| `normalized_value` | **contract + validators** | the value in canonical form (`46.0%` is stored as `46%`), at most 200 characters |
| `excerpt` | **contract + validators** | a short quote copied from the page, at most 300 characters |
| `content_hash` | **contract** | `0x` + keccak256 of the canonical evidence (below) |
| `retrieved_at`, `created_at` | **contract** | protocol transaction time (below) |
| `related_section_id` | submitter | optional charter section, `""` for none |
| `related_revision_version` | **contract** | the charter version at which that section's text in force was set |

The submitter can never supply the status, fact, value, hash or time. The frontend sends exactly five
arguments: `proposal_id`, `source_url`, `source_kind`, `claim`, `related_section_id`.

## Statuses

Evidence statuses are **not** constitutional verdicts. The contract has no `ELIGIBLE`, `INELIGIBLE` or
`REPAIRABLE`.

| Status | Meaning |
| --- | --- |
| `VERIFIED` | the source states a value that supports the claim, the quote is grounded in the fetched text, and validators independently reached the same canonical value |
| `UNVERIFIABLE` | the source was read but does not support the claim as stated (`NOT_SUPPORTED`), the quote could not be found (`NOT_GROUNDED`, nothing is stored), or the source states a different value than the claim (`VALUE_NOT_IN_CLAIM`, the observed value is stored) |
| `SOURCE_UNAVAILABLE` | the validators could not reach the source (`HTTP_404`, `HTTP_500`, `FETCH_FAILED` ...) |
| `INVALID_SOURCE` | reached, but unusable: `EMPTY_BODY`, `NOT_TEXT`, `TOO_LARGE`, `INVALID_JSON`, `EMPTY_TEXT` |

A transaction that **finalizes successfully can still record a non-`VERIFIED` status**. Protocol success and
evidence status are different facts, and the UI shows both.

## Retrieval

| Source kind | Method | What the contract does |
| --- | --- | --- |
| `STATIC_WEB` | `GET` | `gl.nondet.web.get`; HTML has scripts, styles and tags removed and entities decoded |
| `API` | `GET` | `gl.nondet.web.get`; the body is parsed as JSON and re-serialised with sorted keys |
| `DYNAMIC_WEB` | `RENDER_TEXT` | `gl.nondet.web.render(url, mode='text', wait_after_loaded='1000ms')` |

`web.render` also supports `html` and `screenshot` modes. They are **not enabled** in Stage 2: the contract
rejects nothing it cannot read, and the method list is a closed table (`RETRIEVAL_METHOD_BY_KIND`), so adding a
mode later is a deliberate change. Redirects: a 3xx response is recorded as `SOURCE_UNAVAILABLE` (`HTTP_301`);
whether the node follows redirects is not documented for the pinned runner, so nothing is assumed.

## Time

`retrieved_at` and `created_at` are both `gl.message_raw["datetime"]`: the protocol time of the transaction that
recorded the evidence. They are equal in Stage 2 because retrieval happens inside that one transaction.

- It is **not** the time shown on the web page, and not the browser's clock. A page may have been published much earlier.
- Precision varies (`...19:47:10.102Z` and `...19:48:13.090065Z` both occur); the UI shows the canonical value beside a
  human-readable form.

## The hash

```
content_hash = "0x" + keccak256(utf8(
  "chartergate.evidence.v1\n"
  "proposal_id=<n>\nsource_url=<url>\nsource_kind=<kind>\nretrieval_method=<method>\n"
  "status=<status>\nfact=<fact>\nvalue=<canonical value>\n"
  "section=<section id or empty>\nsection_revision_version=<n>"
))
```

**What is hashed:** the agreed, normalised evidence and its provenance identifiers.

**What is not hashed:** the web page, the rendered text, the excerpt, the retrieval time, the evidence id, the claim,
or the submitter.

**Why it is deterministic:** it is computed in contract code **after** consensus, from values every node already
agreed on. It uses no clock, no remote data and no LLM prose. `Keccak256` comes from the pinned SDK itself
(pure Python), so no unverified standard-library module is needed inside GenVM.

**What it proves:** that these exact normalised facts, for this proposal, source and method, were what the validators
agreed on. Two checks that reach the same facts have the same hash; changing the value, status, source, method or
charter relationship changes it.

**What it does not prove:** it is **not** a hash of the web page and **not** archival proof of what the page said.
Dynamic pages are not stable byte for byte, and the page is not stored, so the page cannot be reconstructed from
the hash. Do not describe it as "the hash of the webpage".

## Charter relationship is historical

A proposal is bound to `charter_version_at_submission`. When evidence names a charter section, the section is looked up
**at that version**, not in the latest charter:

- a section created after the proposal was submitted is rejected (`SECTION_NOT_IN_PROPOSAL_CHARTER`);
- a section that was deactivated before submission is rejected (`SECTION_INACTIVE_AT_SUBMISSION`);
- a section deactivated *after* submission is fine;
- `related_revision_version` records which revision's text was in force, so
  `get_charter_section_at_version(section, related_revision_version)` returns the exact rule text.

## Limits

| Item | Limit |
| --- | --- |
| URL | 500 characters, public `http(s)` host (see below) |
| claim | 500 |
| fact / value / excerpt / reason | 64 / 200 / 300 / 64 |
| fetched body | 2,000,000 bytes (larger is `INVALID_SOURCE`, `TOO_LARGE`) |
| text sent to the LLM | 30,000 characters (longer pages are truncated deterministically; later facts are not visible) |
| evidence per proposal | 25 |
| page size for views | 50 |

Evidence is stored as small structured records. Full pages are never stored in contract state.

## URL screening (best effort)

The contract rejects before any web access: empty, over-long, non-printable or non-ASCII characters, spaces,
backslashes, schemes other than `http`/`https`, credentials in the URL, IP-literal hosts, IPv4 and numeric hosts, hosts
without an alphabetic top-level domain (for example `localhost`), the suffixes `.localhost`, `.local`, `.internal`,
`.lan`, `.home`, `.corp`, `.intranet`, and invalid ports. This is syntactic screening only. GenVM's own web module
applies its own scheme, port and TLD checks on the node; this contract makes **no** claim about network-level SSRF safety
(a public name can resolve anywhere).

## Immutability

There is no method that edits, deletes, replaces or re-verifies a record. New evidence is a new record. Submitting
evidence never changes the proposal, the charter or any earlier record.

## Storage

```
EvidenceRecord (@allow_storage dataclass, 17 fields)
evidence:               TreeMap[u256, EvidenceRecord]
evidence_count:         u256
proposal_evidence_ids:  TreeMap[u256, DynArray[u256]]
```

## Methods

`submit_evidence(proposal_id, source_url, source_kind, claim, related_section_id)` (write, proposer only) and the views
`get_evidence`, `get_evidence_count`, `get_evidence_page`, `get_proposal_evidence_count`,
`get_proposal_evidence_ids_page`, `get_proposal_evidence_page`. `get_dao_metadata` also reports `evidence_count`.

## Not in Stage 2

Proposal eligibility, constitutional review, repair, precedent, dissent, appeals, amendments, voting, execution,
screenshot or image evidence, third-party (non-proposer) evidence, and re-verification of old evidence.
