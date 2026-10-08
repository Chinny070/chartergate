"""Evidence Vault: records, provenance, statuses, hashing, immutability. Web and LLM are mocked."""

import json
import warnings

import pytest

from conftest import hex_of
from evidence_support import (
    CLAIM_NUMBERED,
    CLAIM_PLAIN,
    T_EVIDENCE,
    URL,
    URL_PATTERN,
    atlas,  # noqa: F401  (fixture)
    mock_answer,
    mock_page,
    page,
    reset,
    snapshot,
    submit,
    web,  # noqa: F401  (fixture)
)


def only_record(c):
    assert c.get_evidence_count() == 1
    return c.get_evidence(1)


# ---- the acceptance scenario -------------------------------------------------


def test_acceptance_verified_static_evidence_for_a_proposal_under_charter_v4(atlas, web, direct_alice):
    assert atlas.get_proposal(1)["charter_version_at_submission"] == 4
    submit(atlas, claim=CLAIM_PLAIN, related_section_id="2")

    r = only_record(atlas)
    assert r["evidence_id"] == 1 and r["proposal_id"] == 1
    assert r["submitter"].lower() == hex_of(direct_alice)
    assert r["source_url"] == URL
    assert r["source_kind"] == "STATIC_WEB"
    assert r["retrieval_method"] == "GET"
    assert r["claim"] == CLAIM_PLAIN
    assert r["status"] == "VERIFIED" and r["status_reason"] == "SUPPORTED"
    assert (r["normalized_fact"], r["normalized_value"]) == ("team_token_allocation", "46%")
    assert r["excerpt"] == "Team: 46%"
    assert r["related_section_id"] == "2"
    assert r["related_revision_version"] == 3  # section 2 as it read when proposal 1 (charter v4) was submitted
    assert r["content_hash"].startswith("0x") and len(r["content_hash"]) == 66
    assert r["retrieved_at"] == r["created_at"]
    assert r["retrieved_at"].startswith("2026-10-08T21:30:00")


def test_negative_case_claim_46_but_source_says_42_is_never_verified_as_46(atlas, direct_vm):
    mock_page(direct_vm, page(team="42%"))
    mock_answer(direct_vm, supported=False, value="42%", excerpt="Team: 42%")
    submit(atlas, claim=CLAIM_NUMBERED)
    r = only_record(atlas)
    assert r["status"] == "UNVERIFIABLE"
    assert r["normalized_value"] == "42%"  # what the source actually says is preserved
    assert r["normalized_value"] != "46%"


def test_negative_case_even_if_the_llm_wrongly_says_supported(atlas, direct_vm):
    """The deterministic claim-number guard stops 'claim 46%, source 42%' without trusting the LLM."""
    mock_page(direct_vm, page(team="42%"))
    mock_answer(direct_vm, supported=True, value="42%", excerpt="Team: 42%")
    submit(atlas, claim=CLAIM_NUMBERED)
    r = only_record(atlas)
    assert r["status"] == "UNVERIFIABLE"
    assert r["status_reason"] == "VALUE_NOT_IN_CLAIM"
    assert r["normalized_value"] == "42%"


# ---- retrieval methods: GET vs render ----------------------------------------


def test_dynamic_web_uses_render_text(atlas, web):
    submit(atlas, source_kind="DYNAMIC_WEB")
    r = only_record(atlas)
    assert r["retrieval_method"] == "RENDER_TEXT"
    assert r["source_kind"] == "DYNAMIC_WEB"
    assert r["status"] == "VERIFIED"


def test_render_is_really_called_for_dynamic_and_get_for_static(atlas, web, monkeypatch):
    from genlayer import gl

    calls = []
    real_get, real_render = gl.nondet.web.get, gl.nondet.web.render
    monkeypatch.setattr(gl.nondet.web, "get", lambda *a, **k: (calls.append("get"), real_get(*a, **k))[1])
    monkeypatch.setattr(gl.nondet.web, "render", lambda *a, **k: (calls.append(("render", k.get("mode"))), real_render(*a, **k))[1])
    submit(atlas, source_kind="STATIC_WEB")
    submit(atlas, source_kind="API")
    submit(atlas, source_kind="DYNAMIC_WEB")
    assert calls == ["get", "get", ("render", "text")]


