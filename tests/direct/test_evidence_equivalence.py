"""The custom validator rule (docs/STAGE_2_EQUIVALENCE.md section 7).

Each test runs the REAL leader once through `submit_evidence`, then replays the REAL validator with
`direct_vm.run_validator(...)` after changing what the web/LLM mocks return, to simulate a validator
that fetched different data. Nothing here compares raw pages or LLM prose.
"""

import copy
import json

import pytest

from evidence_support import (
    CLAIM_NUMBERED,
    CLAIM_PLAIN,
    URL,
    atlas,  # noqa: F401  (fixture)
    mock_answer,
    mock_binding,
    mock_page,
    page,
    reset,
    submit,
)


def leader_ran(c, vm, *, html=None, answer=None, claim=CLAIM_NUMBERED, kind="STATIC_WEB", **submit_kw):
    """Run the leader against the given page/answer and return the result it produced."""
    reset(vm)
    mock_page(vm, html if html is not None else page())
    mock_answer(vm, **(answer or {}))
    submit(c, claim=claim, source_kind=kind, **submit_kw)
    return copy.deepcopy(vm._captured_validators[-1][0])


def validator_sees(vm, *, html=None, status=200, body=None, answer=None, raw=None, leader_binds=True, **kw):
    """Change what the validator's own fetch and LLM will return, then run the validator.

    `leader_binds` is the validator's own LLM answer to "does the LEADER's quote state this fact?", which a
    validator asks in addition to re-running the extraction itself."""
    leader_result = kw["leader_result"] if "leader_result" in kw else vm._captured_validators[-1][0]
    reset(vm)
    mock_page(vm, html if html is not None else page(), status=status, body=body)
    mock_answer(vm, raw=raw, **(answer or {}))
    if isinstance(leader_result, dict) and isinstance(leader_result.get("excerpt"), str) and leader_result["excerpt"] != "":
        mock_binding(vm, leader_result["excerpt"], leader_binds)
    return vm.run_validator(**kw)


# ---- accept ------------------------------------------------------------------


def test_identical_evidence_is_accepted(atlas, direct_vm):
    leader_ran(atlas, direct_vm)
    assert validator_sees(direct_vm) is True


def test_irrelevant_page_noise_is_ignored(atlas, direct_vm):
    """Footer, date, session id and ads differ between fetches; the evidence does not."""
    leader_ran(atlas, direct_vm, html=page(footer="Rendered at 12:01 session abc123"))
    noisy = page(footer="Rendered at 19:47 session ZZZ999 | sponsored: buy now! | (c) 2031", extra="<aside>Live visitors: 1,204</aside>")
    assert validator_sees(direct_vm, html=noisy) is True


def test_excerpt_wording_and_any_llm_fact_label_do_not_matter(atlas, direct_vm):
    leader_ran(atlas, direct_vm)
    # An LLM-volunteered fact label is ignored (fact identity is the submitted key); only the value and quote matter.
    assert validator_sees(direct_vm, answer=dict(fact="team_allocation", value="46%", excerpt="Team: 46% Community: 30%")) is True


def test_46_and_46_point_0_percent_are_equivalent_when_both_are_on_the_page(atlas, direct_vm):
    both = page(extra="<p>Team (precise): 46.0%</p>")
    leader_ran(atlas, direct_vm, html=both, answer=dict(value="46%", excerpt="Team: 46%"))
    assert validator_sees(direct_vm, html=both, answer=dict(value="46.0%", excerpt="Team (precise): 46.0%")) is True


# ---- reject: the evidence differs ----------------------------------------------


def test_leader_says_46_validator_source_says_42_is_rejected(atlas, direct_vm):
    leader_ran(atlas, direct_vm)
    assert validator_sees(direct_vm, html=page(team="42%"), answer=dict(value="42%", excerpt="Team: 42%")) is False


def test_validator_picks_a_different_value_from_the_same_page_is_rejected(atlas, direct_vm):
    both = page(extra="<p>Team (revised): 42%</p>")
    leader_ran(atlas, direct_vm, html=both, claim=CLAIM_PLAIN, answer=dict(value="46%", excerpt="Team: 46%"))
    assert validator_sees(direct_vm, html=both, answer=dict(value="42%", excerpt="Team (revised): 42%")) is False


def test_0_point_46_is_not_equivalent_to_46_percent(atlas, direct_vm):
    both = page(extra="<p>Team fraction: 0.46</p>")
    leader_ran(atlas, direct_vm, html=both, claim=CLAIM_PLAIN, answer=dict(value="46%", excerpt="Team: 46%"))
    assert validator_sees(direct_vm, html=both, answer=dict(value="0.46", excerpt="Team fraction: 0.46")) is False


