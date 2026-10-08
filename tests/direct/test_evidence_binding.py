"""Claim -> fact -> value binding (Stage 2.1).

The invariant: validators must agree on WHICH FACT a value belongs to, not just on the value. "Team: 46%"
and "Community: 46%" carry the same number and must never be treated as equivalent evidence.

Fact identity is the submitted `fact_key` (canonicalised by one explicit rule), not an LLM-chosen label.
Semantic support is checked by a focused LLM "binding check" on the exact quote, run by the leader's
pipeline, by each validator's own pipeline, and by each validator on the LEADER's quote.
"""

import copy
import json

import pytest

from evidence_support import (
    FACT,
    URL,
    atlas,  # noqa: F401  (fixture)
    mock_answer,
    mock_binding,
    mock_page,
    page,
    reset,
    snapshot,
    submit,
    web,  # noqa: F401  (fixture)
)
from test_evidence_equivalence import leader_ran, validator_sees

CLAIM_Q = "What is the team token allocation?"
CLAIM_46 = "Atlas team token allocation is 46%."

# The ambiguous page: two different subjects with the SAME number.
BOTH = "<html><body><ul><li>Team: 46%</li><li>Community: 46%</li><li>Treasury: 8%</li></ul><footer>noise 1</footer></body></html>"
BOTH_NOISY = "<html><body><ul><li>Team: 46%</li><li>Community: 46%</li><li>Treasury: 8%</li></ul><footer>other noise 99</footer></body></html>"
TEAM_42 = "<html><body><ul><li>Team: 42%</li><li>Community: 46%</li><li>Treasury: 12%</li></ul></body></html>"

TEAM_ANSWER = dict(value="46%", excerpt="Team: 46%")
COMMUNITY_ANSWER = dict(value="46%", excerpt="Community: 46%")


def only(c):
    assert c.get_evidence_count() == 1
    return c.get_evidence(1)


# ---- the cases from the brief --------------------------------------------------------------


def test_same_fact_same_value_is_accepted(atlas, direct_vm):
    leader_ran(atlas, direct_vm, html=BOTH, claim=CLAIM_Q, answer=TEAM_ANSWER)
    assert only(atlas)["status"] == "VERIFIED"
    assert validator_sees(direct_vm, html=BOTH_NOISY, answer=TEAM_ANSWER) is True


def test_leader_binds_the_wrong_subject_validator_binds_the_right_one_is_rejected(atlas, direct_vm):
    """Leader: community = 46%.  Validator: team = 46%.  Same number, different fact."""
    stored = leader_ran(atlas, direct_vm, html=BOTH, claim=CLAIM_Q, answer=TEAM_ANSWER)
    # Forge a VERIFIED leader result whose quote is about the community (page text really contains it).
    stored["excerpt"] = "Community: 46%"
    assert validator_sees(direct_vm, html=BOTH, answer=TEAM_ANSWER, leader_result=stored, leader_binds=False) is False


def test_leader_binds_team_validator_binds_community_is_rejected(atlas, direct_vm):
    """Leader: team = 46%.  Validator (independently): community = 46%."""
    leader_ran(atlas, direct_vm, html=BOTH, claim=CLAIM_Q, answer=TEAM_ANSWER)
    assert only(atlas)["status"] == "VERIFIED"
    assert validator_sees(direct_vm, html=BOTH, answer=dict(COMMUNITY_ANSWER, binds=False)) is False


def test_page_has_both_46_percents_and_the_leader_grounds_the_wrong_one(atlas, direct_vm):
    """The honest leader pipeline itself refuses to verify a quote that is about another subject."""
    leader_ran(atlas, direct_vm, html=BOTH, claim=CLAIM_Q, answer=dict(COMMUNITY_ANSWER, binds=False))
    r = only(atlas)
    assert r["status"] == "UNVERIFIABLE" and r["status_reason"] == "NOT_BOUND"
    assert (r["normalized_value"], r["excerpt"]) == ("", "")  # nothing about the wrong subject is stored
    assert r["normalized_fact"] == FACT


