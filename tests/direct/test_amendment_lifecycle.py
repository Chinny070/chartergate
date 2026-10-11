"""Stage 7: the constitutional amendment lifecycle, its refusals, staleness, historical preservation and atomicity."""

import pytest

from conftest import hex_of
from amendment_support import (
    ITEMIZED,
    NEW_BODY,
    NEW_TITLE,
    RATIONALE,
    amend,
    evaluate,
    lifecycle,
    mock_amendment,
    propose,
    review,
    snapshot,
    version,
    world,  # noqa: F401  (fixture)
    findings,
)


def refuse(vm, code, call):
    vm.clear_mocks()
    with vm.expect_revert(f"EXPECTED:{code}"):
        call()


# ---- a valid lifecycle, for each action ---------------------------------------------------------------------------------------------------


def test_a_valid_add_amendment_goes_proposed_evaluated_approved_applied(world, direct_vm, direct_owner, direct_alice):
    before = version(world)
    aid = amend(world)
    a = world.get_amendment(aid)
    assert (a["status"], a["action"], a["base_version"], a["proposer"].lower()) == ("PROPOSED", "ADD", before, hex_of(direct_alice).lower())
    evaluate(world, direct_vm, aid)
    assert world.get_amendment(aid)["status"] == "EVALUATED" and world.get_amendment(aid)["eval_verdict"] == "COMPATIBLE"
    direct_vm.sender = direct_owner
    world.approve_amendment(aid)
    assert world.get_amendment(aid)["status"] == "APPROVED"
    direct_vm.sender = direct_alice
    world.apply_amendment(aid)
    done = world.get_amendment(aid)
    assert (done["status"], done["applied_version"]) == ("APPLIED", before + 1) and version(world) == before + 1
    assert world.get_charter_section("4")["title"] == NEW_TITLE
    acc = world.get_amendment_accountability(aid)
    assert [e["kind"] for e in acc["events"]] == ["PROPOSED", "EVALUATED", "APPROVED", "APPLIED"]
    assert (acc["execution_state"], acc["contract_verified"], acc["stale"]) == ("APPLIED", True, False)


def test_a_valid_update_amendment_preserves_the_old_wording_in_history(world, direct_vm, direct_owner, direct_alice):
    old = world.get_charter_section("3")
    base = version(world)
    aid = lifecycle(world, direct_vm, direct_owner, direct_alice, action="UPDATE", section="3", title="Budget", body="Budgets must also state a currency.")
    world.apply_amendment(aid)
    assert world.get_charter_section("3")["body"] == "Budgets must also state a currency."
    assert world.get_charter_section_at_version("3", base)["body"] == old["body"]  # the historical version is untouched
    assert world.get_charter_section_at_version("3", base + 1)["body"] == "Budgets must also state a currency."
    assert world.get_charter_sections_at_version_page(base, 0, 50)[2]["body"] == old["body"]


def test_a_valid_deactivate_amendment_keeps_the_section_in_history(world, direct_vm, direct_owner, direct_alice):
    base = version(world)
    aid = lifecycle(world, direct_vm, direct_owner, direct_alice, action="DEACTIVATE", section="3", title="", body="")
    world.apply_amendment(aid)
    assert world.get_charter_section("3")["active"] is False
    assert world.get_charter_section_at_version("3", base)["active"] is True


def test_the_owner_may_also_apply_and_the_proposer_may_apply(world, direct_vm, direct_owner, direct_alice):
    aid = lifecycle(world, direct_vm, direct_owner, direct_alice)
    direct_vm.sender = direct_owner
    world.apply_amendment(aid)
    assert world.get_amendment(aid)["applied_by"].lower() == hex_of(direct_owner).lower()


def test_an_amendment_may_reference_the_proposal_that_motivated_it(world, direct_vm):
    pid = propose(world)
    aid = amend(world, source=pid)
    assert world.get_amendment(aid)["source_proposal_id"] == pid


