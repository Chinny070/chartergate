"""Stage 6: appellate semantics (acceptance fixtures A, B, C), deterministic verdict and disposition, effective verdict,
repair / appeal interaction and precedent behavior after an appeal."""

import pytest

from appeal_support import (
    GROUND,
    ITEMIZED,
    NO_BREAKDOWN,
    STATEMENT,
    VIOLATED,
    adverse_review,
    appeal,
    effective,
    findings,
    fnd,
    mock_appeal,
    propose,
    review,
    snapshot,
    world,  # noqa: F401  (fixture)
)
from precedent_support import cite
from repair_support import mock_repair
from review_support import mock_review, request

TWO_VIOLATIONS = dict(s2="VIOLATED", s2_kw=dict(repairable=True, rationale="No allocation disclosed."), **VIOLATED)


# ---- Fixture A: AFFIRMED --------------------------------------------------------------------------------------------------------------


def test_fixture_a_a_correct_ruling_is_affirmed_and_the_original_is_untouched(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    before = snapshot(world)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    d = world.get_appellate_decision(aid)
    assert (d["verdict"], d["decision_kind"]) == ("REPAIRABLE", "AFFIRMED")
    assert snapshot(world) == before  # the original review, its findings, hashes, snapshots, evidence and charter: state for state
    assert world.get_appeal_id_for_review(rid) == aid
    e = effective(world, pid)
    assert (e["effective_verdict"], e["original_verdict"], e["decision_kind"], e["controlled_by"]) == ("REPAIRABLE", "REPAIRABLE", "AFFIRMED", "APPELLATE_DECISION")


def test_repair_remains_available_after_an_affirmed_appeal(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    appeal(world, direct_vm, rid, findings(**VIOLATED))
    assert [t["section_id"] for t in world.get_repair_targets(pid)] == ["3"]
    direct_vm.clear_mocks()
    mock_repair(direct_vm)
    world.submit_repair_revision(pid, *ITEMIZED)
    assert world.get_proposal(pid)["status"] == "REVISED"
    assert world.get_review_findings_page(rid, 0, 50)[2]["finding"] == "VIOLATED"  # the original is still what it was


# ---- Fixture B: REVERSED to ELIGIBLE ------------------------------------------------------------------------------------------------------


def test_fixture_b_a_wrong_ruling_is_reversed_and_both_judgments_stay_visible(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm, ITEMIZED)  # the proposal DOES itemize its budget, the mocked original is wrong
    aid = appeal(world, direct_vm, rid, findings())
    d = world.get_appellate_decision(aid)
    assert (d["verdict"], d["decision_kind"]) == ("ELIGIBLE", "REVERSED")
    assert world.get_constitutional_review(rid)["verdict"] == "REPAIRABLE"  # historical
    assert world.get_review_findings_page(rid, 0, 50)[2]["finding"] == "VIOLATED"
    e = effective(world, pid)
    assert (e["original_verdict"], e["effective_verdict"], e["decision_kind"]) == ("REPAIRABLE", "ELIGIBLE", "REVERSED")
    assert [f["finding"] for f in e["findings"]] == ["SATISFIED"] * 3  # the controlling findings are the appellate ones
    assert world.get_proposal(pid)["status"] == "ELIGIBLE"
    assert world.get_repair_targets(pid) == []


def test_a_reversed_to_eligible_proposal_cannot_be_repaired_or_appealed_again(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm, ITEMIZED)
    aid = appeal(world, direct_vm, rid, findings())
    with direct_vm.expect_revert("EXPECTED:REPAIR_NOT_ALLOWED"):
        mock_repair(direct_vm)
        world.submit_repair_revision(pid, "Atlas Gateway v2", ITEMIZED[1] + " Plus more detail.", ITEMIZED[2])
    with direct_vm.expect_revert("EXPECTED:APPEAL_ALREADY_EXISTS"):
        world.request_appeal(rid, GROUND, STATEMENT)
    assert aid == 1


# ---- the opposite direction: an appeal is adjudication, not a guaranteed benefit ----------------------------------------------------------------


def test_an_appeal_can_make_things_worse_repairable_to_ineligible_and_then_no_repair_is_possible(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(s3="VIOLATED", s3_kw=dict(repairable=False, rationale="Not curable.")))
    d = world.get_appellate_decision(aid)
    assert (d["verdict"], d["decision_kind"]) == ("INELIGIBLE", "REVERSED")
    assert world.get_constitutional_review(rid)["verdict"] == "REPAIRABLE"
    assert effective(world, pid)["effective_verdict"] == "INELIGIBLE"
    assert world.get_repair_targets(pid) == []
    direct_vm.clear_mocks()
    mock_repair(direct_vm)
    with direct_vm.expect_revert("EXPECTED:REPAIR_NOT_ALLOWED"):
        world.submit_repair_revision(pid, *ITEMIZED)


def test_an_insufficient_evidence_ruling_can_be_appealed(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm, NO_BREAKDOWN, findings(s2="UNCLEAR"))
    assert world.get_constitutional_review(rid)["verdict"] == "INSUFFICIENT_EVIDENCE"
    aid = appeal(world, direct_vm, rid, findings(s2="UNCLEAR"), refs=[])
    assert world.get_appellate_decision(aid)["decision_kind"] == "AFFIRMED"


def test_an_ineligible_ruling_can_be_appealed_and_reversed_to_repairable(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm, NO_BREAKDOWN, findings(s3="VIOLATED", s3_kw=dict(repairable=False, rationale="x")))
    assert world.get_constitutional_review(rid)["verdict"] == "INELIGIBLE"
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    d = world.get_appellate_decision(aid)
    assert (d["verdict"], d["decision_kind"]) == ("REPAIRABLE", "REVERSED")
    assert effective(world, pid)["effective_verdict"] == "REPAIRABLE"
    assert [t["section_id"] for t in world.get_repair_targets(pid)] == ["3"]  # now repairable, targets from the appellate findings


# ---- Fixture C: MODIFIED ------------------------------------------------------------------------------------------------------------------


def test_fixture_c_a_partly_wrong_ruling_is_modified_and_repair_targets_follow_the_appellate_findings(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm, NO_BREAKDOWN, findings(**TWO_VIOLATIONS))
    assert [t["section_id"] for t in world.get_repair_targets(pid)] == ["2", "3"]
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))  # section 2 was wrongly flagged; section 3 is a real violation
    d = world.get_appellate_decision(aid)
    assert (d["verdict"], d["decision_kind"]) == ("REPAIRABLE", "MODIFIED")  # same verdict, different material findings
    assert [t["section_id"] for t in world.get_repair_targets(pid)] == ["3"]  # the stale, overturned section-2 target is gone
    assert [f["section_id"] for f in world.get_review_findings_page(rid, 0, 50) if f["finding"] == "VIOLATED"] == ["2", "3"]  # historical


