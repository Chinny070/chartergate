"""Stage 4 lineage: repair is versioning, never editing. Who may repair, when, how many times, and what never changes."""

import copy

import pytest

from conftest import hex_of
from repair_support import (
    NFT,
    ORIGINAL,
    REPAIRED,
    S1,
    S2,
    S3,
    accept_repair,
    make_proposal_under_review,
    mock_repair,
    repair,
    repairable,  # noqa: F401  (fixture)
    review_revision,
    revision_hash_reference,
    two_targets,  # noqa: F401  (fixture)
    world,
)
from review_support import add_evidence, findings_of, fnd, mock_review, request, review_of

REPAIRABLE_FINDINGS = [fnd("1"), fnd("2", ev=[1]), fnd("3", "VIOLATED", repairable=True)]


# ---- an accepted repair ------------------------------------------------------------------------------------


def test_accepted_repair_creates_revision_2_and_changes_only_the_status(repairable, direct_vm, direct_alice):
    before = copy.deepcopy(world(repairable))
    original_proposal = copy.deepcopy(repairable.get_proposal(1))
    original_review = copy.deepcopy(review_of(repairable))
    original_findings = copy.deepcopy(findings_of(repairable))
    accept_repair(repairable, direct_vm)

    rev = repairable.get_proposal_revision(1)
    assert rev["revision_id"] == 1 and rev["proposal_id"] == 1 and rev["revision_number"] == 2
    assert rev["parent_revision_id"] == 0  # the parent is the original proposal (revision 1)
    assert rev["source_review_id"] == 1
    assert rev["proposer"].lower() == hex_of(direct_alice)
    assert (rev["title"], rev["description"], rev["requested_action"]) == REPAIRED
    assert rev["charter_version"] == 4
    assert rev["addressed_section_ids"] == ["3"]
    assert rev["created_at"].startswith("2026-10-09T11:00:00")
    assert rev["revision_hash"] == revision_hash_reference()
    assert repairable.get_proposal_revision_count(1) == 1

    # nothing historical changed: the original proposal text, its review, its findings, its evidence
    after_proposal = repairable.get_proposal(1)
    assert after_proposal["status"] == "REVISED"
    assert {k: v for k, v in after_proposal.items() if k != "status"} == {k: v for k, v in original_proposal.items() if k != "status"}
    assert review_of(repairable) == original_review
    assert findings_of(repairable) == original_findings
    assert repairable.get_evidence_page(0, 50) == before["evidence"]
    assert repairable.get_charter_version() == 4


def test_the_effective_proposal_is_the_original_then_the_latest_revision(repairable, direct_vm):
    root = repairable.get_effective_proposal(1)
    assert (root["revision_id"], root["revision_number"], root["status"]) == (0, 1, "REPAIRABLE")
    assert (root["title"], root["description"], root["requested_action"]) == ORIGINAL
    assert root["revision_hash"] == ""
    accept_repair(repairable, direct_vm)
    cur = repairable.get_effective_proposal(1)
    assert (cur["revision_id"], cur["revision_number"], cur["status"]) == (1, 2, "REVISED")
    assert (cur["title"], cur["description"], cur["requested_action"]) == REPAIRED
    assert cur["revision_hash"] == repairable.get_proposal_revision(1)["revision_hash"]
    # the original Stage 1 record still holds the ORIGINAL text
    assert repairable.get_proposal(1)["description"] == ORIGINAL[1]


