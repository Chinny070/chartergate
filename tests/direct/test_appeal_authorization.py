"""Stage 6: who may appeal, which rulings may be appealed, and that every refusal happens BEFORE any nondeterministic work.

No LLM mock is registered in the refusal tests: if the contract reached the model it would fail with a missing mock instead of the
expected code, so each expected code also proves the refusal was made up front."""

import pytest

from appeal_support import (
    GROUND,
    ITEMIZED,
    NO_BREAKDOWN,
    STATEMENT,
    VIOLATED,
    adverse_review,
    appeal,
    dissent,
    findings,
    mock_appeal,
    propose,
    review,
    snapshot,
    world,  # noqa: F401  (fixture)
)
from repair_support import mock_repair
from review_support import mock_review, request


def refuse(vm, code, call):
    vm.clear_mocks()
    with vm.expect_revert(f"EXPECTED:{code}"):
        call()


def test_a_stranger_cannot_appeal(world, direct_vm, direct_bob):
    pid, rid = adverse_review(world, direct_vm)
    direct_vm.sender = direct_bob
    refuse(direct_vm, "NOT_PROPOSER", lambda: world.request_appeal(rid, GROUND, STATEMENT))


def test_a_stranger_cannot_request_a_dissent(world, direct_vm, direct_bob):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    direct_vm.sender = direct_bob
    refuse(direct_vm, "NOT_PROPOSER", lambda: world.request_reasoned_dissent(aid))


def test_the_proposer_cannot_appeal_an_eligible_ruling(world, direct_vm):
    pid = propose(world, ITEMIZED)
    rid = review(world, direct_vm, pid, findings())
    assert world.get_constitutional_review(rid)["verdict"] == "ELIGIBLE"
    refuse(direct_vm, "REVIEW_NOT_ADVERSE", lambda: world.request_appeal(rid, GROUND, STATEMENT))