def test_leader_claims_support_but_validator_finds_none(atlas, direct_vm):
    leader_ran(atlas, direct_vm)
    assert validator_sees(direct_vm, answer=dict(supported=False)) is False


def test_validator_cannot_find_the_leaders_quote_in_its_own_fetch(atlas, direct_vm):
    leader_ran(atlas, direct_vm)
    other = "<html><body><p>This page no longer mentions any allocation.</p></body></html>"
    assert validator_sees(direct_vm, html=other, answer=dict(supported=False, fact="", value="", excerpt="")) is False


def test_validator_does_not_depend_on_its_own_llm_to_catch_a_fabricated_quote(atlas, direct_vm):
    """Even if the validator's LLM agrees with the leader, a quote absent from the validator's fetch is rejected."""
    leader_ran(atlas, direct_vm)
    other = "<html><body><p>Nothing about tokens here.</p></body></html>"
    assert validator_sees(direct_vm, html=other, answer=dict(value="46%", excerpt="Team: 46%")) is False


# ---- reject: the leader's result is about something else ------------------------


def test_leader_result_for_a_different_url_is_rejected(atlas, direct_vm):
    stored = leader_ran(atlas, direct_vm)
    stored["source_url"] = "https://evil.example.org/tokenomics"
    assert validator_sees(direct_vm, leader_result=stored) is False


def test_leader_result_for_a_different_proposal_is_rejected(atlas, direct_vm):
    stored = leader_ran(atlas, direct_vm)
    stored["proposal_id"] = 2
    assert validator_sees(direct_vm, leader_result=stored) is False


def test_leader_result_with_a_different_retrieval_method_is_rejected(atlas, direct_vm):
    stored = leader_ran(atlas, direct_vm)
    stored["retrieval_method"] = "RENDER_TEXT"
    assert validator_sees(direct_vm, leader_result=stored) is False


def test_a_boolean_proposal_id_echo_is_rejected(atlas, direct_vm):
    stored = leader_ran(atlas, direct_vm)
    stored["proposal_id"] = True  # True == 1 in Python
    assert validator_sees(direct_vm, leader_result=stored) is False


def test_a_fabricated_verified_result_is_rejected(atlas, direct_vm):
    stored = leader_ran(atlas, direct_vm)
    stored.update(value="99%", excerpt="Team: 99%")
    assert validator_sees(direct_vm, leader_result=stored) is False


def test_leaders_quote_must_appear_in_the_validators_own_fetch_even_when_the_value_is_right(atlas, direct_vm):
    """Only the grounding rule can reject this: the value (46%) is correct and the validator's own extraction
    agrees, but the leader's quoted sentence does not exist on the page the validator fetched."""
    stored = leader_ran(atlas, direct_vm)
    stored["excerpt"] = "The founding team collectively holds 46% of every token"
    assert validator_sees(direct_vm, leader_result=stored) is False
    # control: with the genuine quote the same validator accepts
    stored["excerpt"] = "Team: 46%"
    assert validator_sees(direct_vm, leader_result=stored) is True


def test_a_value_not_contained_in_the_leaders_own_quote_is_rejected(atlas, direct_vm):
    stored = leader_ran(atlas, direct_vm)
    stored["value"] = "30%"  # the page does say 30% elsewhere, but not inside the quoted excerpt "Team: 46%"
    assert validator_sees(direct_vm, leader_result=stored) is False


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.pop("excerpt"),
        lambda r: r.update(extra="x"),
        lambda r: r.update(status="APPROVED"),
        lambda r: r.update(status="ELIGIBLE"),
        lambda r: r.update(value=""),
        lambda r: r.update(fact="Not A Fact!"),
        lambda r: r.update(value="v" * 201),
        lambda r: r.update(excerpt="e" * 301),
        lambda r: r.update(reason=5),
        lambda r: r.update(status=None),
    ],
    ids=["missing_key", "extra_key", "bad_status", "constitutional_verdict", "verified_without_value",
         "bad_fact", "value_too_long", "excerpt_too_long", "reason_not_str", "status_none"],
)
def test_malformed_leader_results_are_rejected(atlas, direct_vm, mutate):
    stored = leader_ran(atlas, direct_vm)
    mutate(stored)
    assert validator_sees(direct_vm, leader_result=stored) is False


@pytest.mark.parametrize("junk", [None, "VERIFIED", 7, [], ["VERIFIED"], {}], ids=["none", "str", "int", "list", "list2", "empty"])
def test_non_dict_leader_results_are_rejected(atlas, direct_vm, junk):
    leader_ran(atlas, direct_vm)
    assert validator_sees(direct_vm, leader_result=junk) is False


# ---- reject: the leader or the validator failed -----------------------------------