# ---- invalid input ----------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs,code",
    [
        (dict(action="DELETE"), "AMENDMENT_ACTION_INVALID"),
        (dict(action="add"), "AMENDMENT_ACTION_INVALID"),
        (dict(section="bad id"), "SECTION_ID_INVALID_CHARS"),
        (dict(section=""), "SECTION_ID_EMPTY"),
        (dict(section="1"), "SECTION_ID_EXISTS"),  # ADD of an existing id
        (dict(title=""), "SECTION_TITLE_EMPTY"),
        (dict(body="   "), "SECTION_BODY_EMPTY"),
        (dict(title="t" * 201), "SECTION_TITLE_TOO_LONG"),
        (dict(rationale=""), "AMENDMENT_RATIONALE_EMPTY"),
        (dict(rationale="r" * 1001), "AMENDMENT_RATIONALE_TOO_LONG"),
        (dict(base=1), "AMENDMENT_STALE"),
        (dict(base=99), "AMENDMENT_STALE"),
        (dict(source=99), "PROPOSAL_NOT_FOUND"),
        (dict(action="UPDATE", section="9"), "SECTION_NOT_FOUND"),
        (dict(action="UPDATE", section="1", title="Mission", body="Fund open-source infrastructure that creates measurable value for developers."), "AMENDMENT_NO_CHANGE"),
        (dict(action="DEACTIVATE", section="1"), "AMENDMENT_UNEXPECTED_TEXT"),
        (dict(action="DEACTIVATE", section="9", title="", body=""), "SECTION_NOT_FOUND"),
    ],
    ids=[
        "unknown-action", "lowercase-action", "bad-section-id", "empty-section-id", "add-existing", "empty-title", "blank-body", "long-title", "empty-rationale",
        "long-rationale", "stale-base-low", "base-from-the-future", "unknown-source", "update-unknown", "update-no-change", "deactivate-with-text", "deactivate-unknown",
    ],
)
def test_invalid_proposals_are_refused_and_change_nothing(world, direct_vm, kwargs, code):
    before = snapshot(world)
    refuse(direct_vm, code, lambda: amend(world, **kwargs))
    assert snapshot(world) == before and world.get_amendment_count() == 0


def test_an_update_of_an_inactive_section_and_a_second_deactivation_are_refused(world, direct_vm, direct_owner, direct_alice):
    aid = lifecycle(world, direct_vm, direct_owner, direct_alice, action="DEACTIVATE", section="3", title="", body="")
    world.apply_amendment(aid)
    refuse(direct_vm, "SECTION_INACTIVE", lambda: amend(world, action="UPDATE", section="3", title="Budget", body="New wording."))
    refuse(direct_vm, "SECTION_ALREADY_INACTIVE", lambda: amend(world, action="DEACTIVATE", section="3", title="", body=""))


@pytest.mark.parametrize("bad", [True, 1.5, None, -1])
def test_argument_types_are_checked(world, direct_vm, bad):
    direct_vm.clear_mocks()
    with pytest.raises(Exception):
        world.propose_amendment("ADD", "4", NEW_TITLE, NEW_BODY, bad, RATIONALE, 0)


# ---- authorization --------------------------------------------------------------------------------------------------------------------------------------


def test_a_stranger_can_propose_but_cannot_evaluate_approve_apply_reject_or_close(world, direct_vm, direct_owner, direct_alice, direct_bob):
    direct_vm.sender = direct_bob
    assert amend(world, section="9", title="Bob", body="Bob's proposal.") == 1  # anyone may propose; nothing changes until the owner approves
    direct_vm.sender = direct_alice
    aid = amend(world)
    direct_vm.sender = direct_bob
    refuse(direct_vm, "NOT_AUTHORIZED", lambda: world.request_amendment_evaluation(aid))
    direct_vm.sender = direct_alice
    evaluate(world, direct_vm, aid)
    direct_vm.sender = direct_bob
    refuse(direct_vm, "NOT_OWNER", lambda: world.approve_amendment(aid))
    direct_vm.sender = direct_owner
    world.approve_amendment(aid)
    direct_vm.sender = direct_bob
    refuse(direct_vm, "NOT_AUTHORIZED", lambda: world.apply_amendment(aid))
    refuse(direct_vm, "NOT_AUTHORIZED", lambda: world.reject_amendment(aid))
    refuse(direct_vm, "NOT_AUTHORIZED", lambda: world.close_stale_amendment(aid))
    assert world.get_amendment(aid)["status"] == "APPROVED" and version(world) == 4