def test_claim_46_source_says_team_42_and_community_46_never_verifies_46_for_team(atlas, direct_vm):
    # (a) the extraction wrongly reports the community figure as supporting the claim
    leader_ran(atlas, direct_vm, html=TEAM_42, claim=CLAIM_46, answer=dict(COMMUNITY_ANSWER, supported=True, binds=False))
    a = atlas.get_evidence(1)
    assert a["status"] == "UNVERIFIABLE" and a["status_reason"] == "NOT_BOUND"
    assert a["normalized_value"] == ""
    # (b) the extraction reads the team line correctly: 42%, which does not support the claim
    leader_ran(atlas, direct_vm, html=TEAM_42, claim=CLAIM_46, answer=dict(supported=False, value="42%", excerpt="Team: 42%"))
    b = atlas.get_evidence(2)
    assert b["status"] == "UNVERIFIABLE" and b["normalized_value"] == "42%"
    # (c) the extraction claims team = 42% supports the 46% claim: the deterministic number guard stops it
    leader_ran(atlas, direct_vm, html=TEAM_42, claim=CLAIM_46, answer=dict(supported=True, value="42%", excerpt="Team: 42%"))
    c = atlas.get_evidence(3)
    assert c["status"] == "UNVERIFIABLE" and c["status_reason"] == "VALUE_NOT_IN_CLAIM"
    assert all(atlas.get_evidence(i)["normalized_value"] != "46%" for i in (1, 2, 3))
    assert all(atlas.get_evidence(i)["status"] != "VERIFIED" for i in (1, 2, 3))


def test_harmless_formatting_of_the_same_fact_is_accepted_when_explicitly_normalised(atlas, direct_vm):
    both = page(extra="<p>Team (precise): 46.0%</p>")
    leader_ran(atlas, direct_vm, html=both, claim=CLAIM_Q, answer=dict(value="46%", excerpt="Team: 46%"), fact_key="Team  Token-Allocation")
    assert only(atlas)["normalized_fact"] == FACT  # fact key canonicalised: case, spaces, hyphens
    assert validator_sees(direct_vm, html=both, answer=dict(value="46.0%", excerpt="Team (precise): 46.0%")) is True


# ---- the binding rule is what decides, nothing else ---------------------------------------


def test_the_leaders_quote_binding_is_the_only_thing_that_rejects_a_wrong_subject_quote(atlas, direct_vm):
    """Same forged quote, same page, same validator extraction. Only the validator's binding answer differs."""
    stored = leader_ran(atlas, direct_vm, html=BOTH, claim=CLAIM_Q, answer=TEAM_ANSWER)
    stored["excerpt"] = "Community: 46%"
    assert validator_sees(direct_vm, html=BOTH, answer=TEAM_ANSWER, leader_result=copy.deepcopy(stored), leader_binds=True) is True
    assert validator_sees(direct_vm, html=BOTH, answer=TEAM_ANSWER, leader_result=copy.deepcopy(stored), leader_binds=False) is False


def test_a_result_about_a_different_fact_is_rejected(atlas, direct_vm):
    stored = leader_ran(atlas, direct_vm, html=BOTH, claim=CLAIM_Q, answer=TEAM_ANSWER)
    stored["fact"] = "community_token_allocation"
    assert validator_sees(direct_vm, html=BOTH, answer=TEAM_ANSWER, leader_result=stored) is False


@pytest.mark.parametrize("fact", ["", "Team_Token_Allocation", "team-token-allocation", "team_allocation", None, 5])
def test_the_leaders_fact_must_be_exactly_the_submitted_canonical_key(atlas, direct_vm, fact):
    stored = leader_ran(atlas, direct_vm, html=BOTH, claim=CLAIM_Q, answer=TEAM_ANSWER)
    stored["fact"] = fact
    assert validator_sees(direct_vm, html=BOTH, answer=TEAM_ANSWER, leader_result=stored) is False


def test_contract_rejects_an_agreed_result_about_another_fact(atlas, direct_vm, monkeypatch):
    from genlayer import gl

    mock_page(direct_vm, BOTH)
    mock_answer(direct_vm, **TEAM_ANSWER)
    wrong = {"proposal_id": 1, "source_url": URL, "retrieval_method": "GET", "status": "VERIFIED", "reason": "SUPPORTED",
             "fact": "community_token_allocation", "value": "46%", "excerpt": "Community: 46%"}
    monkeypatch.setattr(gl.vm, "run_nondet", lambda leader, validator, **kw: wrong)
    with direct_vm.expect_revert("CONSENSUS_ERROR:MALFORMED_RESULT"):
        submit(atlas, claim=CLAIM_Q)
    assert atlas.get_evidence_count() == 0


# ---- two different facts with the same number are two different pieces of evidence ----------------


