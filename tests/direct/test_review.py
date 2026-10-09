"""Stage 3 constitutional review: verdicts, derivation precedence, binding, atomicity, immutability.

The LLM is mocked. These tests prove the contract's rules, not the quality of a real model's reasoning.
"""

import copy

import pytest

from conftest import hex_of
from evidence_support import atlas  # noqa: F401  (not used here; keeps the fixture import style uniform)
from review_support import (
    T_REVIEW,
    all_findings,
    findings_of,
    fnd,
    mock_review,
    request,
    review_of,
    reviewable,  # noqa: F401  (fixture)
    world,
)

# ---- the four acceptance fixtures -------------------------------------------------------------------


def test_fixture_a_eligible(reviewable, direct_vm):
    """Mission satisfied by the proposal; transparency satisfied by VERIFIED evidence #1."""
    mock_review(direct_vm, all_findings(fnd("1"), fnd("2", ev=[1])))
    request(reviewable)
    r = review_of(reviewable)
    assert r["verdict"] == "ELIGIBLE"
    assert r["primary_section_id"] == ""
    assert reviewable.get_proposal(1)["status"] == "ELIGIBLE"


def test_fixture_b_ineligible(reviewable, direct_vm):
    """A direct, material, non-curable conflict established by VERIFIED evidence #1."""
    mock_review(direct_vm, all_findings(fnd("1"), fnd("2", "VIOLATED", repairable=False, ev=[1])))
    request(reviewable)
    r = review_of(reviewable)
    assert r["verdict"] == "INELIGIBLE"
    assert r["primary_section_id"] == "2"
    assert reviewable.get_proposal(1)["status"] == "INELIGIBLE"


def test_fixture_c_repairable(reviewable, direct_vm):
    """A real current deficiency that can be cured by supplying a disclosure."""
    mock_review(direct_vm, all_findings(fnd("1"), fnd("2", "VIOLATED", repairable=True, rationale="treasury disclosure missing")))
    request(reviewable)
    r = review_of(reviewable)
    assert r["verdict"] == "REPAIRABLE"
    assert r["primary_section_id"] == "2"
    assert reviewable.get_proposal(1)["status"] == "REPAIRABLE"


def test_fixture_d_insufficient_evidence(reviewable, direct_vm):
    """No violation is shown, but a required fact has no VERIFIED evidence (only a failed attempt, #3)."""
    mock_review(direct_vm, all_findings(fnd("1"), fnd("2", "UNCLEAR", ev=[3], missing="conflict_of_interest_disclosure")))
    request(reviewable)
    r = review_of(reviewable)
    assert r["verdict"] == "INSUFFICIENT_EVIDENCE"
    assert r["primary_section_id"] == "2"
    assert reviewable.get_proposal(1)["status"] == "INSUFFICIENT_EVIDENCE"
    assert findings_of(reviewable)[1]["missing_fact"] == "conflict_of_interest_disclosure"


# ---- deterministic verdict precedence ----------------------------------------------------------------

S = lambda sid="1": fnd(sid)  # noqa: E731
NA = lambda sid: fnd(sid, "NOT_APPLICABLE")  # noqa: E731
V_FIX = lambda sid: fnd(sid, "VIOLATED", repairable=True)  # noqa: E731
V_BAD = lambda sid: fnd(sid, "VIOLATED", repairable=False)  # noqa: E731
U = lambda sid: fnd(sid, "UNCLEAR")  # noqa: E731

PRECEDENCE = [
    ("all satisfied", [S("1"), S("2")], "ELIGIBLE"),
    ("satisfied and not applicable", [S("1"), NA("2")], "ELIGIBLE"),
    ("one nonrepairable violation", [S("1"), V_BAD("2")], "INELIGIBLE"),
    ("one repairable violation", [S("1"), V_FIX("2")], "REPAIRABLE"),
    ("several repairable violations", [V_FIX("1"), V_FIX("2")], "REPAIRABLE"),
    ("repairable plus nonrepairable violation", [V_FIX("1"), V_BAD("2")], "INELIGIBLE"),
    ("no violation, unresolved fact", [S("1"), U("2")], "INSUFFICIENT_EVIDENCE"),
    ("unclear plus nonrepairable violation", [U("1"), V_BAD("2")], "INELIGIBLE"),
    ("unclear plus repairable violation", [U("1"), V_FIX("2")], "REPAIRABLE"),
    ("two unclear", [U("1"), U("2")], "INSUFFICIENT_EVIDENCE"),
]