def test_the_proposer_cannot_approve_their_own_amendment(world, direct_vm, direct_alice):
    aid = amend(world)
    evaluate(world, direct_vm, aid)
    refuse(direct_vm, "NOT_OWNER", lambda: world.approve_amendment(aid))


def test_unknown_amendment_ids_are_refused(world, direct_vm, direct_owner):
    for call in (world.request_amendment_evaluation, world.reject_amendment, world.apply_amendment, world.close_stale_amendment):
        refuse(direct_vm, "AMENDMENT_NOT_FOUND", lambda call=call: call(7))
    direct_vm.sender = direct_owner
    refuse(direct_vm, "AMENDMENT_NOT_FOUND", lambda: world.approve_amendment(7))
    with direct_vm.expect_revert("EXPECTED:AMENDMENT_NOT_FOUND"):
        world.get_amendment_accountability(7)


# ---- approval requirements ----------------------------------------------------------------------------------------------------------------------------


def test_an_amendment_cannot_be_applied_before_it_is_approved(world, direct_vm, direct_owner, direct_alice):
    aid = amend(world)
    refuse(direct_vm, "AMENDMENT_NOT_APPROVED", lambda: world.apply_amendment(aid))  # PROPOSED
    evaluate(world, direct_vm, aid)
    refuse(direct_vm, "AMENDMENT_NOT_APPROVED", lambda: world.apply_amendment(aid))  # EVALUATED, not approved
    assert version(world) == 4 and world.get_amendment(aid)["status"] == "EVALUATED"


def test_an_unevaluated_amendment_cannot_be_approved(world, direct_vm, direct_owner):
    aid = amend(world)
    direct_vm.sender = direct_owner
    refuse(direct_vm, "AMENDMENT_NOT_APPROVABLE", lambda: world.approve_amendment(aid))


def test_a_conflicting_amendment_cannot_be_approved_and_the_conflicts_are_recorded(world, direct_vm, direct_owner, direct_alice):
    aid = amend(world, action="UPDATE", section="3", title="Budget", body="Budgets are optional.")
    evaluate(world, direct_vm, aid, compatible=False, conflicts=("1", "2"))
    a = world.get_amendment(aid)
    assert (a["eval_verdict"], a["eval_conflicting_section_ids"]) == ("CONFLICTING", ["1", "2"])
    direct_vm.sender = direct_owner
    refuse(direct_vm, "AMENDMENT_CONFLICTING", lambda: world.approve_amendment(aid))
    world.reject_amendment(aid)  # the owner can close it
    assert world.get_amendment(aid)["status"] == "REJECTED"


# ---- duplicates and replay -------------------------------------------------------------------------------------------------------------------------------


def test_each_transition_happens_once(world, direct_vm, direct_owner, direct_alice):
    aid = amend(world)
    evaluate(world, direct_vm, aid)
    direct_vm.clear_mocks()
    mock_amendment(direct_vm)
    refuse(direct_vm, "AMENDMENT_NOT_EVALUABLE", lambda: world.request_amendment_evaluation(aid))
    direct_vm.sender = direct_owner
    world.approve_amendment(aid)
    refuse(direct_vm, "AMENDMENT_NOT_APPROVABLE", lambda: world.approve_amendment(aid))
    world.apply_amendment(aid)
    v = version(world)
    refuse(direct_vm, "AMENDMENT_NOT_APPROVED", lambda: world.apply_amendment(aid))  # replay
    refuse(direct_vm, "AMENDMENT_NOT_OPEN", lambda: world.reject_amendment(aid))
    assert version(world) == v and world.get_amendment(aid)["applied_version"] == v


