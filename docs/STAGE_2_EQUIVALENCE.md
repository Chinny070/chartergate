# Stage 2: equivalence design for web evidence

Status: design (Stage 2), tightened in Stage 2.1 (fact binding and claim-bound hash). Stage 2 collects and verifies **evidence**. It does not
judge proposals (that is Stage 3).

## 1. What is non-deterministic, and why strict equality is wrong

Leader and validators each fetch the source themselves. Their responses can differ in ads, session ids, footers,
"last updated" dates, live counters and markup. If an LLM reads the page, its prose also differs between runs.
So **no raw page, no rendered HTML and no LLM prose is ever compared**, and `strict_eq` is not used anywhere.

The design separates three layers:

```
raw source response            (not compared, not stored)
        |  deterministic normalisation (same code on every node)
        v
normalised page text           (not compared, not stored; bounded to 30,000 chars)
        |  LLM picks a span  +  deterministic grounding checks
        v
structured evidence            {status, fact, value, excerpt}   <- the ONLY thing that is agreed on and stored
                               (`fact` is the submitted fact key, not an LLM label)
```

## 2. Verified GenLayer APIs this design uses (pinned runner v0.2.16)

Verified in the pinned SDK source (`genlayer` package extracted by genvm-linter / genlayer-test), the official
`write-contract` skill, and the official docs.

| Need | API | Notes |
| --- | --- | --- |
| static / API fetch | `gl.nondet.web.get(url, headers=...)` -> `Response(status: int, headers: dict[str, bytes], body: bytes or None)` | the pinned SDK uses `.status` (main-branch docs say `.status_code`) |
| JS rendering | `gl.nondet.web.render(url, mode='text'\|'html'\|'screenshot', wait_after_loaded='1000ms')` -> `str` (text, html) or `Image` | `text` is used. `html` and `screenshot` exist but are **not enabled** in Stage 2 |
| LLM | `gl.nondet.exec_prompt(prompt, response_format='json')` -> `dict` | |
| leader / validator | `gl.vm.run_nondet(leader_fn, validator_fn)` | `validator_fn(leaders_result) -> bool` runs in a sandbox. `Return` / `UserError` / `VMError` are the result types |
| errors | `gl.vm.UserError(message)`; `gl.nondet.NondetException` for failed fetch/LLM calls | |
| hashing | `Keccak256` (exported by `genlayer`; `.update(bytes)`, `.digest()`, `.hexdigest()`) | pure Python in the SDK. Stdlib `hashlib` is not verified inside GenVM, so it is not used |
| time | `gl.message_raw["datetime"]` | transaction datetime. `gl.vm.get_timestamp()` does not exist in v0.2.16 |

Not verifiable from docs or the SDK: request timeouts, maximum response size and redirect behaviour. `web.get`
and `web.render` expose **no** timeout or size parameters in v0.2.16. The official validator docs say GenVM's web
module itself validates URLs for scheme, port and TLD (`web.check_url`, `allowed_tld`), and that is the only
documented restriction. This design therefore enforces its own bounds on what it *processes* (section 6) and makes no
claim about network-level SSRF safety.

## 3. Roles

- **Contract (deterministic, before the nondet block):** validates every input, authorises the caller, resolves the
  charter section relative to the proposal, chooses the retrieval method from the source kind, and **canonicalises the
  fact key** (section 4a). The caller never supplies the method, the extracted value, the status, the hash or a time.
- **Leader:** fetches, normalises, asks the LLM for a span **for the asked fact**, checks that the quote is grounded, asks the LLM
  whether that quote really states that fact, and returns a small structured result.
- **Validators:** independently fetch and normalise **the same URL by the same method**, run the whole leader pipeline themselves, and
  additionally judge **the leader's own quote** against the fact.
- **Contract (deterministic, after consensus):** re-checks the agreed result, canonicalises the value, computes the hash,
  stamps protocol time, and stores the record.

## 4. What the leader returns

```
{
  "proposal_id":      int,   # echo of the input
  "source_url":       str,   # echo of the input
  "retrieval_method": str,   # echo of the contract's choice: GET | RENDER_TEXT
  "status":           "VERIFIED" | "UNVERIFIABLE" | "SOURCE_UNAVAILABLE" | "INVALID_SOURCE",
  "reason":           str,   # short code, e.g. SUPPORTED, NOT_SUPPORTED, NOT_GROUNDED, NOT_BOUND, HTTP_404, TOO_LARGE
  "fact":             str,   # ALWAYS the submitted, canonical fact key (e.g. team_token_allocation)
  "value":            str,   # <= 200 chars; empty unless something grounded and bound was found
  "excerpt":          str    # <= 300 chars, copied verbatim from the page; empty unless found
}
```