def test_repair_admission_uses_the_appellate_targets(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm, NO_BREAKDOWN, findings(**TWO_VIOLATIONS))
    appeal(world, direct_vm, rid, findings(**VIOLATED))
    direct_vm.clear_mocks()
    mock_repair(
        direct_vm,
        addressed=("3",),
        must=[r"section_id: 3"],
        must_not=[r"section_id: 2\n"],  # section 2 is no longer a target
    )
    world.submit_repair_revision(pid, *ITEMIZED)
    assert world.get_proposal_revision(1)["source_review_id"] == rid


def test_a_repairability_change_alone_is_a_modification(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm, NO_BREAKDOWN, findings(**TWO_VIOLATIONS))
    aid = appeal(world, direct_vm, rid, findings(s2="VIOLATED", s2_kw=dict(repairable=False, rationale="x"), s3="VIOLATED", s3_kw=dict(repairable=False, rationale="x")))
    assert world.get_appellate_decision(aid)["decision_kind"] == "REVERSED"  # a nonrepairable violation changes the verdict
    pid2, rid2 = adverse_review(world, direct_vm, ITEMIZED, findings(s3="VIOLATED", s3_kw=dict(repairable=False, rationale="x"), s2="VIOLATED", s2_kw=dict(repairable=True, rationale="y")))
    aid2 = appeal(world, direct_vm, rid2, findings(s3="VIOLATED", s3_kw=dict(repairable=False, rationale="x"), s2="SATISFIED"))
    assert world.get_appellate_decision(aid2)["decision_kind"] == "MODIFIED"  # still INELIGIBLE, but section 2 changed class