def test_api_source_is_canonicalised_json(atlas, direct_vm):
    mock_page(direct_vm, body=json.dumps({"b": 1, "allocations": {"team": "46%", "community": "30%"}}, indent=4))
    mock_answer(direct_vm, value="46%", excerpt='"team":"46%"')
    submit(atlas, source_kind="API")
    r = only_record(atlas)
    assert r["status"] == "VERIFIED"
    assert r["retrieval_method"] == "GET" and r["source_kind"] == "API"


def test_page_noise_is_ignored_when_extracting_text(atlas, direct_vm):
    seen = []
    mock_page(direct_vm, page(footer="visit our sponsor &amp; win"))
    direct_vm.mock_llm(r"CLAIM TO CHECK", json.dumps({"supported": True, "fact": "team_token_allocation", "value": "46%", "excerpt": "Team: 46%"}))
    from genlayer import gl

    original = gl.nondet.exec_prompt

    def spy(prompt, **kw):
        seen.append(prompt)
        return original(prompt, **kw)

    import pytest as _p  # noqa: F401

    gl.nondet.exec_prompt = spy
    try:
        submit(atlas)
    finally:
        gl.nondet.exec_prompt = original
    prompt = seen[0]
    assert "var session" not in prompt and "color:red" not in prompt  # script/style removed
    assert "<li>" not in prompt  # tags stripped
    assert "visit our sponsor & win" in prompt  # entities decoded


# ---- non-VERIFIED outcomes are recorded honestly -----------------------------


@pytest.mark.parametrize("status,reason", [(404, "HTTP_404"), (500, "HTTP_500"), (503, "HTTP_503"), (301, "HTTP_301")])
def test_http_errors_record_source_unavailable_never_verified(atlas, direct_vm, status, reason):
    mock_page(direct_vm, status=status, body="")
    mock_answer(direct_vm)
    submit(atlas)
    r = only_record(atlas)
    assert r["status"] == "SOURCE_UNAVAILABLE" and r["status_reason"] == reason
    assert (r["normalized_fact"], r["normalized_value"], r["excerpt"]) == ("", "", "")


def test_fetch_exception_records_source_unavailable(atlas, direct_vm, monkeypatch):
    from genlayer import gl

    def boom(*a, **k):
        raise gl.nondet.NondetException("timeout")

    monkeypatch.setattr(gl.nondet.web, "get", boom)
    submit(atlas)
    r = only_record(atlas)
    assert (r["status"], r["status_reason"]) == ("SOURCE_UNAVAILABLE", "FETCH_FAILED")


def test_render_exception_records_source_unavailable(atlas, direct_vm, monkeypatch):
    from genlayer import gl

    def boom(*a, **k):
        raise gl.nondet.NondetException("render timeout")

    monkeypatch.setattr(gl.nondet.web, "render", boom)
    submit(atlas, source_kind="DYNAMIC_WEB")
    r = only_record(atlas)
    assert (r["status"], r["status_reason"]) == ("SOURCE_UNAVAILABLE", "FETCH_FAILED")


@pytest.mark.parametrize(
    "kind,body,reason",
    [
        ("STATIC_WEB", "", "EMPTY_BODY"),
        ("STATIC_WEB", b"\xff\xfe\x00binary", "NOT_TEXT"),
        ("STATIC_WEB", "<html><script>x()</script><style>a{}</style></html>", "EMPTY_TEXT"),
        ("API", "{not json", "INVALID_JSON"),
        ("API", "<html>an HTML error page</html>", "INVALID_JSON"),
        ("STATIC_WEB", "x" * 2_000_001, "TOO_LARGE"),
    ],
    ids=["empty_body", "binary", "only_script_and_style", "bad_json", "html_for_api", "too_large"],
)
def test_unusable_content_records_invalid_source(atlas, direct_vm, kind, body, reason):
    mock_page(direct_vm, body=body)
    mock_answer(direct_vm)
    submit(atlas, source_kind=kind)
    r = only_record(atlas)
    assert (r["status"], r["status_reason"]) == ("INVALID_SOURCE", reason)
    assert r["normalized_value"] == ""


