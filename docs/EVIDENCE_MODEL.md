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
| `normalized_fact` | submitter, canonicalised by the **contract** | **which fact is being asked about**, e.g. `team_token_allocation`: a constrained key, at most 64 characters, `[a-z0-9_]` only. Always set, even when retrieval failed |
| `status` | **contract + validators** | see below |
| `status_reason` | **contract + validators** | short code, e.g. `SUPPORTED`, `HTTP_404`, `NOT_GROUNDED` |
| `normalized_value` | **contract + validators** | the value in canonical form (`46.0%` is stored as `46%`), at most 200 characters; empty unless a grounded value for **that fact** was found |
| `excerpt` | **contract + validators** | a short quote copied from the page, at most 300 characters |
| `content_hash` | **contract** | `0x` + keccak256 of the canonical evidence (below) |
| `retrieved_at`, `created_at` | **contract** | protocol transaction time (below) |
| `related_section_id` | submitter | optional charter section, `""` for none |
| `related_revision_version` | **contract** | the charter version at which that section's text in force was set |

The submitter can never supply the status, the extracted value, the quote, the hash or the time. They declare the **question** (which
proposal, which source, which claim, which fact) and the contract and validators produce the **answer**. The frontend sends exactly six
arguments: `proposal_id`, `source_url`, `source_kind`, `claim`, `fact_key`, `related_section_id`.

### Fact identity

The fact key is canonicalised by one rule only: trim, collapse whitespace, lower-case, spaces and hyphens become underscores. There are
no synonym aliases and no fuzzy matching: `team_allocation` and `team_token_allocation` are different facts. The LLM does not name facts.
Validators must agree the source states **this** fact: a figure about another subject with the same number (`Community: 46%` for a
`team_token_allocation` question) is `UNVERIFIABLE` (`NOT_BOUND`) and stores nothing. See `docs/STAGE_2_EQUIVALENCE.md`.

## Statuses

Evidence statuses are **not** constitutional verdicts. The contract has no `ELIGIBLE`, `INELIGIBLE` or
`REPAIRABLE`.

| Status | Meaning |
| --- | --- |
| `VERIFIED` | the source states a value for **this fact** that supports the claim, the quote is grounded in the fetched text and bound to the fact, and validators independently reached the same canonical value and judged the leader's quote to state the fact |
| `UNVERIFIABLE` | the source was read but does not support the claim as stated (`NOT_SUPPORTED`); the quote could not be found (`NOT_GROUNDED`, nothing stored); the quote is about a different subject than the fact (`NOT_BOUND`, nothing stored); or the source states a different value than the claim (`VALUE_NOT_IN_CLAIM`, the observed value for this fact is stored) |
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
  "chartergate.evidence.v2\n"
  "proposal_id=<n>\nsource_url=<url>\nsource_kind=<kind>\nretrieval_method=<method>\n"
  "claim=<submitted claim, whitespace collapsed>\n"
  "status=<status>\nfact=<canonical fact key>\nvalue=<canonical value>\n"
  "section=<section id or empty>\nsection_revision_version=<n>"
))
```

**What is hashed:** the proposal identity, the **submitted claim**, the **fact asked**, the source URL, kind and retrieval method, the status,
the canonical value, and the charter section and revision. So a different evaluated claim, a different fact or a different value gives a
different hash, even when the URL and the number are the same.

**What is not hashed, and why:** the **excerpt** (a quote the LLM chose; two correct, grounded quotes for the same fact and value can differ, so
including it would make equal evidence hash differently), the retrieval time and the evidence id (the same evidence checked twice has one hash),
the submitter, and the web page itself.

**Normalised before hashing:** whitespace in the claim; case, spaces and hyphens in the fact key; percent formatting in the value (`46.0%` is
`46%`). **Not normalised:** claim wording or case, URL text or case, and `0.46` versus `46%` (all different evidence).

**Why it is deterministic:** it is computed in contract code **after** consensus, from values every node already agreed on or that came from the
transaction. It uses no clock, no remote data and no LLM prose. `Keccak256` comes from the pinned SDK itself (pure Python) and matches the standard
Ethereum keccak-256 test vectors, so no unverified standard-library module is needed inside GenVM.

**What it proves:** that these normalised facts, for this proposal, claim, source and method, were what the validators agreed on. Every input is a
stored field, so anyone can recompute any record's hash from the record alone.

**What it does not prove:** it is **not** a hash of the web page and **not** archival proof of what the page said. Dynamic pages are not stable byte
for byte, and the page is not stored, so the page cannot be reconstructed from the hash. Do not describe it as "the hash of the webpage".

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
| text assessed by the evidence extraction pass | first 30,000 characters of the decoded, normalized page text (longer pages are truncated deterministically; later facts are not visible to that pass) |
| evidence per proposal | 25 |
| page size for views | 50 |

Evidence is stored as small structured records. Full pages are never stored in contract state.

### Assessment boundary and limitation

The 30,000-character cap applies **per evidence assessment**, after retrieval and text normalization and before the leader's extraction prompt. Validators independently fetch and normalize the page, then apply the same prefix cap before their own extraction and grounding checks. This is not a claim that the entire source page was assessed. A decision-critical fact after character 30,000 is outside the assessment and cannot support a `VERIFIED` record for that assessment. The current pipeline does not search later chunks or prove that the omitted tail contains no contradictory facts. Pages with important material after the boundary should be split into precise public sources/URLs or submitted as separate evidence; the UI and reviewer should treat a truncated source as incomplete context.

An adversarial direct test places a decision-critical 99% allocation after the boundary, makes the mocked extractor claim it found that fact, and asserts the tail is absent from the prompt and the result remains `UNVERIFIABLE:NOT_GROUNDED`. This proves the boundary behavior, not the truth or completeness of any live web source.

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
EvidenceRecord (@allow_storage dataclass, 17 fields; unchanged by Stage 2.1)
evidence:               TreeMap[u256, EvidenceRecord]
evidence_count:         u256
proposal_evidence_ids:  TreeMap[u256, DynArray[u256]]
```

## Methods

`submit_evidence(proposal_id, source_url, source_kind, claim, fact_key, related_section_id)` (write, proposer only) and the views
`get_evidence`, `get_evidence_count`, `get_evidence_page`, `get_proposal_evidence_count`,
`get_proposal_evidence_ids_page`, `get_proposal_evidence_page`. `get_dao_metadata` also reports `evidence_count`.

## Not in Stage 2

Proposal eligibility, constitutional review, repair, precedent, dissent, appeals, amendments, voting, execution,
screenshot or image evidence, third-party (non-proposer) evidence, and re-verification of old evidence.