@pytest.mark.parametrize("findings,verdict", [(f, v) for _n, f, v in PRECEDENCE], ids=[n for n, _f, _v in PRECEDENCE])
def test_verdict_precedence(reviewable, direct_vm, findings, verdict):
    mock_review(direct_vm, findings)
    request(reviewable)
    assert review_of(reviewable)["verdict"] == verdict
    assert reviewable.get_proposal(1)["status"] == verdict


def test_primary_section_prefers_a_nonrepairable_violation(reviewable, direct_vm):
    mock_review(direct_vm, [V_FIX("1"), V_BAD("2")])
    request(reviewable)
    assert review_of(reviewable)["primary_section_id"] == "2"


def test_llm_supplied_verdict_is_ignored(reviewable, direct_vm):
    """The LLM never decides the verdict: whatever it claims, the findings decide."""
    mock_review(direct_vm, [S("1"), V_BAD("2")], extra={"verdict": "ELIGIBLE", "overall": "ELIGIBLE"})
    request(reviewable)
    assert review_of(reviewable)["verdict"] == "INELIGIBLE"


# ---- stored review shape -----------------------------------------------------------------------------


def test_review_record_fields(reviewable, direct_vm, direct_alice):
    mock_review(direct_vm, all_findings(fnd("1"), fnd("2", ev=[1])))
    request(reviewable)
    r = review_of(reviewable)
    assert reviewable.get_review_count() == 1
    assert reviewable.get_review_id_for_proposal(1) == 1
    assert reviewable.get_constitutional_review(1) == r
    assert r["review_id"] == 1 and r["proposal_id"] == 1
    assert r["requested_by"].lower() == hex_of(direct_alice)
    assert r["charter_version"] == 3
    assert r["evidence_count_at_review"] == 4
    assert r["finding_count"] == 2
    assert r["created_at"] == T_REVIEW
    for h in (r["evidence_set_hash"], r["review_context_hash"], r["review_hash"]):
        assert h.startswith("0x") and len(h) == 66


def test_findings_are_stored_in_charter_order_with_evidence_refs(reviewable, direct_vm):
    # The LLM answers out of order; storage is in charter order.
    mock_review(direct_vm, [fnd("2", ev=[1], rationale="Disclosed."), fnd("1", rationale="On mission.")])
    request(reviewable)
    stored = findings_of(reviewable)
    assert [f["section_id"] for f in stored] == ["1", "2"]
    assert stored[1] == {
        "section_id": "2",
        "finding": "SATISFIED",
        "repairable": False,
        "evidence_ids": [1],
        "missing_fact": "",
        "rationale": "Disclosed.",
    }
    assert reviewable.get_review_findings_page(1, 1, 1) == [stored[1]]


def test_evidence_snapshot_reads(reviewable, direct_vm):
    mock_review(direct_vm, all_findings())
    request(reviewable)
    assert reviewable.get_review_evidence_ids_page(1, 0, 50) == [1, 2, 3, 4]
    assert reviewable.get_review_evidence_ids_page(1, 1, 2) == [2, 3]


def test_review_reads_are_bounded_and_typed(reviewable, direct_vm):
    mock_review(direct_vm, all_findings())
    request(reviewable)
    with direct_vm.expect_revert("EXPECTED:PAGE_LIMIT_TOO_LARGE"):
        reviewable.get_review_findings_page(1, 0, 51)
    with direct_vm.expect_revert("EXPECTED:REVIEW_NOT_FOUND"):
        reviewable.get_constitutional_review(2)
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:review_id"):
        reviewable.get_constitutional_review("1")
    with direct_vm.expect_revert("EXPECTED:PROPOSAL_NOT_FOUND"):
        reviewable.get_review_for_proposal(9)


def test_proposal_without_review_reads(reviewable, direct_vm):
    assert reviewable.get_review_count() == 0
    assert reviewable.get_review_id_for_proposal(1) == 0
    with direct_vm.expect_revert("EXPECTED:REVIEW_NOT_FOUND"):
        review_of(reviewable)


