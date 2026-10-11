"""Stage 9: post-execution accountability. Amendment execution is a charter change the contract itself makes, so it is contract-verified.
Execution reports about a proposal are SELF-REPORTED and are never verified: the contract cannot see an outside payment, transfer or action."""

import pytest

from conftest import hex_of
from amendment_support import (
    ITEMIZED,
    NO_BREAKDOWN,
    VIOLATED,
    amend,
    evaluate,
    findings,
    lifecycle,
    propose,
    review,
    snapshot,
    version,
    world,  # noqa: F401  (fixture)
)
from appeal_support import GROUND, STATEMENT, mock_appeal
from review_support import mock_review


def refuse(vm, code, call):
    vm.clear_mocks()
    with vm.expect_revert(f"EXPECTED:{code}"):
        call()


def eligible(world, vm):
    """A proposal whose controlling ruling is ELIGIBLE. Returns (proposal id, review id)."""
    pid = propose(world, ITEMIZED)
    return pid, review(world, vm, pid, findings())


# ---- amendment accountability (verified by the contract) -----------------------------------------------------------------------------------------------


def test_an_applied_amendment_is_contract_verified_and_names_the_versions_it_touched(world, direct_vm, direct_owner, direct_alice):
    aid = lifecycle(world, direct_vm, direct_owner, direct_alice, action="UPDATE", section="3", title="Budget", body="Budgets must name a currency.")
    acc = world.get_amendment_accountability(aid)
    assert acc["execution_state"] == "APPROVED_NOT_APPLIED" and acc["contract_verified"] is True
    assert acc["amendment"]["decided_by"].lower() == hex_of(direct_owner)  # the approver is recorded, with a time
    assert acc["amendment"]["decided_at"] != "" and acc["amendment"]["applied_version"] == 0
    world.apply_amendment(aid)
    acc = world.get_amendment_accountability(aid)
    a = acc["amendment"]
    assert (acc["execution_state"], a["status"], a["base_version"], a["applied_version"]) == ("APPLIED", "APPLIED", 4, 5)
    assert a["applied_by"] != "" and a["applied_at"] != ""
    assert [e["kind"] for e in acc["events"]] == ["PROPOSED", "EVALUATED", "APPROVED", "APPLIED"]
    assert acc["events"][-1]["charter_version"] == 5  # the event records the charter version it produced
    assert all(e["actor"] != "" and e["at"] != "" for e in acc["events"])


def test_an_amendment_that_was_never_applied_is_reported_honestly(world, direct_vm, direct_owner, direct_alice):
    open_one = amend(world)
    rejected = amend(world, section="5", title="Other", body="Other.")
    world.reject_amendment(rejected)
    assert world.get_amendment_accountability(open_one)["execution_state"] == "NOT_APPROVED"
    assert world.get_amendment_accountability(rejected)["execution_state"] == "REJECTED"
    assert world.get_amendment(rejected)["applied_version"] == 0 and world.get_amendment(rejected)["applied_by"] == ""


def test_a_superseded_amendment_is_not_reported_as_executed(world, direct_vm, direct_owner, direct_alice):
    a = lifecycle(world, direct_vm, direct_owner, direct_alice, section="4")
    b = lifecycle(world, direct_vm, direct_owner, direct_alice, section="5", title="Other", body="Other.")
    world.apply_amendment(a)
    world.close_stale_amendment(b)
    acc = world.get_amendment_accountability(b)
    assert (acc["execution_state"], acc["amendment"]["applied_version"], acc["stale"]) == ("SUPERSEDED", 0, False)


def test_accountability_records_are_immutable_there_is_no_method_that_edits_them(world, direct_vm, direct_owner, direct_alice):
    import json
    from pathlib import Path

    schema = json.loads((Path(__file__).resolve().parents[2] / "docs" / "charter_gate.schema.json").read_text(encoding="utf-8"))
    writers = {m for m, v in schema["methods"].items() if not v["readonly"]}
    assert {m for m in writers if "report" in m or "accountab" in m} == {"report_execution"}  # the only writer appends; none updates or deletes
    aid = lifecycle(world, direct_vm, direct_owner, direct_alice)
    world.apply_amendment(aid)
    before = world.get_amendment_accountability(aid)
    other = lifecycle(world, direct_vm, direct_owner, direct_alice, section="5", title="Other", body="Other.")
    world.apply_amendment(other)
    after = world.get_amendment_accountability(aid)
    assert after["amendment"] == before["amendment"] and after["events"] == before["events"]  # later governance never rewrites a closed record