def test_the_repair_creates_no_new_proposal_and_no_new_evidence(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    assert repairable.get_proposal_count() == 1
    assert repairable.get_evidence_count() == 1  # nothing was cloned for the revision
    assert repairable.get_proposal_evidence_count(1) == 1


# ---- who may repair, and when ------------------------------------------------------------------------------


def test_a_stranger_cannot_repair_and_no_llm_is_consulted(repairable, direct_vm, direct_bob):
    before = world(repairable)
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("EXPECTED:NOT_PROPOSER"):  # no repair mock is registered: the LLM was never reached
        repair(repairable)
    assert world(repairable) == before


@pytest.mark.parametrize(
    "findings,verdict",
    [
        ([fnd("1"), fnd("2", ev=[1]), fnd("3")], "ELIGIBLE"),
        ([fnd("1", "VIOLATED", repairable=False), fnd("2", ev=[1]), fnd("3")], "INELIGIBLE"),
        ([fnd("1"), fnd("2", "UNCLEAR"), fnd("3")], "INSUFFICIENT_EVIDENCE"),
    ],
    ids=["eligible", "ineligible", "insufficient-evidence"],
)
def test_only_a_repairable_review_allows_a_repair(charter, direct_vm, direct_alice, findings, verdict):
    make_proposal_under_review(charter, direct_vm, direct_alice, findings)
    assert review_of(charter)["verdict"] == verdict
    before = world(charter)
    with direct_vm.expect_revert("EXPECTED:REPAIR_NOT_ALLOWED"):
        repair(charter)
    assert world(charter) == before


def test_a_proposal_that_was_never_reviewed_cannot_be_repaired(charter, direct_vm, direct_alice):
    for s in (S1, S2, S3):
        charter.add_charter_section(*s)
    direct_vm.sender = direct_alice
    charter.submit_proposal(*ORIGINAL)
    with direct_vm.expect_revert("EXPECTED:REPAIR_NOT_ALLOWED"):
        repair(charter)


def test_a_revision_awaiting_review_cannot_be_repaired_again_no_branching(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    before = world(repairable)
    mock_repair(direct_vm)
    with direct_vm.expect_revert("EXPECTED:REPAIR_NOT_ALLOWED"):  # one reviewed revision may create at most ONE child
        repair(repairable, ("Another", "A second child of the same parent.", "Grant 1 USDC"))
    assert world(repairable) == before
    assert repairable.get_proposal_revision_count(1) == 1


def test_a_proposal_that_became_eligible_cannot_be_repaired(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, [fnd("1"), fnd("2", ev=[1]), fnd("3")])
    assert repairable.get_proposal(1)["status"] == "ELIGIBLE"
    with direct_vm.expect_revert("EXPECTED:REPAIR_NOT_ALLOWED"):
        repair(repairable)


def test_unknown_proposal_and_bad_types(repairable, direct_vm):
    with direct_vm.expect_revert("EXPECTED:PROPOSAL_NOT_FOUND"):
        repairable.submit_repair_revision(9, *REPAIRED)
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:proposal_id"):
        repairable.submit_repair_revision("1", *REPAIRED)
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:title"):
        repairable.submit_repair_revision(1, 5, REPAIRED[1], REPAIRED[2])


@pytest.mark.parametrize(
    "text,code",
    [
        (("", REPAIRED[1], REPAIRED[2]), "PROPOSAL_TITLE_EMPTY"),
        ((REPAIRED[0], "  ", REPAIRED[2]), "PROPOSAL_DESCRIPTION_EMPTY"),
        ((REPAIRED[0], REPAIRED[1], ""), "PROPOSAL_ACTION_EMPTY"),
        (("t" * 201, REPAIRED[1], REPAIRED[2]), "PROPOSAL_TITLE_TOO_LONG"),
        ((REPAIRED[0], "d" * 10001, REPAIRED[2]), "PROPOSAL_DESCRIPTION_TOO_LONG"),
        ((REPAIRED[0], REPAIRED[1], "a" * 2001), "PROPOSAL_ACTION_TOO_LONG"),
    ],
)
def test_revision_text_is_validated_like_a_proposal_before_any_llm_call(repairable, direct_vm, text, code):
    before = world(repairable)
    with direct_vm.expect_revert("EXPECTED:" + code):
        repair(repairable, text)
    assert world(repairable) == before


def test_an_unchanged_revision_is_rejected_deterministically_without_the_llm(repairable, direct_vm):
    with direct_vm.expect_revert("EXPECTED:REVISION_UNCHANGED"):
        repair(repairable, ORIGINAL)
    reworded = (ORIGINAL[0], "  " + ORIGINAL[1].replace(" ", "   ") + " ", ORIGINAL[2])  # whitespace only
    with direct_vm.expect_revert("EXPECTED:REVISION_UNCHANGED"):
        repair(repairable, reworded)


# ---- failed repairs leave no history ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs,code",
    [
        (dict(purpose=False), "PURPOSE_CHANGED"),
        (dict(scope=True), "SCOPE_CHANGED"),
        (dict(addressed=()), "NO_TARGET_ADDRESSED"),
    ],
    ids=["purpose-changed", "scope-changed", "no-target-addressed"],
)
def test_an_inadmissible_repair_enters_no_history_and_consumes_no_revision_id(repairable, direct_vm, kwargs, code):
    before = copy.deepcopy(world(repairable))
    mock_repair(direct_vm, **kwargs)
    with direct_vm.expect_revert("EXPECTED:REPAIR_REJECTED:" + code):
        repair(repairable)
    assert world(repairable) == before
    assert repairable.get_proposal(1)["status"] == "REPAIRABLE"
    assert repairable.get_proposal_revision_count(1) == 0
    with direct_vm.expect_revert("EXPECTED:REVISION_NOT_FOUND"):
        repairable.get_proposal_revision(1)
    # the revision id was not consumed: the next accepted repair is revision id 1
    direct_vm.clear_mocks()
    accept_repair(repairable, direct_vm)
    assert repairable.get_proposal_revision(1)["revision_number"] == 2


def test_failed_llm_output_also_leaves_no_history(repairable, direct_vm):
    before = world(repairable)
    mock_repair(direct_vm, raw="not json")
    with direct_vm.expect_revert("LLM_ERROR:MALFORMED_JSON"):
        repair(repairable)
    assert world(repairable) == before


# ---- the lineage is linear and bounded -------------------------------------------------------------------------


def three_deep(c, vm):
    """repair, re-review REPAIRABLE, repair again: revision 3 exists and is awaiting review."""
    accept_repair(c, vm)
    review_revision(c, vm, REPAIRABLE_FINDINGS, 1)
    second = ("Atlas RPC Gateway", REPAIRED[1] + " Plus a timeline.", REPAIRED[2])
    accept_repair(c, vm, second)
    return second


def test_revision_numbers_parents_and_source_reviews_chain_linearly(repairable, direct_vm):
    second = three_deep(repairable, direct_vm)
    r1, r2 = repairable.get_proposal_revision(1), repairable.get_proposal_revision(2)
    assert (r1["revision_number"], r1["parent_revision_id"], r1["source_review_id"]) == (2, 0, 1)
    assert (r2["revision_number"], r2["parent_revision_id"], r2["source_review_id"]) == (3, 1, 2)
    assert (r2["title"], r2["description"], r2["requested_action"]) == second
    assert repairable.get_proposal_revision_count(1) == 2
    assert [r["revision_id"] for r in repairable.get_proposal_revisions_page(1, 0, 50)] == [1, 2]
    assert repairable.get_effective_proposal(1)["revision_number"] == 3


def test_the_revision_limit_is_five_repairs_after_the_original(repairable, direct_vm):
    for n in range(5):
        accept_repair(repairable, direct_vm, ("Atlas RPC Gateway", REPAIRED[1] + f" Round {n}.", REPAIRED[2]))
        review_revision(repairable, direct_vm, REPAIRABLE_FINDINGS, n + 1)
    assert repairable.get_proposal_revision_count(1) == 5
    assert repairable.get_proposal(1)["status"] == "REPAIRABLE"
    before = world(repairable)
    mock_repair(direct_vm)
    with direct_vm.expect_revert("EXPECTED:REVISION_LIMIT_REACHED"):
        repair(repairable, ("Atlas RPC Gateway", REPAIRED[1] + " Round 6.", REPAIRED[2]))
    assert world(repairable) == before
    assert repairable.get_effective_proposal(1)["revision_number"] == 6


# ---- the charter version never moves ------------------------------------------------------------------------------


def amend_charter(c, vm, owner, alice):
    vm.sender = owner
    c.update_charter_section("3", "Budget", "Budget breakdowns are optional.")  # v5, rewrites the rule that failed
    c.add_charter_section("4", "Later", "A rule added after the proposal.")  # v6
    c.deactivate_charter_section("1")  # v7
    vm.sender = alice
    assert c.get_charter_version() == 7


def test_a_repair_stays_under_the_charter_the_proposal_was_submitted_under(repairable, direct_vm, direct_owner, direct_alice):
    amend_charter(repairable, direct_vm, direct_owner, direct_alice)
    mock_repair(
        direct_vm,
        must=[r"\(version 4\)", "Every funding proposal must contain a specific budget breakdown"],
        must_not=["Budget breakdowns are optional", "A rule added after"],
    )
    repair(repairable)
    rev = repairable.get_proposal_revision(1)
    assert rev["charter_version"] == 4  # inherited, not the current v7
    assert repairable.get_charter_version() == 7
    direct_vm.clear_mocks()
    # and the re-review judges revision 2 under v4 too: v4's three sections, v4's text
    mock_review(
        direct_vm,
        [fnd("1"), fnd("2", ev=[1]), fnd("3")],
        must=[r"\(version 4\)", "Every funding proposal must contain a specific budget breakdown", r"\[section_id: 1\]"],
        must_not=["Budget breakdowns are optional", r"\[section_id: 4\]"],
    )
    repairable.request_revision_review(1)
    assert repairable.get_review_for_revision(1)["verdict"] == "ELIGIBLE"
    assert review_of(repairable)["verdict"] == "REPAIRABLE"  # the original review is still what it was
    assert repairable.get_review_for_revision(1)["charter_version"] == 4


def test_every_later_revision_keeps_the_original_charter_version(repairable, direct_vm, direct_owner, direct_alice):
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, REPAIRABLE_FINDINGS, 1)
    amend_charter(repairable, direct_vm, direct_owner, direct_alice)
    accept_repair(repairable, direct_vm, ("Atlas RPC Gateway", REPAIRED[1] + " More detail.", REPAIRED[2]))
    assert [r["charter_version"] for r in repairable.get_proposal_revisions_page(1, 0, 50)] == [4, 4]
    assert repairable.get_proposal(1)["charter_version_at_submission"] == 4