# ---- who may request, and once only --------------------------------------------------------------------


def test_only_the_proposer_may_request(reviewable, direct_vm, direct_bob, direct_owner):
    mock_review(direct_vm, all_findings())
    before = world(reviewable)
    for stranger in (direct_bob, direct_owner):
        direct_vm.sender = stranger
        with direct_vm.expect_revert("EXPECTED:NOT_PROPOSER"):
            request(reviewable)
    assert world(reviewable) == before


def test_duplicate_review_is_rejected_cleanly(reviewable, direct_vm):
    mock_review(direct_vm, all_findings())
    request(reviewable)
    before = world(reviewable)
    with direct_vm.expect_revert("EXPECTED:REVIEW_ALREADY_EXISTS"):
        request(reviewable)
    assert world(reviewable) == before
    assert reviewable.get_review_count() == 1


def test_unknown_proposal_and_bad_types(reviewable, direct_vm):
    with direct_vm.expect_revert("EXPECTED:PROPOSAL_NOT_FOUND"):
        request(reviewable, 7)
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:proposal_id"):
        request(reviewable, "1")
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:proposal_id"):
        request(reviewable, True)


# ---- failed reviews change nothing ------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,code",
    [
        ("not json at all", "MALFORMED_JSON"),
        ("[1, 2]", "NOT_AN_OBJECT"),
        ('{"findings": "none"}', "BAD_FINDINGS"),
        ('{"nothing": 1}', "BAD_FINDINGS"),
    ],
    ids=["prose", "array", "findings-not-list", "no-findings"],
)
def test_malformed_llm_output_fails_closed_and_changes_nothing(reviewable, direct_vm, raw, code):
    mock_review(direct_vm, None, raw=raw)
    before = world(reviewable)
    with direct_vm.expect_revert("LLM_ERROR:" + code):
        request(reviewable)
    assert world(reviewable) == before
    assert reviewable.get_review_count() == 0
    assert reviewable.get_proposal(1)["status"] == "SUBMITTED"
    # no review id was consumed: the next successful review is review 1
    direct_vm.clear_mocks()
    mock_review(direct_vm, all_findings())
    request(reviewable)
    assert review_of(reviewable)["review_id"] == 1


def test_failed_review_does_not_mutate_evidence_or_charter(reviewable, direct_vm):
    mock_review(direct_vm, [fnd("1")])  # wrong coverage
    before = world(reviewable)
    with direct_vm.expect_revert("LLM_ERROR:BAD_FINDING_COVERAGE"):
        request(reviewable)
    after = world(reviewable)
    assert after["evidence"] == before["evidence"]
    assert after["sections"] == before["sections"]
    assert after["dao"] == before["dao"]


def test_llm_call_failure_fails_closed(reviewable, direct_vm):
    # no LLM mock registered at all
    with pytest.raises(Exception):
        request(reviewable)
    assert reviewable.get_review_count() == 0
    assert reviewable.get_proposal(1)["status"] == "SUBMITTED"


# ---- immutability ----------------------------------------------------------------------------------------


def test_no_method_can_edit_a_review_or_set_a_proposal_status(reviewable):
    for name in ("set_status", "set_proposal_status", "edit_review", "update_review", "override_review", "rerun_review", "request_review_again"):
        assert not hasattr(reviewable, name)


def test_review_is_unchanged_by_later_activity(reviewable, direct_vm, direct_owner, direct_alice):
    mock_review(direct_vm, all_findings(fnd("1"), fnd("2", ev=[1])))
    request(reviewable)
    snap = (copy.deepcopy(review_of(reviewable)), copy.deepcopy(findings_of(reviewable)))
    direct_vm.sender = direct_owner
    reviewable.update_charter_section("2", "Transparency", "Completely rewritten rule.")
    reviewable.deactivate_charter_section("1")
    reviewable.add_charter_section("3", "New", "Brand new rule")
    direct_vm.sender = direct_alice
    direct_vm.clear_mocks()
    assert (review_of(reviewable), findings_of(reviewable)) == snap
    assert reviewable.get_proposal(1)["status"] == "ELIGIBLE"