# ---- the verdict and the disposition are deterministic: the model supplies neither ---------------------------------------------------------------


def test_a_model_that_volunteers_a_verdict_or_a_disposition_is_ignored(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    direct_vm.clear_mocks()
    mock_appeal(direct_vm, findings(**VIOLATED), extra={"verdict": "ELIGIBLE", "decision_kind": "REVERSED", "precedents": "x"})
    world.request_appeal(rid, GROUND, STATEMENT)
    d = world.get_appellate_decision(1)
    assert (d["verdict"], d["decision_kind"]) == ("REPAIRABLE", "AFFIRMED")


@pytest.mark.parametrize(
    "fs,verdict,kind",
    [
        (findings(), "ELIGIBLE", "REVERSED"),
        (findings(s2="UNCLEAR"), "INSUFFICIENT_EVIDENCE", "REVERSED"),
        (findings(s3="NOT_APPLICABLE"), "ELIGIBLE", "REVERSED"),
        (findings(**VIOLATED), "REPAIRABLE", "AFFIRMED"),
    ],
    ids=["satisfied", "unclear", "not-applicable", "violated"],
)
def test_the_appellate_verdict_follows_the_stage_3_derivation(world, direct_vm, fs, verdict, kind):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, fs, refs=[])
    d = world.get_appellate_decision(aid)
    assert (d["verdict"], d["decision_kind"]) == (verdict, kind)


# ---- the closed appellate record is exposed in one bounded read -------------------------------------------------------------------------------


def test_the_appeal_record_is_one_read_and_binds_the_original(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    r = world.get_appeal_record(aid)
    original = world.get_constitutional_review(rid)
    assert r["appeal"]["original_review_hash"] == original["review_hash"]
    assert r["appeal"]["evidence_set_hash"] == original["evidence_set_hash"]
    assert r["appeal"]["charter_version"] == original["charter_version"]
    assert r["appeal"]["ground"] == GROUND and r["appeal"]["statement"] == STATEMENT
    assert r["review"] == original
    assert [f["finding"] for f in r["original_findings"]] == ["SATISFIED", "SATISFIED", "VIOLATED"]
    assert r["dissent"] is None and r["citations"] == [] and r["precedent_candidates"] == []
    assert world.get_review_appeal_status(rid)["appeal_id"] == aid and world.get_review_appeal_status(rid)["appealable"] is False


# ---- precedent after an appeal --------------------------------------------------------------------------------------------------------------


def candidates(c, review_id, section="3"):
    return [x["precedent_review_id"] for x in c.get_review_precedents(review_id)["candidates"] if x["section_id"] == section]


def test_an_affirmed_review_remains_automatic_precedent(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    appeal(world, direct_vm, rid, findings(**VIOLATED))
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    assert candidates(world, 2) == [rid]


@pytest.mark.parametrize(
    "appellate",
    [findings(), findings(s2="VIOLATED", s2_kw=dict(repairable=True, rationale="x"), **VIOLATED)],
    ids=["reversed", "modified"],
)
def test_a_modified_or_reversed_review_is_excluded_from_future_precedent_but_stays_in_history(world, direct_vm, appellate):
    pid, rid = adverse_review(world, direct_vm)
    appeal(world, direct_vm, rid, appellate)
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    assert candidates(world, 2) == []  # no longer a candidate
    assert world.get_rule_precedents_page("3@4", 0, 50) == [1, 2]  # the index (audit history) still lists it
    assert world.get_precedent_case(rid, "3")["finding"]["finding"] == "VIOLATED"  # and it is still inspectable


def test_excluding_one_review_lets_the_next_older_review_fill_the_slot(world, direct_vm):
    _, first = adverse_review(world, direct_vm)
    _, second = adverse_review(world, direct_vm)
    appeal(world, direct_vm, second, findings())  # reversed: the second review stops being precedent
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    assert candidates(world, 3) == [first]