@pytest.mark.parametrize("message", ["LLM_ERROR:MALFORMED_JSON", "EXPECTED:CLAIM_EMPTY", "anything"])
def test_a_failed_leader_is_always_rejected_to_force_rotation(atlas, direct_vm, message):
    leader_ran(atlas, direct_vm)
    assert validator_sees(direct_vm, leader_error=Exception(message)) is False


def test_validator_whose_own_llm_output_is_unusable_votes_no_instead_of_crashing(atlas, direct_vm):
    leader_ran(atlas, direct_vm)
    assert validator_sees(direct_vm, raw="complete nonsense, no json") is False


def test_validator_that_cannot_fetch_rejects_a_verified_leader(atlas, direct_vm):
    leader_ran(atlas, direct_vm)
    assert validator_sees(direct_vm, status=503, body="") is False


# ---- non-verified statuses --------------------------------------------------------


def test_two_unavailable_sources_agree_even_if_the_error_codes_differ(atlas, direct_vm):
    reset(direct_vm)
    mock_page(direct_vm, status=404, body="")
    submit(atlas)
    assert atlas.get_evidence(1)["status"] == "SOURCE_UNAVAILABLE"
    assert validator_sees(direct_vm, status=500, body="") is True


def test_leader_unavailable_but_validator_can_read_the_page_is_rejected(atlas, direct_vm):
    reset(direct_vm)
    mock_page(direct_vm, status=404, body="")
    submit(atlas)
    assert validator_sees(direct_vm) is False


def test_both_find_the_source_unusable(atlas, direct_vm):
    reset(direct_vm)
    mock_page(direct_vm, body="")
    submit(atlas)
    assert atlas.get_evidence(1)["status"] == "INVALID_SOURCE"
    assert validator_sees(direct_vm, body="") is True


def test_both_find_the_claim_unsupported_even_if_the_observed_values_differ(atlas, direct_vm):
    leader_ran(atlas, direct_vm, claim=CLAIM_NUMBERED, html=page(team="42%"),
               answer=dict(supported=False, value="42%", excerpt="Team: 42%"))
    assert atlas.get_evidence(1)["status"] == "UNVERIFIABLE"
    assert validator_sees(direct_vm, html=page(team="43%"), answer=dict(supported=False, value="43%", excerpt="Team: 43%")) is True


def test_leader_unverifiable_but_validator_verifies_is_rejected(atlas, direct_vm):
    leader_ran(atlas, direct_vm, claim=CLAIM_PLAIN, answer=dict(supported=False))
    assert atlas.get_evidence(1)["status"] == "UNVERIFIABLE"
    assert validator_sees(direct_vm, answer=dict(supported=True)) is False


# ---- rendered pages --------------------------------------------------------------


def test_rendered_evidence_uses_the_same_rules(atlas, direct_vm):
    leader_ran(atlas, direct_vm, kind="DYNAMIC_WEB")
    assert atlas.get_evidence(1)["retrieval_method"] == "RENDER_TEXT"
    assert validator_sees(direct_vm, html=page(footer="different render noise 5555")) is True
    assert validator_sees(direct_vm, html=page(team="42%"), answer=dict(value="42%", excerpt="Team: 42%")) is False


# ---- the contract also re-checks the agreed result ---------------------------------


def test_contract_rejects_a_malformed_result_even_if_consensus_returned_it(atlas, direct_vm, monkeypatch):
    from genlayer import gl

    mock_page(direct_vm, page())
    mock_answer(direct_vm)
    bogus = {"proposal_id": 1, "source_url": URL, "retrieval_method": "GET", "status": "ELIGIBLE",
             "reason": "x", "fact": "f", "value": "v", "excerpt": "e"}
    monkeypatch.setattr(gl.vm, "run_nondet", lambda leader, validator, **kw: bogus)
    with direct_vm.expect_revert("CONSENSUS_ERROR:MALFORMED_RESULT"):
        submit(atlas)
    assert atlas.get_evidence_count() == 0


def test_contract_rejects_an_agreed_result_about_a_different_url(atlas, direct_vm, monkeypatch):
    from genlayer import gl

    mock_page(direct_vm, page())
    mock_answer(direct_vm)
    wrong = {"proposal_id": 1, "source_url": "https://evil.example.org/x", "retrieval_method": "GET", "status": "VERIFIED",
             "reason": "SUPPORTED", "fact": "team_token_allocation", "value": "46%", "excerpt": "Team: 46%"}
    monkeypatch.setattr(gl.vm, "run_nondet", lambda leader, validator, **kw: wrong)
    with direct_vm.expect_revert("CONSENSUS_ERROR:MALFORMED_RESULT"):
        submit(atlas)
    assert atlas.get_evidence_count() == 0