# ---- proposal execution reports (self-reported, never verified) ----------------------------------------------------------------------------------------


def test_an_approved_proposal_starts_as_approved_and_not_reported(world, direct_vm):
    pid, rid = eligible(world, direct_vm)
    acc = world.get_proposal_accountability(pid)
    assert (acc["approved"], acc["execution_state"], acc["verified"], acc["reports"]) == (True, "APPROVED_NOT_REPORTED", False, [])
    assert (acc["review_id"], acc["effective_verdict"], acc["charter_version"]) == (rid, "ELIGIBLE", 4)
    assert acc["ruling_hash"] == world.get_constitutional_review(rid)["review_hash"]


def test_attempted_then_reported_complete_keeps_the_decision_the_outcome_and_the_unverified_flag(world, direct_vm, direct_alice):
    pid, rid = eligible(world, direct_vm)
    world.report_execution(pid, "ATTEMPTED", "Payment initiated by the treasurer.")
    assert world.get_proposal_accountability(pid)["execution_state"] == "ATTEMPTED"
    world.report_execution(pid, "REPORTED_COMPLETE", "Payment settled according to the treasurer.")
    acc = world.get_proposal_accountability(pid)
    assert acc["execution_state"] == "REPORTED_COMPLETE" and acc["verified"] is False
    first, second = acc["reports"]
    assert (first["report_number"], first["outcome"], second["report_number"], second["outcome"]) == (1, "ATTEMPTED", 2, "REPORTED_COMPLETE")
    for r in acc["reports"]:
        assert r["verified"] is False  # the contract cannot see an outside payment
        assert (r["review_id"], r["charter_version"], r["appeal_id"]) == (rid, 4, 0)
        assert r["ruling_hash"] == world.get_constitutional_review(rid)["review_hash"]  # the decision the report answers to
        assert r["reporter"] != "" and r["reported_at"] != ""


def test_a_failed_execution_is_represented_as_failed(world, direct_vm):
    pid, _ = eligible(world, direct_vm)
    world.report_execution(pid, "REPORTED_FAILED", "The transfer was rejected by the bank.")
    acc = world.get_proposal_accountability(pid)
    assert (acc["execution_state"], acc["reports"][0]["outcome"], acc["verified"]) == ("REPORTED_FAILED", "REPORTED_FAILED", False)


def test_a_terminal_report_closes_the_record_and_duplicates_are_refused(world, direct_vm):
    pid, _ = eligible(world, direct_vm)
    world.report_execution(pid, "ATTEMPTED", "Started.")
    refuse(direct_vm, "EXECUTION_ALREADY_ATTEMPTED", lambda: world.report_execution(pid, "ATTEMPTED", "Started again."))
    world.report_execution(pid, "REPORTED_COMPLETE", "Done.")
    for outcome in ("ATTEMPTED", "REPORTED_COMPLETE", "REPORTED_FAILED"):
        refuse(direct_vm, "EXECUTION_ALREADY_CLOSED", lambda outcome=outcome: world.report_execution(pid, outcome, "Again."))
    assert len(world.get_proposal_accountability(pid)["reports"]) == 2


def test_a_failed_report_also_closes_the_record(world, direct_vm):
    pid, _ = eligible(world, direct_vm)
    world.report_execution(pid, "REPORTED_FAILED", "Failed.")
    refuse(direct_vm, "EXECUTION_ALREADY_CLOSED", lambda: world.report_execution(pid, "REPORTED_COMPLETE", "Actually it worked."))


def test_only_the_proposer_can_report(world, direct_vm, direct_bob, direct_owner):
    pid, _ = eligible(world, direct_vm)
    for who in (direct_bob, direct_owner):
        direct_vm.sender = who
        refuse(direct_vm, "NOT_PROPOSER", lambda: world.report_execution(pid, "ATTEMPTED", "I did it."))
    assert world.get_proposal_accountability(pid)["reports"] == []


