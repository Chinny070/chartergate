# Stage 2: equivalence design for web evidence

Status: design, written before the implementation. Stage 2 collects and verifies **evidence**. It does not
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
  charter section relative to the proposal, and chooses the retrieval method from the source kind. The caller never
  supplies the method, the status, the fact, the value or the hash.
- **Leader:** fetches, normalises, asks the LLM for a span, applies grounding checks, returns a small structured result.
- **Validators:** independently fetch and normalise **the same URL by the same method**, run their own LLM
  extraction, and judge the leader's result against their own evidence.
- **Contract (deterministic, after consensus):** re-checks the agreed result, canonicalises the value, computes
  the hash, stamps protocol time, and stores the record.

## 4. What the leader returns

```
{
  "proposal_id":      int,   # echo of the input
  "source_url":       str,   # echo of the input
  "retrieval_method": str,   # echo of the contract's choice: GET | RENDER_TEXT
  "status":           "VERIFIED" | "UNVERIFIABLE" | "SOURCE_UNAVAILABLE" | "INVALID_SOURCE",
  "reason":           str,   # short code, e.g. SUPPORTED, NOT_SUPPORTED, HTTP_404, TOO_LARGE
  "fact":             str,   # snake_case label, <= 64 chars (empty unless something was extracted)
  "value":            str,   # <= 200 chars
  "excerpt":          str    # <= 300 chars, copied verbatim from the page
}
```

The echo fields exist so that a leader cannot silently answer for a different proposal or URL. The URL and method are
**inputs**, not leader output: the contract stores its own copy and the validator rejects any result whose echo
differs.

## 5. Deterministic checks (applied by leader AND validator, no LLM)

These make a hallucinated fact impossible to verify:

1. **Grounding.** `excerpt` must be a substring of the normalised page text (whitespace collapsed, case folded), and
   `value` must be a substring of `excerpt`. Otherwise the result is `UNVERIFIABLE`, never `VERIFIED`.
2. **Claim-number consistency.** If the claim contains numbers and none of them appears among the numbers in `value`,
   the result is `UNVERIFIABLE` (reason `VALUE_NOT_IN_CLAIM`) and the observed value is still recorded. This is
   what stops "claim 46%, source says 42%" from becoming `VERIFIED` as 46%. It is deliberately conservative: a claim
   such as "under 50%" cannot be `VERIFIED` by a value of "46%"; Stage 3 reasons about such comparisons.
3. **Shape.** Field types, enum values and lengths are validated. Malformed output never becomes an approval.

## 6. Normalisation (the same code on every node)

| Kind | Method | Normalisation |
| --- | --- | --- |
| `STATIC_WEB` | `GET` | `<script>` / `<style>` removed, tags stripped, common entities decoded, whitespace collapsed |
| `API` | `GET` | body parsed as JSON and re-serialised with sorted keys and compact separators; invalid JSON is `INVALID_SOURCE` |
| `DYNAMIC_WEB` | `RENDER_TEXT` | `web.render(url, mode='text', wait_after_loaded='1000ms')`, whitespace collapsed |

Bounds: URL 500 chars, claim 500, response body 2,000,000 bytes (larger is `INVALID_SOURCE`, reason `TOO_LARGE`),
text sent to the LLM 30,000 chars (longer text is truncated deterministically, so facts beyond that point are not
visible; this is a documented limit), at most 25 evidence records per proposal.

## 7. Validator acceptance rules

A validator runs the **same** fetch + normalise + LLM pipeline on its own and then evaluates the leader's result.
It returns `True` only if **all** of these hold:

| Rule | Detail |
| --- | --- |
| well-formed | every field present, correct type, valid enum, within length limits |
| same subject | `proposal_id`, `source_url` and `retrieval_method` equal the validator's own inputs |
| same status class | leader status equals the validator's own status |
| `VERIFIED` | (a) the leader's `excerpt` and `value` are grounded in the **validator's own** fetched text; (b) the validator's own result is also `VERIFIED`; (c) the canonical values are equal (section 8) |
| `UNVERIFIABLE` | the validator also finds the claim unsupported. A validator that finds it supported rejects |
| `SOURCE_UNAVAILABLE` | the validator also cannot reach the source (reason codes may differ: 404 vs timeout) |
| `INVALID_SOURCE` | the validator also finds the content unusable |
| leader raised `LLM_ERROR` | always reject, to force leader rotation (official guidance) |

**What does not have to agree:** the `fact` label (the LLM chooses the wording, so `team_token_allocation` and
`team_allocation` are both fine), the `excerpt` wording, the `reason` text, and everything in the page that is not
the evidence (ads, dates, footers, session data). **What must agree:** subject, status class, and the canonical value.

Rule (a) is the important one: the leader's quoted evidence is checked against a *second, independent* fetch.
A validator does not take the leader's word, and does not depend on its own LLM to catch a fabricated quote.

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

`content_hash` is `keccak256` over a canonical string built from the **agreed, normalised** result, not over the page:

```
chartergate.evidence.v1
proposal_id=<n>
source_url=<url>
source_kind=<kind>
retrieval_method=<method>
status=<status>
fact=<fact>
value=<canonical value>
section=<section id or empty>
section_revision_version=<n>
```

It is deterministic because it is computed in contract code, after consensus, from values that every node already
agreed on, with no clock and no remote data. It does **not** include the excerpt, the retrieval time, the evidence id
or the page. Therefore it is **not** a hash of the web page, not archival proof of what the page said, and two
checks that reach the same facts have the same hash. See `docs/EVIDENCE_MODEL.md`.

## 11. Residual risks (honest list)

- Validators and the leader may all see the same wrong page (for example a site that serves bad data to everyone).
  Evidence is "what GenLayer's validators independently read", not "ground truth".
- An LLM can choose the wrong span for the claim. Grounding stops fabricated quotes, not a real quote about a
  different subject; rule (b) (the validator's own extraction must reach the same canonical value) reduces this.
- Prompt injection inside a page is mitigated by delimiting page text as data and by the deterministic checks, not
  eliminated.
- Truncation at 30,000 characters can hide facts that appear later in a long page.
- Pages that serve different content to different regions or bots can cause validators to disagree. That fails the
  round and rotates the leader; it is never recorded as `VERIFIED`.
