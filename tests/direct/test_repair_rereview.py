"""Stage 4 re-review: an accepted revision gets a FULL Stage 3 constitutional review, bound to that exact revision."""

import copy

import pytest

from conftest import hex_of
from repair_support import REPAIRED, ORIGINAL, accept_repair, mock_repair, repair, repairable, review_revision, two_targets, world  # noqa: F401
from review_support import add_evidence, findings_of, fnd, mock_review, request, review_of

OK = [fnd("1"), fnd("2", ev=[1]), fnd("3")]


def test_an_accepted_revision_can_be_reviewed_and_the_review_binds_to_it(repairable, direct_vm, direct_alice):
    accept_repair(repairable, direct_vm)
    assert repairable.get_proposal(1)["status"] == "REVISED"
    mock_review(direct_vm, OK)
    repairable.request_revision_review(1)
    r = repairable.get_review_for_revision(1)
    assert r["review_id"] == 2 and r["proposal_id"] == 1 and r["verdict"] == "ELIGIBLE"
    assert r["requested_by"].lower() == hex_of(direct_alice)
    assert repairable.get_review_revision_id(2) == 1  # which revision did review 2 judge? revision 1 (the repair)
    assert repairable.get_review_revision_id(1) == 0  # review 1 judged the original proposal
    assert repairable.get_proposal(1)["status"] == "ELIGIBLE"
    assert repairable.get_review_count() == 2
    assert repairable.get_proposal_review_count(1) == 2
    assert [x["review_id"] for x in repairable.get_proposal_reviews_page(1, 0, 50)] == [1, 2]
    assert [x["verdict"] for x in repairable.get_proposal_reviews_page(1, 0, 50)] == ["REPAIRABLE", "ELIGIBLE"]
    assert [f["section_id"] for f in repairable.get_review_findings_page(2, 0, 50)] == ["1", "2", "3"]


def test_both_verdicts_coexist_the_original_review_is_never_replaced(repairable, direct_vm):
    original = copy.deepcopy(review_of(repairable))
    original_findings = copy.deepcopy(findings_of(repairable))
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, OK)
    assert review_of(repairable) == original  # get_review_for_proposal is the ORIGINAL (Stage 3 semantics)
    assert findings_of(repairable) == original_findings
    assert repairable.get_review_id_for_proposal(1) == 1
    assert review_of(repairable)["verdict"] == "REPAIRABLE" and repairable.get_review_for_revision(1)["verdict"] == "ELIGIBLE"


def test_status_goes_repairable_revised_then_the_new_verdict(repairable, direct_vm):
    seen = [repairable.get_proposal(1)["status"]]
    accept_repair(repairable, direct_vm)
    seen.append(repairable.get_proposal(1)["status"])
    review_revision(repairable, direct_vm, OK)
    seen.append(repairable.get_proposal(1)["status"])
    assert seen == ["REPAIRABLE", "REVISED", "ELIGIBLE"]


# ---- who, when, how often --------------------------------------------------------------------------------------------


def test_a_revision_is_reviewed_once_only(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, OK)
    before = world(repairable)
    with direct_vm.expect_revert("EXPECTED:REVIEW_ALREADY_EXISTS"):
        repairable.request_revision_review(1)
    assert world(repairable) == before


def test_a_stranger_cannot_review_a_revision_and_the_llm_is_not_consulted(repairable, direct_vm, direct_bob):
    accept_repair(repairable, direct_vm)
    before = world(repairable)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("EXPECTED:NOT_PROPOSER"):
        repairable.request_revision_review(1)
    assert world(repairable) == before


def test_a_rejected_repair_leaves_nothing_to_review(repairable, direct_vm):
    mock_repair(direct_vm, purpose=False)
    with direct_vm.expect_revert("EXPECTED:REPAIR_REJECTED:PURPOSE_CHANGED"):
        repair(repairable)
    with direct_vm.expect_revert("EXPECTED:REVISION_NOT_FOUND"):
        repairable.request_revision_review(1)
    assert repairable.get_proposal(1)["status"] == "REPAIRABLE"