@pytest.mark.parametrize(
    "fs,code",
    [(findings(**VIOLATED), "PROPOSAL_NOT_APPROVED")],
    ids=["repairable"],
)
def test_a_proposal_that_was_not_approved_cannot_be_reported_as_executed(world, direct_vm, fs, code):
    pid = propose(world, NO_BREAKDOWN)
    review(world, direct_vm, pid, fs)
    refuse(direct_vm, code, lambda: world.report_execution(pid, "REPORTED_COMPLETE", "Paid."))
    acc = world.get_proposal_accountability(pid)
    assert (acc["approved"], acc["execution_state"]) == (False, "NOT_APPROVED")


def test_an_undecided_proposal_cannot_be_reported(world, direct_vm):
    pid = propose(world)
    refuse(direct_vm, "PROPOSAL_NOT_DECIDED", lambda: world.report_execution(pid, "ATTEMPTED", "Started."))


@pytest.mark.parametrize(
    "outcome,note,code",
    [
        ("PAID", "x", "EXECUTION_OUTCOME_INVALID"),
        ("attempted", "x", "EXECUTION_OUTCOME_INVALID"),
        ("ATTEMPTED", "", "EXECUTION_NOTE_EMPTY"),
        ("ATTEMPTED", "  ", "EXECUTION_NOTE_EMPTY"),
        ("ATTEMPTED", "n" * 501, "EXECUTION_NOTE_TOO_LONG"),
    ],
)
def test_invalid_reports_are_refused_and_store_nothing(world, direct_vm, outcome, note, code):
    pid, _ = eligible(world, direct_vm)
    refuse(direct_vm, code, lambda: world.report_execution(pid, outcome, note))
    assert world.get_proposal_accountability(pid)["reports"] == []
    world.report_execution(pid, "ATTEMPTED", "Fine.")  # nothing was consumed
    assert len(world.get_proposal_accountability(pid)["reports"]) == 1


def test_unknown_proposals_and_bad_types_are_refused(world, direct_vm):
    refuse(direct_vm, "PROPOSAL_NOT_FOUND", lambda: world.report_execution(5, "ATTEMPTED", "x"))
    direct_vm.clear_mocks()
    with pytest.raises(Exception):
        world.report_execution(True, "ATTEMPTED", "x")


def test_an_appeal_that_reverses_to_eligible_is_the_decision_a_report_references(world, direct_vm):
    pid = propose(world, ITEMIZED)
    rid = review(world, direct_vm, pid, findings(**VIOLATED))  # the (mistaken) original ruling is REPAIRABLE
    refuse(direct_vm, "PROPOSAL_NOT_APPROVED", lambda: world.report_execution(pid, "ATTEMPTED", "Started."))
    direct_vm.clear_mocks()
    mock_appeal(direct_vm, findings())
    world.request_appeal(rid, GROUND, STATEMENT)  # REVERSED to ELIGIBLE
    world.report_execution(pid, "ATTEMPTED", "Started after the appeal.")
    r = world.get_proposal_accountability(pid)["reports"][0]
    decision = world.get_appellate_decision(1)
    assert (r["appeal_id"], r["review_id"], r["ruling_hash"]) == (1, rid, decision["decision_hash"])


def test_a_closed_report_is_not_changed_by_anything_that_happens_later(world, direct_vm, direct_owner, direct_alice):
    pid, rid = eligible(world, direct_vm)
    world.report_execution(pid, "REPORTED_COMPLETE", "Done.")
    before = world.get_proposal_accountability(pid)
    aid = lifecycle(world, direct_vm, direct_owner, direct_alice, action="UPDATE", section="3", title="Budget", body="A newer budget rule.")
    world.apply_amendment(aid)
    direct_vm.sender = direct_alice
    after = world.get_proposal_accountability(pid)
    assert after == before and after["charter_version"] == 4  # the historical charter version the decision was made under


def test_a_refused_report_changes_nothing_else(world, direct_vm, direct_bob):
    pid, _ = eligible(world, direct_vm)
    before = snapshot(world)
    direct_vm.sender = direct_bob
    refuse(direct_vm, "NOT_PROPOSER", lambda: world.report_execution(pid, "ATTEMPTED", "x"))
    assert snapshot(world) == before