The echo fields exist so a leader cannot silently answer for a different proposal, URL or fact. The URL, method and fact are
**inputs**, not leader output: the contract holds its own copy and a result whose echo differs is rejected, by every validator and
again by the contract after consensus.

### 4a. Fact identity

A "fact" is **which question about the source is being asked**, for example `team_token_allocation`. It is declared by the submitter,
exactly like the claim, and it is **not** an answer: the value, the quote, the status and the hash are still produced by the contract
and agreed by validators.

The contract canonicalises the key with one explicit rule, and nothing else: trim, collapse whitespace, lower-case, and turn spaces and
hyphens into underscores. The result must match `[a-z0-9_]{1,64}` and contain at least one letter or digit.

| Submitted | Stored |
| --- | --- |
| `team_token_allocation`, `Team Token-Allocation`, `  TEAM_TOKEN_ALLOCATION ` | `team_token_allocation` |
| `team_allocation` | `team_allocation` (a **different** fact) |
| `team.token.allocation`, `team/allocation`, `___` | rejected |

There are **no synonym aliases and no fuzzy matching**: `team_allocation`, `team_tokens` and `team_token_allocation` are three different
facts. This was chosen over three alternatives. (1) A free LLM-chosen label made two validators able to agree on a number while meaning
different facts. (2) A closed vocabulary is the "enormous ontology" we explicitly avoid. (3) Asking an LLM whether two labels mean the same
makes the identity of a fact itself a fuzzy judgment. A submitter-declared key makes identity deterministic, and the semantic question that
is left (does *this quote* state *this fact*?) is asked directly, about a concrete quote.

Because the LLM no longer names facts, any `fact` label it volunteers is ignored.

## 5. Checks applied by the leader AND by every validator's own pipeline

These make a hallucinated or mis-attributed fact impossible to verify:

1. **Grounding (deterministic).** `excerpt` must be a substring of the normalised page text (whitespace collapsed, case folded), and `value` must
   be a substring of `excerpt`. Otherwise the result is `UNVERIFIABLE` (`NOT_GROUNDED`, or `NOT_SUPPORTED` if the LLM itself said unsupported), and
   nothing is stored.
2. **Binding (LLM, focused).** For a grounded quote, a second, separate prompt asks only: *does this exact quote state that the value of THIS fact
   is VALUE?* It states that a quote about a different subject (for example "community" when the fact is about the "team") does not count,
   even if the number is the same. If the answer is no, the result is `UNVERIFIABLE` (`NOT_BOUND`, or `NOT_SUPPORTED`) and **nothing is stored**,
   so a figure about the wrong subject can never be recorded as evidence for this fact.
3. **Claim-number consistency (deterministic).** If the claim contains numbers and none of them appears among the numbers in `value`, the result
   is `UNVERIFIABLE` (`VALUE_NOT_IN_CLAIM`) and the observed (grounded, bound) value is still recorded. This stops "claim 46%, source says 42%"
   from becoming `VERIFIED` as 46%. It is conservative: "under 50%" cannot be `VERIFIED` by "46%"; Stage 3 reasons about comparisons.
4. **Shape (deterministic).** Field types, enum values and lengths are validated. Malformed output never becomes an approval.

Order: grounding, then binding, then the number guard. The cheap deterministic check always runs first, so an ungrounded quote never costs an
LLM call.

## 6. Normalisation (the same code on every node)

| Kind | Method | Normalisation |
| --- | --- | --- |
| `STATIC_WEB` | `GET` | `<script>` / `<style>` removed, tags stripped, common entities decoded, whitespace collapsed |
| `API` | `GET` | body parsed as JSON and re-serialised with sorted keys and compact separators; invalid JSON is `INVALID_SOURCE` |
| `DYNAMIC_WEB` | `RENDER_TEXT` | `web.render(url, mode='text', wait_after_loaded='1000ms')`, whitespace collapsed |

Bounds: URL 500 chars, claim 500, response body 2,000,000 bytes (larger is `INVALID_SOURCE`, reason `TOO_LARGE`),
and at most 25 evidence records per proposal. For each source, an extraction pass sees only the first 30,000
characters of decoded and normalized page text. Validators apply the same prefix limit. Text after that boundary
does not support or contradict the extracted facts in that assessment; the pipeline does not scan the remaining
text or prove that the assessed prefix contains the whole page. Treat a source exceeding the limit as incomplete
for decision-critical facts and provide a precise URL or separate evidence for material content beyond the prefix.

## 7. Validator acceptance rules