def test_same_value_for_two_facts_is_two_distinct_records_with_distinct_hashes(atlas, direct_vm):
    reset(direct_vm)
    mock_page(direct_vm, BOTH)
    mock_answer(direct_vm, **TEAM_ANSWER)
    mock_answer(direct_vm, **COMMUNITY_ANSWER)
    submit(atlas, claim=CLAIM_Q, fact_key="team_token_allocation")
    submit(atlas, claim="What is the community token allocation?", fact_key="community_token_allocation")
    a, b = atlas.get_evidence(1), atlas.get_evidence(2)
    assert (a["status"], a["normalized_value"]) == ("VERIFIED", "46%") == (b["status"], b["normalized_value"])
    assert a["normalized_fact"] != b["normalized_fact"]
    assert a["content_hash"] != b["content_hash"]


# ---- fact key canonicalisation: one explicit rule, no synonym aliases -----------------------------------


@pytest.mark.parametrize(
    "given",
    ["team_token_allocation", "Team_Token_Allocation", "  TEAM_TOKEN_ALLOCATION  ", "team token allocation",
     "Team Token-Allocation", "team-token-allocation", "team   token \t allocation"],
)
def test_case_whitespace_and_hyphens_are_the_only_normalisation(atlas, web, given):
    submit(atlas, fact_key=given)
    assert atlas.get_evidence(1)["normalized_fact"] == "team_token_allocation"


@pytest.mark.parametrize("given", ["team_allocation", "team_tokens", "token_allocation_team", "team_token_allocations", "team.token.allocation"])
def test_there_are_no_synonym_aliases_different_keys_are_different_facts(atlas, web, direct_vm, given):
    """team_allocation is NOT team_token_allocation: no fuzzy matching, no thesaurus."""
    if "." in given:
        with direct_vm.expect_revert("EXPECTED:FACT_KEY_INVALID"):
            submit(atlas, fact_key=given)
        return
    submit(atlas, fact_key=given)
    assert atlas.get_evidence(1)["normalized_fact"] == given
    assert atlas.get_evidence(1)["normalized_fact"] != FACT


@pytest.mark.parametrize(
    "given,code",
    [
        ("", "FACT_KEY_EMPTY"),
        ("   \n ", "FACT_KEY_EMPTY"),
        ("team/allocation", "FACT_KEY_INVALID"),
        ("team:allocation", "FACT_KEY_INVALID"),
        ("équipe", "FACT_KEY_INVALID"),
        ("team%allocation", "FACT_KEY_INVALID"),
        ("___", "FACT_KEY_INVALID"),
        ("---", "FACT_KEY_INVALID"),
        ("a" * 65, "FACT_KEY_TOO_LONG"),
    ],
)
def test_invalid_fact_keys_are_rejected_and_consume_nothing(atlas, web, given, code):
    before = snapshot(atlas)
    with web.expect_revert("EXPECTED:" + code):
        submit(atlas, fact_key=given)
    assert atlas.get_evidence_count() == 0
    assert snapshot(atlas) == before


def test_a_64_character_fact_key_is_accepted(atlas, web):
    submit(atlas, fact_key="k" * 64)
    assert atlas.get_evidence(1)["normalized_fact"] == "k" * 64


@pytest.mark.parametrize("bad", [1, True, None, ["x"], {"a": 1}, b"x"])
def test_fact_key_must_be_a_string(atlas, web, bad):
    with web.expect_revert("EXPECTED:INVALID_TYPE:fact_key"):
        submit(atlas, fact_key=bad)
    assert atlas.get_evidence_count() == 0


def test_the_llm_cannot_name_the_fact(atlas, direct_vm):
    """An LLM-volunteered fact label of any shape is ignored; the record carries the submitted key."""
    mock_page(direct_vm, BOTH)
    for label in ("community_token_allocation", "TOTALLY DIFFERENT", ["x"], 7, None):
        reset(direct_vm)
        mock_page(direct_vm, BOTH)
        mock_answer(direct_vm, raw=json.dumps({"supported": True, "fact": label, **TEAM_ANSWER}))
        mock_binding(direct_vm, "Team: 46%")
        submit(atlas, claim=CLAIM_Q)
    assert {atlas.get_evidence(i)["normalized_fact"] for i in range(1, 6)} == {FACT}


# ---- what the LLM is actually asked ---------------------------------------------------------------------


def test_prompts_carry_the_fact_the_claim_and_the_exact_quote(atlas, direct_vm):
    from genlayer import gl

    seen = []
    original = gl.nondet.exec_prompt

    def spy(prompt, **kw):
        seen.append(prompt)
        return original(prompt, **kw)

    mock_page(direct_vm, BOTH)
    mock_answer(direct_vm, **TEAM_ANSWER)
    gl.nondet.exec_prompt = spy
    try:
        submit(atlas, claim=CLAIM_Q)
    finally:
        gl.nondet.exec_prompt = original
    extraction, binding = seen
    assert "CLAIM TO CHECK:\n" + CLAIM_Q in extraction and "FACT TO EXTRACT: " + FACT in extraction
    assert "BINDING CHECK" in binding and "FACT BEING CHECKED: " + FACT in binding
    assert "VALUE: 46%" in binding and "<<<QUOTE\nTeam: 46%\nQUOTE>>>" in binding
    assert "CLAIM: " + CLAIM_Q in binding
    assert "different subject" in binding  # the instruction that makes the check about the subject, not the number