def test_llm_is_not_called_when_the_source_is_unusable(atlas, direct_vm):
    mock_page(direct_vm, status=404, body="")
    # no LLM mock registered: an LLM call would raise MockNotFoundError and fail the test
    submit(atlas)
    assert only_record(atlas)["status"] == "SOURCE_UNAVAILABLE"


def test_hallucinated_excerpt_is_never_verified(atlas, direct_vm):
    mock_page(direct_vm, page())
    mock_answer(direct_vm, supported=True, value="46%", excerpt="Team members hold 46% of all tokens")
    submit(atlas)
    r = only_record(atlas)
    assert (r["status"], r["status_reason"]) == ("UNVERIFIABLE", "NOT_GROUNDED")
    assert (r["normalized_fact"], r["normalized_value"], r["excerpt"]) == ("", "", "")  # nothing ungrounded is stored


def test_value_not_inside_its_own_excerpt_is_not_grounded(atlas, direct_vm):
    mock_page(direct_vm, page())
    mock_answer(direct_vm, supported=True, value="99%", excerpt="Team: 46%")
    submit(atlas, claim=CLAIM_PLAIN)
    assert only_record(atlas)["status_reason"] == "NOT_GROUNDED"


def test_source_that_does_not_mention_the_claim_is_unverifiable(atlas, direct_vm):
    mock_page(direct_vm, page())
    mock_answer(direct_vm, supported=False, fact="", value="", excerpt="")
    submit(atlas, claim=CLAIM_PLAIN)
    r = only_record(atlas)
    assert (r["status"], r["status_reason"]) == ("UNVERIFIABLE", "NOT_SUPPORTED")
    assert (r["normalized_fact"], r["normalized_value"]) == ("", "")


def test_failed_retrieval_never_stores_a_verified_result(atlas, direct_vm):
    for status in (404, 500):
        reset(direct_vm)
        mock_page(direct_vm, status=status, body="")
        mock_answer(direct_vm)
        submit(atlas)
    assert all(e["status"] != "VERIFIED" for e in atlas.get_evidence_page(0, 50))


# ---- LLM output handling (fails closed) --------------------------------------


@pytest.mark.parametrize(
    "raw,code",
    [
        ("not json at all", "MALFORMED_JSON"),
        ("{broken json", "MALFORMED_JSON"),
        ("[1, 2, 3]", "NOT_AN_OBJECT"),
        ({"fact": "x", "value": "1", "excerpt": "e"}, "BAD_SUPPORTED"),
        ({"supported": "maybe", "fact": "x", "value": "1", "excerpt": "e"}, "BAD_SUPPORTED"),
        ({"supported": 1, "fact": "x", "value": "1", "excerpt": "e"}, "BAD_SUPPORTED"),
        ({"supported": True, "fact": ["a"], "value": "1", "excerpt": "e"}, "BAD_FACT"),
        ({"supported": True, "fact": "Not A Valid/Key!", "value": "1", "excerpt": "e"}, "BAD_FACT"),
        ({"supported": True, "fact": "ok_key", "value": {"x": 1}, "excerpt": "e"}, "BAD_VALUE"),
        ({"supported": True, "fact": "ok_key", "value": "v" * 201, "excerpt": "e"}, "BAD_VALUE"),
        # GenVM calldata cannot represent floats, so the node hands the contract None: fail closed.
        ({"supported": True, "fact": "ok_key", "value": "1", "excerpt": 5.5}, "NOT_AN_OBJECT"),
        ({"supported": True, "fact": "ok_key", "value": "1", "excerpt": 5}, None),  # int is coerced to text, then fails grounding
    ],
    ids=["prose", "broken_json", "json_array", "missing_supported", "supported_maybe", "supported_int", "fact_list",
         "fact_bad_chars", "value_object", "value_too_long", "excerpt_float", "excerpt_int"],
)
def test_malformed_llm_output_fails_closed(atlas, direct_vm, raw, code):
    mock_page(direct_vm, page())
    mock_answer(direct_vm, raw=raw if isinstance(raw, str) else json.dumps(raw))
    if code is None:
        submit(atlas)
        assert only_record(atlas)["status"] != "VERIFIED"
        return
    with direct_vm.expect_revert(f"LLM_ERROR:{code}"):
        submit(atlas)
    assert atlas.get_evidence_count() == 0  # no record, no id consumed