def test_a_rejected_amendment_cannot_continue(world, direct_vm, direct_owner, direct_alice):
    aid = amend(world)
    world.reject_amendment(aid)  # the proposer withdraws
    assert [e["kind"] for e in world.get_amendment_accountability(aid)["events"]] == ["PROPOSED", "WITHDRAWN"]
    direct_vm.clear_mocks()
    mock_amendment(direct_vm)
    refuse(direct_vm, "AMENDMENT_NOT_EVALUABLE", lambda: world.request_amendment_evaluation(aid))
    direct_vm.sender = direct_owner
    refuse(direct_vm, "AMENDMENT_NOT_APPROVABLE", lambda: world.approve_amendment(aid))
    refuse(direct_vm, "AMENDMENT_NOT_APPROVED", lambda: world.apply_amendment(aid))


# ---- stale and competing amendments -----------------------------------------------------------------------------------------------------------------------


def test_competing_amendments_against_the_same_version_only_one_can_apply(world, direct_vm, direct_owner, direct_alice):
    a = lifecycle(world, direct_vm, direct_owner, direct_alice, section="4", title="Timeline", body="State a delivery date.")
    direct_vm.sender = direct_alice
    b = amend(world, section="5", title="Security", body="State a security plan.")  # also against version 4
    evaluate(world, direct_vm, b)
    direct_vm.sender = direct_owner
    world.approve_amendment(b)  # approved while still current
    world.apply_amendment(a)  # the first one applies, the charter moves on
    assert version(world) == 5
    stale = world.get_amendment_accountability(b)
    assert (stale["stale"], stale["execution_state"]) == (True, "APPROVED_BUT_STALE")
    refuse(direct_vm, "AMENDMENT_STALE", lambda: world.apply_amendment(b))  # an approved amendment still cannot overwrite a newer charter
    assert world.get_amendment(b)["status"] == "APPROVED" and version(world) == 5
    world.close_stale_amendment(b)
    assert world.get_amendment(b)["status"] == "SUPERSEDED"
    assert world.get_amendment_accountability(b)["events"][-1]["kind"] == "SUPERSEDED"
    refuse(direct_vm, "AMENDMENT_NOT_OPEN", lambda: world.close_stale_amendment(b))


def test_a_stale_amendment_cannot_be_evaluated_or_approved(world, direct_vm, direct_owner, direct_alice):
    first = amend(world, section="4")
    second = amend(world, section="5", title="Other", body="Other rule.")
    evaluate(world, direct_vm, second)
    direct_vm.sender = direct_owner
    world.approve_amendment(second)
    world.apply_amendment(second)  # the charter moves to version 5
    direct_vm.sender = direct_alice
    direct_vm.clear_mocks()
    mock_amendment(direct_vm)
    refuse(direct_vm, "AMENDMENT_STALE", lambda: world.request_amendment_evaluation(first))
    assert world.get_amendment(first)["status"] == "PROPOSED"


def test_a_stale_amendment_that_was_evaluated_cannot_be_approved(world, direct_vm, direct_owner, direct_alice):
    first = amend(world, section="4")
    evaluate(world, direct_vm, first)
    second = amend(world, section="5", title="Other", body="Other rule.")
    evaluate(world, direct_vm, second)
    direct_vm.sender = direct_owner
    world.approve_amendment(second)
    world.apply_amendment(second)
    refuse(direct_vm, "AMENDMENT_STALE", lambda: world.approve_amendment(first))


def test_a_current_amendment_cannot_be_closed_as_stale(world, direct_vm):
    aid = amend(world)
    refuse(direct_vm, "AMENDMENT_NOT_STALE", lambda: world.close_stale_amendment(aid))