def test_the_original_proposal_cannot_be_reviewed_twice_after_a_repair(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    with direct_vm.expect_revert("EXPECTED:REVIEW_ALREADY_EXISTS"):
        request(repairable)


def test_bad_revision_review_arguments(repairable, direct_vm):
    with direct_vm.expect_revert("EXPECTED:REVISION_NOT_FOUND"):
        repairable.request_revision_review(1)
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:revision_id"):
        repairable.request_revision_review("1")
    with direct_vm.expect_revert("EXPECTED:REVIEW_NOT_FOUND"):
        accept_repair(repairable, direct_vm)
        repairable.get_review_for_revision(1)
    with direct_vm.expect_revert("EXPECTED:REVIEW_NOT_FOUND"):
        repairable.get_review_revision_id(7)


def test_a_failed_revision_review_changes_nothing_and_consumes_no_review_id(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    before = world(repairable)
    mock_review(direct_vm, None, raw="not json")
    with direct_vm.expect_revert("LLM_ERROR:MALFORMED_JSON"):
        repairable.request_revision_review(1)
    assert world(repairable) == before
    assert repairable.get_proposal(1)["status"] == "REVISED"
    direct_vm.clear_mocks()
    review_revision(repairable, direct_vm, OK)
    assert repairable.get_review_for_revision(1)["review_id"] == 2  # the failed attempt consumed no id


def test_the_revision_review_obeys_every_stage_3_validation_rule(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    for findings, code in (
        ([fnd("1")], "BAD_FINDING_COVERAGE"),
        ([fnd("1"), fnd("2", ev=[7]), fnd("3")], "BAD_EVIDENCE_REF"),
        ([fnd("1"), fnd("2"), fnd("9")], "BAD_SECTION_REF"),
    ):
        direct_vm.clear_mocks()
        mock_review(direct_vm, findings)
        with direct_vm.expect_revert("LLM_ERROR:" + code):
            repairable.request_revision_review(1)


# ---- evidence across revisions ------------------------------------------------------------------------------------------


def test_each_review_has_its_own_snapshot_and_the_old_one_never_changes(repairable, direct_vm):
    first = copy.deepcopy(review_of(repairable))
    assert first["evidence_count_at_review"] == 1
    # the proposer adds evidence after the REPAIRABLE review, as the Stage 2 flow allows
    add_evidence(repairable, direct_vm, fact="community_allocation", claim="Atlas team token allocation is 46%.")  # evidence #2
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, [fnd("1"), fnd("2", ev=[1, 2]), fnd("3")])
    second = repairable.get_review_for_revision(1)
    assert second["evidence_count_at_review"] == 2
    assert repairable.get_review_evidence_ids_page(1, 0, 50) == [1]
    assert repairable.get_review_evidence_ids_page(2, 0, 50) == [1, 2]
    assert second["evidence_set_hash"] != first["evidence_set_hash"]
    assert review_of(repairable) == first  # review 1 is untouched
    assert findings_of(repairable, 2)[1]["evidence_ids"] == [1, 2]
    # evidence belongs to the proposal, so the revision shares it: nothing was cloned
    assert repairable.get_evidence_count() == 2 and repairable.get_proposal_evidence_count(1) == 2


def test_evidence_added_after_the_revision_review_does_not_change_it(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, OK)
    snap = copy.deepcopy(repairable.get_review_for_revision(1))
    add_evidence(repairable, direct_vm, fact="late_fact", claim="Atlas team token allocation is 46%.")
    assert repairable.get_review_for_revision(1) == snap
    assert repairable.get_review_evidence_ids_page(2, 0, 50) == [1]


# ---- the revision review judges the revised text, under the original charter ---------------------------------------------


def test_the_revision_review_prompt_contains_the_revised_text_not_the_original(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    mock_review(
        direct_vm,
        OK,
        must=[r"<<<DATA\ntitle: Atlas RPC Gateway\ndescription: [^\n]*Budget: 12000 USDC engineering"],
        must_not=["We request 30000 USDC in total for development"],
    )
    repairable.request_revision_review(1)


def test_the_revision_context_hash_binds_the_revision_and_differs_from_the_original(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, OK)
    assert repairable.get_review_for_revision(1)["review_context_hash"] != review_of(repairable)["review_context_hash"]


# ---- the four verdicts after a repair ---------------------------------------------------------------------------------------


def test_a_full_repair_is_eligible(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, OK)
    assert repairable.get_review_for_revision(1)["verdict"] == "ELIGIBLE"


def test_a_partial_repair_is_admitted_but_may_still_be_repairable(two_targets, direct_vm):
    """Repair admission and constitutional compliance are different decisions."""
    accept_repair(two_targets, direct_vm, addressed=("3",))
    review_revision(two_targets, direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=True), fnd("3")])
    assert two_targets.get_review_for_revision(1)["verdict"] == "REPAIRABLE"
    assert two_targets.get_proposal(1)["status"] == "REPAIRABLE"
    assert [t["section_id"] for t in two_targets.get_repair_targets(1)] == ["2"]  # the latest review's targets
    # and the lineage can continue: revision 3 is allowed
    accept_repair(two_targets, direct_vm, ("Atlas RPC Gateway", REPAIRED[1] + " Team allocation is 18%.", REPAIRED[2]), addressed=("2",))
    assert two_targets.get_proposal_revision(2)["source_review_id"] == 2


def test_a_repair_that_introduces_a_non_repairable_violation_is_ineligible(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, [fnd("1", "VIOLATED", repairable=False), fnd("2", ev=[1]), fnd("3")])
    assert repairable.get_review_for_revision(1)["verdict"] == "INELIGIBLE"
    with direct_vm.expect_revert("EXPECTED:REPAIR_NOT_ALLOWED"):
        repair(repairable)


def test_a_repair_that_needs_missing_evidence_is_insufficient_evidence(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, [fnd("1"), fnd("2", "UNCLEAR", missing="budget_confirmation"), fnd("3")])
    assert repairable.get_review_for_revision(1)["verdict"] == "INSUFFICIENT_EVIDENCE"
    with direct_vm.expect_revert("EXPECTED:REPAIR_NOT_ALLOWED"):  # evidence remediation is not a Stage 4 path
        repair(repairable)


def test_review_history_keeps_every_verdict_in_order(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, [fnd("1"), fnd("2", ev=[1]), fnd("3", "VIOLATED", repairable=True)], 1)
    accept_repair(repairable, direct_vm, ("Atlas RPC Gateway", REPAIRED[1] + " Detail.", REPAIRED[2]))
    review_revision(repairable, direct_vm, OK, 2)
    verdicts = [x["verdict"] for x in repairable.get_proposal_reviews_page(1, 0, 50)]
    assert verdicts == ["REPAIRABLE", "REPAIRABLE", "ELIGIBLE"]
    assert [repairable.get_review_revision_id(i) for i in (1, 2, 3)] == [0, 1, 2]
    assert repairable.get_proposal(1)["status"] == "ELIGIBLE"
    assert repairable.get_review_count() == 3