def test_llm_call_failure_reverts_with_llm_error(atlas, direct_vm, monkeypatch):
    from genlayer import gl

    mock_page(direct_vm, page())

    def boom(*a, **k):
        raise gl.nondet.NondetException("provider down")

    monkeypatch.setattr(gl.nondet, "exec_prompt", boom)
    with direct_vm.expect_revert("LLM_ERROR:CALL_FAILED"):
        submit(atlas)
    assert atlas.get_evidence_count() == 0


def test_documented_aliases_and_wrapped_json_are_accepted(atlas, direct_vm):
    mock_page(direct_vm, page())
    wrapped = 'Sure! Here you go: {"is_supported": "TRUE", "fact_name": "Team Token-Allocation", "extracted_value": 46, "quote": "Team: 46%"} Hope that helps.'
    mock_answer(direct_vm, raw=wrapped)
    submit(atlas, claim=CLAIM_PLAIN)
    r = only_record(atlas)
    assert r["status"] == "VERIFIED"
    assert r["normalized_fact"] == "team_token_allocation"  # lower-cased, spaces and hyphens become underscores
    assert r["normalized_value"] == "46"


def test_long_excerpt_is_truncated_and_a_truncated_quote_can_still_be_grounded(atlas, direct_vm):
    long_page = page(extra="<p>" + ("Team: 46% of the supply is held by the team. " * 20) + "</p>")
    mock_page(direct_vm, long_page)
    quote = "Team: 46% of the supply is held by the team. " * 20
    mock_answer(direct_vm, value="46%", excerpt=quote.strip())
    submit(atlas)
    r = only_record(atlas)
    assert len(r["excerpt"]) <= 300


# ---- canonical value and hash ------------------------------------------------


def test_percent_values_are_canonicalised_but_other_formats_are_not(atlas, direct_vm):
    for value, expected in [("46.0%", "46%"), ("46.00%", "46%"), ("46 %", "46%"), ("1,000", "1000"), ("0.46", "0.46"), ("Forty-Six", "forty-six")]:
        reset(direct_vm)
        mock_page(direct_vm, page(team=value))
        mock_answer(direct_vm, value=value, excerpt=f"Team: {value}")
        submit(atlas, claim=CLAIM_PLAIN)
    values = [e["normalized_value"] for e in atlas.get_evidence_page(0, 50)]
    assert values == ["46%", "46%", "46%", "1000", "0.46", "forty-six"]


def test_hash_matches_the_documented_canonical_form(atlas, web):
    from genlayer.py.keccak import Keccak256

    submit(atlas, related_section_id="2")
    r = only_record(atlas)
    canonical = "\n".join(
        [
            "chartergate.evidence.v1",
            "proposal_id=1",
            f"source_url={URL}",
            "source_kind=STATIC_WEB",
            "retrieval_method=GET",
            "status=VERIFIED",
            "fact=team_token_allocation",
            "value=46%",
            "section=2",
            "section_revision_version=3",
        ]
    )
    h = Keccak256()
    h.update(canonical.encode("utf-8"))
    assert r["content_hash"] == "0x" + h.hexdigest()