def test_a_review_that_is_no_longer_the_controlling_one_cannot_be_appealed(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    direct_vm.clear_mocks()
    mock_repair(direct_vm)
    world.submit_repair_revision(pid, *ITEMIZED)
    direct_vm.clear_mocks()
    mock_review(direct_vm, findings(s3="VIOLATED", s3_kw=dict(repairable=True, rationale="Still short.")))
    world.request_revision_review(1)
    newest = int(world.get_review_count())
    refuse(direct_vm, "REVIEW_NOT_CONTROLLING", lambda: world.request_appeal(rid, GROUND, STATEMENT))  # the older review is obsolete
    assert world.get_review_appeal_status(newest)["appealable"] is True


def test_no_appeal_after_a_repair_child_exists(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    direct_vm.clear_mocks()
    mock_repair(direct_vm)
    world.submit_repair_revision(pid, *ITEMIZED)  # the repair child exists but is not yet re-reviewed: rid is still the latest review
    status = world.get_review_appeal_status(rid)
    assert status["appealable"] is False and status["blocked_reason"] == "REPAIR_ALREADY_STARTED"
    refuse(direct_vm, "REPAIR_ALREADY_STARTED", lambda: world.request_appeal(rid, GROUND, STATEMENT))


def test_no_repair_after_an_appeal_that_closed_the_option_but_repair_is_the_alternative_before_it(world, direct_vm):
    """Repair and appeal are alternatives from the same ruling: choosing repair first closes the appeal (above); an appeal that keeps
    the verdict REPAIRABLE leaves repair open (see test_appeal_semantics)."""
    pid, rid = adverse_review(world, direct_vm)
    appeal(world, direct_vm, rid, findings(**VIOLATED))
    direct_vm.clear_mocks()
    mock_repair(direct_vm)
    world.submit_repair_revision(pid, *ITEMIZED)
    assert world.get_review_appeal_status(rid)["appeal_id"] == 1


def test_a_second_appeal_of_the_same_review_is_rejected(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    appeal(world, direct_vm, rid, findings(**VIOLATED))
    refuse(direct_vm, "APPEAL_ALREADY_EXISTS", lambda: world.request_appeal(rid, GROUND, STATEMENT))
    assert world.get_appeal_count() == 1


def test_there_is_no_appeal_of_an_appeal(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    # appeals are not reviews: an appeal id is not a review id, and the review it decided cannot be appealed again
    refuse(direct_vm, "APPEAL_ALREADY_EXISTS", lambda: world.request_appeal(rid, "PROCEDURAL_ERROR", "Again."))
    refuse(direct_vm, "REVIEW_NOT_FOUND", lambda: world.request_appeal(aid + 100, GROUND, STATEMENT))


def test_a_second_dissent_is_rejected(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    dissent(world, direct_vm, aid, findings(s3="VIOLATED", s3_kw=dict(repairable=False, rationale="Not curable.")))
    refuse(direct_vm, "DISSENT_ALREADY_EXISTS", lambda: world.request_reasoned_dissent(aid))


def test_unknown_ids_are_rejected(world, direct_vm):
    refuse(direct_vm, "REVIEW_NOT_FOUND", lambda: world.request_appeal(1, GROUND, STATEMENT))
    refuse(direct_vm, "APPEAL_NOT_FOUND", lambda: world.request_reasoned_dissent(1))
    with direct_vm.expect_revert("EXPECTED:APPEAL_NOT_FOUND"):
        world.get_appeal(1)
    with direct_vm.expect_revert("EXPECTED:DISSENT_NOT_FOUND" if False else "EXPECTED:APPEAL_NOT_FOUND"):
        world.get_reasoned_dissent(1)


def test_a_missing_dissent_read_is_an_expected_error(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    with direct_vm.expect_revert("EXPECTED:DISSENT_NOT_FOUND"):
        world.get_reasoned_dissent(aid)


@pytest.mark.parametrize(
    "ground,statement,code",
    [
        ("NOT_A_GROUND", STATEMENT, "APPEAL_GROUND_INVALID"),
        ("charter_misinterpretation", STATEMENT, "APPEAL_GROUND_INVALID"),
        ("", STATEMENT, "APPEAL_GROUND_INVALID"),
        (GROUND, "", "APPEAL_STATEMENT_EMPTY"),
        (GROUND, "   ", "APPEAL_STATEMENT_EMPTY"),
        (GROUND, "x" * 1001, "APPEAL_STATEMENT_TOO_LONG"),
        ("PRECEDENT_MISAPPLICATION", STATEMENT, "GROUND_NOT_APPLICABLE"),  # the original review saw no precedent
    ],
    ids=["unknown-ground", "wrong-case", "empty-ground", "empty-statement", "blank-statement", "too-long", "precedent-ground-without-precedent"],
)
def test_invalid_appeal_arguments_are_refused_before_any_model_call(world, direct_vm, ground, statement, code):
    pid, rid = adverse_review(world, direct_vm)
    refuse(direct_vm, code, lambda: world.request_appeal(rid, ground, statement))


@pytest.mark.parametrize("arg", [True, "1", 1.5, None, -1])
def test_argument_types_are_checked(world, direct_vm, arg):
    pid, rid = adverse_review(world, direct_vm)
    direct_vm.clear_mocks()
    with pytest.raises(Exception):
        world.request_appeal(arg, GROUND, STATEMENT)


def test_a_statement_of_exactly_the_maximum_length_is_accepted(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED), statement="x" * 1000)
    assert len(world.get_appeal(aid)["statement"]) == 1000


@pytest.mark.parametrize("ground", ["CHARTER_MISINTERPRETATION", "EVIDENCE_MISAPPLICATION", "PROCEDURAL_ERROR"])
def test_every_ground_category_is_accepted(world, direct_vm, ground):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED), ground=ground)
    assert world.get_appeal(aid)["ground"] == ground


def test_a_refusal_changes_nothing(world, direct_vm, direct_bob):
    pid, rid = adverse_review(world, direct_vm)
    before = snapshot(world)
    direct_vm.sender = direct_bob
    refuse(direct_vm, "NOT_PROPOSER", lambda: world.request_appeal(rid, GROUND, STATEMENT))
    assert snapshot(world) == before and world.get_appeal_count() == 0