# ---- the binding check itself can fail, and fails closed ---------------------------------------------------


@pytest.mark.parametrize(
    "raw,code",
    [
        ('{"states_fact": "maybe"}', "BAD_BINDING"),
        ('{"states_fact": 1}', "BAD_BINDING"),
        ('{"other": true}', "BAD_BINDING"),
        ("not json", "MALFORMED_JSON"),
        ("[true]", "NOT_AN_OBJECT"),
    ],
    ids=["maybe", "int", "missing_key", "prose", "array"],
)
def test_malformed_binding_output_fails_closed_on_the_leader(atlas, direct_vm, raw, code):
    mock_page(direct_vm, BOTH)
    direct_vm.mock_llm(r"CLAIM TO CHECK", json.dumps({"supported": True, **TEAM_ANSWER}))
    direct_vm.mock_llm(r"BINDING CHECK", raw)
    with direct_vm.expect_revert("LLM_ERROR:" + code):
        submit(atlas, claim=CLAIM_Q)
    assert atlas.get_evidence_count() == 0


def test_binding_aliases_and_string_booleans_are_accepted(atlas, direct_vm):
    mock_page(direct_vm, BOTH)
    direct_vm.mock_llm(r"CLAIM TO CHECK", json.dumps({"supported": True, **TEAM_ANSWER}))
    direct_vm.mock_llm(r"BINDING CHECK", 'Sure: {"binds": "TRUE"} done')
    submit(atlas, claim=CLAIM_Q)
    assert only(atlas)["status"] == "VERIFIED"


def test_validator_whose_binding_call_is_unusable_votes_no_instead_of_crashing(atlas, direct_vm):
    stored = leader_ran(atlas, direct_vm, html=BOTH, claim=CLAIM_Q, answer=TEAM_ANSWER)
    reset(direct_vm)
    mock_page(direct_vm, BOTH)
    direct_vm.mock_llm(r"CLAIM TO CHECK", json.dumps({"supported": True, **TEAM_ANSWER}))
    direct_vm.mock_llm(r"BINDING CHECK", "gibberish")
    assert direct_vm.run_validator(leader_result=stored) is False


def test_binding_call_failure_reverts_with_llm_error(atlas, direct_vm, monkeypatch):
    from genlayer import gl

    mock_page(direct_vm, BOTH)
    mock_answer(direct_vm, **TEAM_ANSWER)
    original = gl.nondet.exec_prompt

    def flaky(prompt, **kw):
        if "BINDING CHECK" in prompt:
            raise gl.nondet.NondetException("provider down")
        return original(prompt, **kw)

    monkeypatch.setattr(gl.nondet, "exec_prompt", flaky)
    with direct_vm.expect_revert("LLM_ERROR:CALL_FAILED"):
        submit(atlas, claim=CLAIM_Q)
    assert atlas.get_evidence_count() == 0


def test_binding_is_not_asked_when_the_quote_is_not_even_on_the_page(atlas, direct_vm):
    """Grounding comes first and is deterministic; an ungrounded quote never reaches the LLM binding check."""
    mock_page(direct_vm, BOTH)
    direct_vm.mock_llm(r"CLAIM TO CHECK", json.dumps({"supported": True, "value": "46%", "excerpt": "Team members hold 46%"}))
    # no binding mock registered: a binding call would raise MockNotFoundError
    submit(atlas, claim=CLAIM_Q)
    assert only(atlas)["status_reason"] == "NOT_GROUNDED"


def test_the_binding_check_is_also_applied_to_unsupported_observations(atlas, direct_vm):
    """Even for UNVERIFIABLE records, nothing is stored about a subject other than the one asked about."""
    leader_ran(atlas, direct_vm, html=BOTH, claim=CLAIM_Q, answer=dict(supported=False, **COMMUNITY_ANSWER, binds=False))
    r = only(atlas)
    assert (r["status"], r["status_reason"]) == ("UNVERIFIABLE", "NOT_SUPPORTED")
    assert (r["normalized_value"], r["excerpt"]) == ("", "")