def test_same_canonical_evidence_has_the_same_hash_regardless_of_id_time_and_excerpt(atlas, direct_vm):
    mock_page(direct_vm, page())
    mock_answer(direct_vm, excerpt="Team: 46%")
    direct_vm.warp("2026-10-08T21:31:00Z")
    submit(atlas)
    reset(direct_vm)
    mock_page(direct_vm, page(extra="<p>The team holds Team: 46% of supply.</p>"))
    mock_answer(direct_vm, excerpt="Team: 46%")
    direct_vm.warp("2026-11-01T08:00:00Z")
    submit(atlas)
    a, b = atlas.get_evidence(1), atlas.get_evidence(2)
    assert a["evidence_id"] != b["evidence_id"] and a["retrieved_at"] != b["retrieved_at"]
    assert a["content_hash"] == b["content_hash"]


def test_hash_formats_46_and_46_point_0_percent_identically(atlas, direct_vm):
    for v in ("46%", "46.0%"):
        reset(direct_vm)
        mock_page(direct_vm, page(team=v))
        mock_answer(direct_vm, value=v, excerpt=f"Team: {v}")
        submit(atlas)
    assert atlas.get_evidence(1)["content_hash"] == atlas.get_evidence(2)["content_hash"]


@pytest.mark.parametrize(
    "change",
    [
        dict(kind="DYNAMIC_WEB"),  # different retrieval method
        dict(url="https://atlas.example.org/other"),  # different source
        dict(section="1"),  # different charter relationship
        dict(value="45%"),  # different fact value
        dict(fact="community_allocation"),  # different fact
    ],
    ids=["method", "url", "section", "value", "fact"],
)
def test_any_change_to_the_canonical_evidence_changes_the_hash(atlas, direct_vm, change):
    mock_page(direct_vm, page(team="46%"), pattern=r"atlas\.example\.org")
    mock_answer(direct_vm)
    submit(atlas)
    reset(direct_vm)
    value = change.get("value", "46%")
    mock_page(direct_vm, page(team=value), pattern=r"atlas\.example\.org")
    mock_answer(direct_vm, value=value, fact=change.get("fact", "team_token_allocation"), excerpt=f"Team: {value}")
    submit(
        atlas,
        source_kind=change.get("kind", "STATIC_WEB"),
        source_url=change.get("url", URL),
        related_section_id=change.get("section", "2"),
        claim=CLAIM_PLAIN,
    )
    assert atlas.get_evidence(1)["content_hash"] != atlas.get_evidence(2)["content_hash"]


def test_hash_differs_between_a_verified_and_an_unverifiable_result(atlas, direct_vm):
    mock_page(direct_vm, page())
    mock_answer(direct_vm)
    submit(atlas)
    reset(direct_vm)
    mock_page(direct_vm, page())
    mock_answer(direct_vm, supported=False)
    submit(atlas, claim=CLAIM_PLAIN)
    assert atlas.get_evidence(1)["content_hash"] != atlas.get_evidence(2)["content_hash"]


# ---- ids, counts, pagination -------------------------------------------------


def test_evidence_ids_increment_and_are_indexed_per_proposal(atlas, web, direct_vm, direct_alice, direct_bob):
    submit(atlas)
    submit(atlas)
    direct_vm.sender = direct_bob
    atlas.submit_proposal("Second proposal", "Another description", "Another action")  # proposal 2
    submit(atlas, proposal_id=2, related_section_id="")
    assert atlas.get_evidence_count() == 3
    assert atlas.get_proposal_evidence_count(1) == 2
    assert atlas.get_proposal_evidence_count(2) == 1
    assert atlas.get_proposal_evidence_ids_page(1, 0, 10) == [1, 2]
    assert atlas.get_proposal_evidence_ids_page(2, 0, 10) == [3]
    assert [e["evidence_id"] for e in atlas.get_proposal_evidence_page(1, 0, 10)] == [1, 2]
    assert [e["evidence_id"] for e in atlas.get_evidence_page(0, 10)] == [1, 2, 3]
    assert [e["evidence_id"] for e in atlas.get_evidence_page(1, 1)] == [2]
    assert atlas.get_evidence_page(5, 10) == []
    assert atlas.get_dao_metadata()["evidence_count"] == 3