A validator runs the **same** fetch, normalise, extract and bind pipeline on its own, and then evaluates the leader's result. It returns `True`
only if **all** of these hold:

| Rule | Detail |
| --- | --- |
| well-formed | every field present, correct type, valid enum, within length limits, and no extra fields |
| same subject | `proposal_id`, `source_url` and `retrieval_method` equal the validator's own inputs |
| **same fact** | the result's `fact` equals the submitted canonical fact key exactly (a result about any other fact is rejected) |
| same status class | leader status equals the validator's own status |
| `VERIFIED` (a) | the leader's `excerpt` and `value` are grounded in the **validator's own** fetched text |
| `VERIFIED` (b) | the validator's own pipeline is also `VERIFIED`, which includes the validator's own binding check on **its own** quote |
| `VERIFIED` (c) | the canonical values are equal (section 8) |
| `VERIFIED` (d) | **the validator's own binding check on the LEADER's quote says it states the fact** |
| `UNVERIFIABLE` | the validator also finds the claim unsupported. A validator that finds it supported rejects |
| `SOURCE_UNAVAILABLE` | the validator also cannot reach the source (reason codes may differ: 404 vs timeout) |
| `INVALID_SOURCE` | the validator also finds the content unusable |
| leader raised `LLM_ERROR` | always reject, to force leader rotation (official guidance) |
| the validator's own LLM output is unusable | reject (vote no) rather than crash |

**What must agree:** subject (proposal, URL, method), **fact identity**, status class, the canonical value, and that the quote really states
that fact. **What does not have to agree:** the wording or length of the quote, the `reason` text, and everything on the page that is not the
evidence (ads, dates, footers, session data).

Why both (b) and (d)? Rule (b) catches a validator whose own reading lands on the wrong subject. Rule (d) catches a leader whose quote is
about the wrong subject while the validator's own reading is fine. Without (d), a leader could quote "Community: 46%" for a *team* question and
be accepted by a validator that independently found "Team: 46%", because the numbers match. Rule (a) separately prevents a leader from inventing
a quote that is not on the page.

Worked example (page lists `Team: 46%` and `Community: 46%`; fact `team_token_allocation`):

| Leader's quote | Validator's own reading | Result |
| --- | --- | --- |
| `Team: 46%` | `Team: 46%` | accept |
| `Community: 46%` | `Team: 46%` | reject: the validator judges the leader's quote does not state the team fact (rule d) |
| `Team: 46%` | `Community: 46%` | reject: the validator's own binding on its own quote fails, so it is `UNVERIFIABLE` and the statuses differ (rule b) |
| a result whose `fact` is `community_token_allocation` | any | reject: not the submitted fact |

## 8. Value equivalence (explicit, narrow)

Values are compared after canonicalisation, which is intentionally minimal:

- trim, collapse whitespace, case fold, remove thousands separators inside numbers (`1,000` -> `1000`);
- a number with a percent sign has trailing zeros after the decimal point removed (`46.0%` and `46.00%` -> `46%`);
- everything else is compared as text.

So `46%` is equivalent to `46.0%`. It is **not** equivalent to `0.46` (that would silently change meaning), and not to
`42%`. Anything not covered by these rules must match exactly after trimming.

## 9. Failure classification

| Condition | Result | Why |
| --- | --- | --- |
| bad type, bad URL, unknown kind, blank claim, unknown proposal, not the proposer, bad section, cap reached | revert `EXPECTED:...` | caller error; no id consumed |
| HTTP 4xx / 5xx, network failure, `NondetException` on fetch | record `SOURCE_UNAVAILABLE` (reason `HTTP_404`, `HTTP_5XX`, `FETCH_FAILED`) | a durable statement that the source could not be read; validators must independently also fail to read it |
| non-text content, empty text, invalid JSON for `API`, too large | record `INVALID_SOURCE` | fetched but unusable |
| LLM output missing, malformed, wrong types after sanitising | revert `LLM_ERROR:...` | not a statement about the source; validators always disagree so the leader rotates |
| source read, claim not supported, contradicted, or not grounded | record `UNVERIFIABLE` | observed value is still recorded when grounded |
| source supports the claim and grounding passes | record `VERIFIED` | |

A transaction that finalizes successfully can still record a non-`VERIFIED` evidence status; **protocol success
and evidence status are different things.** The UI shows both.

## 10. The hash