# ---- reads -------------------------------------------------------------------------------------------------------


def test_repair_targets_come_from_the_parent_review(two_targets):
    targets = two_targets.get_repair_targets(1)
    assert [t["section_id"] for t in targets] == ["2", "3"]
    assert targets[1]["title"] == "Budget" and targets[1]["body"] == S3[2]  # the section text at the historical version
    assert targets[0]["rationale"] == "Team allocation not disclosed."
    assert targets[1]["evidence_ids"] == []


def test_repair_targets_are_the_parents_repairable_violations_only(charter, direct_vm, direct_alice):
    make_proposal_under_review(
        charter, direct_vm, direct_alice, [fnd("1", "UNCLEAR"), fnd("2", "VIOLATED", repairable=True), fnd("3")]
    )
    assert [t["section_id"] for t in charter.get_repair_targets(1)] == ["2"]


def test_no_repair_targets_unless_the_latest_review_is_repairable(charter, direct_vm, direct_alice):
    make_proposal_under_review(charter, direct_vm, direct_alice, [fnd("1"), fnd("2", ev=[1]), fnd("3")])
    assert charter.get_repair_targets(1) == []


def test_revision_reads_are_bounded_and_typed(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    with direct_vm.expect_revert("EXPECTED:PAGE_LIMIT_TOO_LARGE"):
        repairable.get_proposal_revisions_page(1, 0, 51)
    with direct_vm.expect_revert("EXPECTED:REVISION_NOT_FOUND"):
        repairable.get_proposal_revision(2)
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:revision_id"):
        repairable.get_proposal_revision("1")
    with direct_vm.expect_revert("EXPECTED:PROPOSAL_NOT_FOUND"):
        repairable.get_proposal_revision_count(9)
    assert repairable.get_proposal_revisions_page(1, 1, 5) == []


def test_there_is_no_method_that_edits_a_proposal_or_revision(repairable):
    for name in ("edit_proposal", "update_proposal", "edit_revision", "update_revision", "delete_revision", "set_revision"):
        assert not hasattr(repairable, name)