def test_a_proposal_with_no_evidence_has_empty_lists(atlas):
    assert atlas.get_proposal_evidence_count(1) == 0
    assert atlas.get_proposal_evidence_ids_page(1, 0, 10) == []
    assert atlas.get_proposal_evidence_page(1, 0, 10) == []
    assert atlas.get_evidence_count() == 0


def test_per_proposal_evidence_is_capped(atlas, web):
    for _ in range(25):
        submit(atlas)
    before = atlas.get_evidence_count()
    with web.expect_revert("EXPECTED:EVIDENCE_LIMIT_REACHED"):
        submit(atlas)
    assert atlas.get_evidence_count() == before == 25


# ---- failed submissions consume nothing --------------------------------------


@pytest.mark.parametrize(
    "overrides,code",
    [
        (dict(proposal_id=99), "PROPOSAL_NOT_FOUND"),
        (dict(proposal_id=0), "PROPOSAL_NOT_FOUND"),
        (dict(source_url=""), "SOURCE_URL_EMPTY"),
        (dict(source_url="ftp://atlas.example.org/x"), "SOURCE_URL_UNSUPPORTED_SCHEME"),
        (dict(source_kind="PDF"), "INVALID_SOURCE_KIND"),
        (dict(source_kind="static_web"), "INVALID_SOURCE_KIND"),
        (dict(source_kind=""), "INVALID_SOURCE_KIND"),
        (dict(claim=""), "CLAIM_EMPTY"),
        (dict(claim="   \n"), "CLAIM_EMPTY"),
        (dict(claim="c" * 501), "CLAIM_TOO_LONG"),
        (dict(related_section_id="nope"), "SECTION_NOT_IN_PROPOSAL_CHARTER"),
        (dict(related_section_id="bad id"), "SECTION_ID_INVALID_CHARS"),
    ],
)
def test_rejected_submissions_do_not_consume_an_evidence_id_or_change_state(atlas, web, overrides, code):
    before = snapshot(atlas)
    with web.expect_revert("EXPECTED:" + code):
        submit(atlas, **overrides)
    assert atlas.get_evidence_count() == 0
    assert snapshot(atlas) == before
    submit(atlas)  # the next valid submission still gets id 1
    assert atlas.get_evidence(1)["evidence_id"] == 1


def test_only_the_proposer_may_attach_evidence(atlas, web, direct_vm, direct_bob, direct_owner):
    for stranger in (direct_bob, direct_owner):
        direct_vm.sender = stranger
        with direct_vm.expect_revert("EXPECTED:NOT_PROPOSER"):
            submit(atlas)
    assert atlas.get_evidence_count() == 0


# ---- charter relationship is historical --------------------------------------


def test_evidence_cannot_cite_a_charter_section_created_after_the_proposal(charter, direct_vm, direct_alice, direct_owner, web):
    charter.add_charter_section("1", "Mission", "Original mission")  # v2
    direct_vm.sender = direct_alice
    charter.submit_proposal("Early proposal", "Submitted before section 2 existed", "An action")  # bound to v2
    direct_vm.sender = direct_owner
    charter.add_charter_section("2", "Transparency", "Added later")  # v3
    direct_vm.sender = direct_alice
    before = snapshot(charter)
    with direct_vm.expect_revert("EXPECTED:SECTION_NOT_IN_PROPOSAL_CHARTER"):
        submit(charter, related_section_id="2")
    assert charter.get_evidence_count() == 0
    assert snapshot(charter) == before
    # ...but a section that existed at the proposal's version is fine.
    submit(charter, related_section_id="1")
    assert charter.get_evidence(1)["related_section_id"] == "1"