`content_hash` is `keccak256` (Ethereum's, verified against known test vectors) over a canonical string built from the **agreed, normalised**
result and the question that was asked, not over the page:

```
chartergate.evidence.v2
proposal_id=<n>
source_url=<url>
source_kind=<kind>
retrieval_method=<method>
claim=<the submitted claim, whitespace collapsed>
status=<status>
fact=<canonical fact key>
value=<canonical value>
section=<section id or empty>
section_revision_version=<n>
```

It is deterministic because it is computed in contract code, after consensus, from values every node already agreed on or that came from the
transaction itself, with no clock and no remote data. The format is versioned (`v2` adds the claim; `v1` was never deployed).

**Included, and why.** The proposal identity, the submitted claim and the fact asked, so that *different evaluated question, different hash* even if
the URL and the number happen to be identical; the source URL, kind and retrieval method, so the provenance is part of the identity; the status and the
canonical value; and the charter section and the revision in force, so the rule the evidence relates to is part of the identity.

**Excluded, and why.** The excerpt: it is a quote the LLM chose, and two correct, grounded quotes for the same fact and value may legitimately differ, so
including it would make equal evidence hash differently. The retrieval time and the evidence id: the same evidence checked twice has the same hash. The
submitter. The page itself.

**Normalised before hashing (explicit):** whitespace in the claim, case/space/hyphen in the fact key, and percent formatting in the value (`46.0%` is `46%`).
**Not normalised:** claim wording or case, URL text or case, and `0.46` versus `46%`; those are different evidence.

It is **not** a hash of the web page and **not** archival proof of what the page said: the page is not stored, so it cannot be reconstructed from the hash, and
dynamic pages are not stable byte for byte anyway. It proves only that these normalised facts, for this proposal, claim, source and method, are what the
validators agreed they read. Every input is a stored field, so any record's hash can be recomputed from the record alone (a test does exactly that).

## 11. Residual risks (honest list)

- Validators and the leader may all see the same wrong page (for example a site that serves bad data to everyone). Evidence is "what GenLayer's
  validators independently read", not "ground truth".
- **The binding check is an LLM judgment.** It is a focused question about a concrete quote, run independently by every validator, and it is checked
  against a deterministic grounding check, but a mistaken model could still say a wrong-subject quote states the fact. The design makes a single
  error insufficient (the leader's pipeline, the validator's pipeline and the validator's judgment of the leader's quote must all go the same way),
  not impossible.
- **The fact key and the claim are both the submitter's words.** The contract stores and hashes both, so a reader can see the pairing, but it does not
  verify that the claim is about the declared fact. A submitter who declares a misleading pairing only mislabels their own evidence.
- A page that is ambiguous in a way a human could not resolve will fail to reach `VERIFIED` (or fail consensus) rather than guess.
- Prompt injection inside a page is mitigated by delimiting page text as data and by the deterministic checks, not eliminated.
- The 30,000-character per-source prefix can omit decision-critical support or contradictions later in a page.
  The pipeline does not inspect the remainder, so a successful assessment applies only to the visible prefix.
- Pages that serve different content to different regions or bots can cause validators to disagree. That fails the round and rotates the
  leader; it is never recorded as `VERIFIED`.

## 12. What changed in Stage 2.1

1. Fact identity became the submitted, canonicalised fact key (4a). Before, it was a free LLM label that validators did not have to agree on.
2. A semantic binding check was added: in every pipeline, and by each validator on the leader's quote (sections 5 and 7).
3. The claim entered the canonical hash and the hash format moved to `v2` (section 10).
4. The record's `normalized_fact` now always holds the fact that was asked, including when retrieval failed, so the hash is recomputable from the
   stored record. `normalized_value` and `excerpt` stay empty unless something grounded and bound was found.


## 13. Live verification notes (Stage 2.2)

- **Leader rotation.** On the StudioNet verification deployment, 2 of 8 earlier live LLM submissions required leader rotation: the
  `STATIC_WEB` live test took 2 rounds and the `DYNAMIC_WEB` render test took 3. No root cause is confirmed (`debugTraceTransaction`
  is unavailable on StudioNet), and no `LLM_ERROR` was observed. The consensus and equivalence rules were not changed or weakened.
  This is an operational observation about liveness, not a blocker.
- **Loopback URL.** `http://localhost/admin` was rejected by CharterGate's own `_validate_source_url` with
  `EXPECTED:SOURCE_URL_HOST_NOT_PUBLIC` (leader and validator both rolled back, no nondeterministic block ran). No evidence id was
  consumed and no record was created. This is a syntactic screen only; it makes no claim about network-level SSRF protection, which
  belongs to GenVM's web layer and is not verified here.
- **Browser E2E.** Evidence #9 and #10 were submitted from the browser wallet. #9 exposed a frontend bug (the transaction result was
  unmounted by the list reload); #10 verified the fixed flow end to end.