# ---- historical preservation ----------------------------------------------------------------------------------------------------------------------------------


def test_applied_amendments_never_change_a_proposals_governing_charter(world, direct_vm, direct_owner, direct_alice):
    pid = propose(world)  # submitted under version 4
    aid = lifecycle(world, direct_vm, direct_owner, direct_alice, action="UPDATE", section="3", title="Budget", body="A completely different budget rule.")
    world.apply_amendment(aid)
    assert world.get_proposal(pid)["charter_version_at_submission"] == 4
    direct_vm.clear_mocks()
    from review_support import mock_review

    mock_review(direct_vm, findings(), must=[r"CHARTER IN FORCE AT SUBMISSION \(version 4\)", r"Every funding proposal must contain a specific budget breakdown"], must_not=[r"completely different budget rule"])
    world.request_constitutional_review(pid)
    assert world.get_constitutional_review(1)["charter_version"] == 4


def test_every_applied_amendment_records_the_version_it_changed_and_the_version_it_created(world, direct_vm, direct_owner, direct_alice):
    first = lifecycle(world, direct_vm, direct_owner, direct_alice, section="4")
    world.apply_amendment(first)
    second = lifecycle(world, direct_vm, direct_owner, direct_alice, section="5", title="Other", body="Other rule.")
    world.apply_amendment(second)
    a, b = world.get_amendment(first), world.get_amendment(second)
    assert (a["base_version"], a["applied_version"], b["base_version"], b["applied_version"]) == (4, 5, 5, 6)
    assert world.get_amendments_page(0, 50)[0]["amendment_id"] == first and [x["amendment_id"] for x in world.get_amendments_page(1, 50)] == [second]


# ---- atomicity ----------------------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,code",
    [
        ("not json", "LLM_ERROR"),
        ({"compatible": "maybe"}, "LLM_ERROR:BAD_AMENDMENT_VERDICT"),
        ({"compatible": False, "conflicting_section_ids": "1"}, "LLM_ERROR:BAD_AMENDMENT_CONFLICTS"),
        ({"compatible": False, "conflicting_section_ids": ["99"]}, "LLM_ERROR:BAD_AMENDMENT_CONFLICTS"),
        ({"compatible": False, "conflicting_section_ids": ["4"]}, "LLM_ERROR:BAD_AMENDMENT_CONFLICTS"),  # the amendment's own target
        ({"compatible": False, "conflicting_section_ids": ["1", "1"]}, "LLM_ERROR:BAD_AMENDMENT_CONFLICTS"),
        ({"compatible": False, "conflicting_section_ids": [1]}, "LLM_ERROR:BAD_AMENDMENT_CONFLICTS"),
    ],
    ids=["unusable", "bad-verdict", "conflicts-not-a-list", "unknown-section", "own-target", "duplicate", "non-string"],
)
def test_a_failed_evaluation_stores_nothing(world, direct_vm, raw, code):
    aid = amend(world)
    before = snapshot(world)
    direct_vm.clear_mocks()
    mock_amendment(direct_vm, raw=raw)
    with direct_vm.expect_revert(code):
        world.request_amendment_evaluation(aid)
    assert snapshot(world) == before and world.get_amendment(aid)["status"] == "PROPOSED"
    evaluate(world, direct_vm, aid)  # the same request succeeds once the model behaves
    assert world.get_amendment(aid)["status"] == "EVALUATED"


def test_a_compatible_verdict_discards_any_listed_conflicts(world, direct_vm):
    aid = amend(world)
    evaluate(world, direct_vm, aid, compatible=True, conflicts=("1",))
    assert world.get_amendment(aid)["eval_conflicting_section_ids"] == []


def test_a_refused_apply_changes_nothing(world, direct_vm, direct_owner, direct_alice):
    aid = amend(world)
    before = snapshot(world)
    refuse(direct_vm, "AMENDMENT_NOT_APPROVED", lambda: world.apply_amendment(aid))
    assert snapshot(world) == before