def test_related_revision_is_the_one_in_force_at_submission_not_the_latest(charter, direct_vm, direct_alice, direct_owner, web):
    charter.add_charter_section("2", "Transparency", "Wording at submission")  # v2
    direct_vm.sender = direct_alice
    charter.submit_proposal("P", "D", "A")  # bound to v2
    direct_vm.sender = direct_owner
    charter.update_charter_section("2", "Transparency", "Changed wording")  # v3
    charter.update_charter_section("2", "Transparency", "Changed again")  # v4
    direct_vm.sender = direct_alice
    submit(charter, related_section_id="2")
    r = charter.get_evidence(1)
    assert r["related_revision_version"] == 2
    historical = charter.get_charter_section_at_version("2", r["related_revision_version"])
    assert historical["body"] == "Wording at submission"  # the exact rule text the evidence relates to


def test_a_section_deactivated_before_submission_cannot_be_cited(charter, direct_vm, direct_alice, direct_owner, web):
    charter.add_charter_section("2", "Transparency", "Rule")  # v2
    charter.deactivate_charter_section("2")  # v3
    direct_vm.sender = direct_alice
    charter.submit_proposal("P", "D", "A")  # bound to v3, where section 2 is inactive
    with direct_vm.expect_revert("EXPECTED:SECTION_INACTIVE_AT_SUBMISSION"):
        submit(charter, related_section_id="2")
    assert charter.get_evidence_count() == 0


def test_a_section_deactivated_after_submission_can_still_be_cited(charter, direct_vm, direct_alice, direct_owner, web):
    charter.add_charter_section("2", "Transparency", "Rule")  # v2
    direct_vm.sender = direct_alice
    charter.submit_proposal("P", "D", "A")  # bound to v2
    direct_vm.sender = direct_owner
    charter.deactivate_charter_section("2")  # v3
    direct_vm.sender = direct_alice
    submit(charter, related_section_id="2")
    assert charter.get_evidence(1)["related_revision_version"] == 2


def test_evidence_without_a_charter_section_is_allowed(atlas, web):
    submit(atlas, related_section_id="")
    r = only_record(atlas)
    assert (r["related_section_id"], r["related_revision_version"]) == ("", 0)


# ---- immutability and isolation ----------------------------------------------


def test_no_public_method_can_change_or_delete_evidence(atlas):
    for name in (
        "update_evidence", "edit_evidence", "delete_evidence", "remove_evidence", "overwrite_evidence",
        "set_evidence_status", "update_evidence_status", "replace_evidence_source", "set_evidence_hash",
        "set_normalized_fact", "reverify_evidence", "refresh_evidence",
    ):
        assert not hasattr(atlas, name), name


def test_evidence_does_not_modify_the_proposal_or_the_charter(atlas, web):
    before = snapshot(atlas)
    for _ in range(3):
        submit(atlas)
    assert snapshot(atlas) == before


def test_evidence_records_are_unchanged_by_later_activity(atlas, web, direct_vm, direct_owner):
    submit(atlas)
    original = atlas.get_evidence(1)
    submit(atlas)
    direct_vm.sender = direct_owner
    atlas.update_charter_section("2", "Transparency", "Rewritten after the evidence")
    atlas.add_charter_section("3", "New", "New section")
    assert atlas.get_evidence(1) == original


def test_evidence_timestamps_are_protocol_time_not_page_time(atlas, direct_vm):
    mock_page(direct_vm, page(footer="Last updated 1999-01-01T00:00:00Z"))
    mock_answer(direct_vm)
    direct_vm.warp("2031-05-06T07:08:09Z")
    submit(atlas)
    r = only_record(atlas)
    assert r["retrieved_at"].startswith("2031-05-06T07:08:09")
    assert "1999" not in r["retrieved_at"] and "1999" not in r["created_at"]


# ---- the closures must be picklable (GenVM cloudpickles them) -----------------


def test_leader_and_validator_closures_are_picklable(atlas, web):
    web.check_pickling = True
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        submit(atlas)
    assert [str(w.message) for w in caught if "not picklable" in str(w.message)] == []
