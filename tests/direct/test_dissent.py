"""Stage 6: reasoned dissent (acceptance fixture G and the bad dissent).

A reasoned dissent is an AI-generated, immutable, NON-CONTROLLING alternative reading of the same closed record. GenVM exposes no
authenticated validator-minority opinion to contract code, so nothing here pretends to be one. These tests prove the contract's own
rules: it must disagree materially, it never changes anything that controls, and a failure stores nothing."""

import copy
import json

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
    effective,
    findings,
    mock_dissent,
    propose,
    review,
    snapshot,
    world,  # noqa: F401  (fixture)
)
from review_support import mock_refs

INELIGIBLE_ALT = findings(s3="VIOLATED", s3_kw=dict(repairable=False, rationale="This omission cannot be cured by edits."))


@pytest.fixture
def decided(world, direct_vm):
    """Proposal 1: original REPAIRABLE, appeal AFFIRMED (REPAIRABLE controls)."""
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    return world, pid, rid, aid


# ---- Fixture G: a material dissent is stored and controls nothing -----------------------------------------------------------------------------


def test_fixture_g_a_material_dissent_is_stored_and_changes_nothing_that_controls(decided, direct_vm):
    world, pid, rid, aid = decided
    before = snapshot(world)
    ruling = effective(world, pid)
    decision = world.get_appellate_decision(aid)
    record = world.get_appeal_record(aid)
    review(world, direct_vm, propose(world), findings(**VIOLATED))  # unrelated activity before the dissent, for the index comparison
    index_before = world.get_rule_precedents_page("3@4", 0, 50)
    direct_vm.clear_mocks()
    dissent(world, direct_vm, aid, INELIGIBLE_ALT)
    x = world.get_reasoned_dissent(aid)
    assert (x["verdict"], x["disagreeing_section_ids"], x["appeal_id"]) == ("INELIGIBLE", ["3"], aid)
    assert [f["finding"] for f in x["findings"]] == ["SATISFIED", "SATISFIED", "VIOLATED"]
    assert x["findings"][2]["repairable"] is False
    # non-controlling: nothing that controls moved
    assert effective(world, pid) == ruling and ruling["effective_verdict"] == "REPAIRABLE"
    assert world.get_proposal(pid)["status"] == "REPAIRABLE"
    assert [t["section_id"] for t in world.get_repair_targets(pid)] == ["3"]
    assert world.get_appellate_decision(aid) == decision
    assert world.get_rule_precedents_page("3@4", 0, 50) == index_before  # not precedent
    after = world.get_appeal_record(aid)
    assert after["dissent"] == x and {k: v for k, v in after.items() if k != "dissent"} == {k: v for k, v in record.items() if k != "dissent"}
    assert snapshot(world)["reviews"][0] == before["reviews"][0] and snapshot(world)["findings"][0] == before["findings"][0]


def test_a_dissent_is_never_automatic_precedent(decided, direct_vm):
    world, pid, rid, aid = decided
    dissent(world, direct_vm, aid, INELIGIBLE_ALT)
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    p = world.get_review_precedents(2)
    assert [c["precedent_review_id"] for c in p["candidates"] if c["section_id"] == "3"] == [rid]
    assert world.get_review_count() == 2  # a dissent is not a review and has no review id


def test_the_repair_workflow_still_uses_the_controlling_decision_not_the_dissent(decided, direct_vm):
    from repair_support import mock_repair

    world, pid, rid, aid = decided
    dissent(world, direct_vm, aid, INELIGIBLE_ALT)  # the dissent says the violation is not repairable
    direct_vm.clear_mocks()
    mock_repair(direct_vm)
    world.submit_repair_revision(pid, *ITEMIZED)  # repair remains possible: the controlling verdict is REPAIRABLE
    assert world.get_proposal(pid)["status"] == "REVISED"


def test_a_dissent_does_not_prevent_or_change_a_later_reversal_view(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm, ITEMIZED)
    aid = appeal(world, direct_vm, rid, findings())  # REVERSED to ELIGIBLE
    dissent(world, direct_vm, aid, findings(s3="VIOLATED", s3_kw=dict(repairable=True, rationale="No itemized timeline.")))
    x = world.get_reasoned_dissent(aid)
    assert x["verdict"] == "REPAIRABLE"
    e = effective(world, pid)
    assert (e["effective_verdict"], e["decision_kind"]) == ("ELIGIBLE", "REVERSED")


# ---- the bad dissent: a reworded majority is not a dissent --------------------------------------------------------------------------------------


def test_a_reworded_majority_is_rejected_and_nothing_is_stored(decided, direct_vm):
    world, pid, rid, aid = decided
    before = snapshot(world)
    same = findings(s3="VIOLATED", s3_kw=dict(repairable=True, rationale="An entirely different way of saying the same thing."))
    direct_vm.clear_mocks()
    mock_dissent(direct_vm, same)
    with direct_vm.expect_revert("EXPECTED:NO_MATERIAL_DISSENT"):
        world.request_reasoned_dissent(aid)
    assert snapshot(world) == before
    assert world.get_appeal_record(aid)["dissent"] is None
    with direct_vm.expect_revert("EXPECTED:DISSENT_NOT_FOUND"):
        world.get_reasoned_dissent(aid)
    assert world.get_review_appeal_status(rid)["dissent_id"] == 0


def test_a_verdict_and_findings_the_model_volunteers_do_not_make_a_dissent(decided, direct_vm):
    world, pid, rid, aid = decided
    direct_vm.clear_mocks()
    mock_dissent(direct_vm, findings(**VIOLATED), raw={"findings": findings(**VIOLATED), "verdict": "INELIGIBLE", "disagreeing": ["3"]})
    with direct_vm.expect_revert("EXPECTED:NO_MATERIAL_DISSENT"):
        world.request_reasoned_dissent(aid)


@pytest.mark.parametrize(
    "alt",
    [
        findings(s2="VIOLATED", s2_kw=dict(repairable=True, rationale="x"), **VIOLATED),
        findings(s1="NOT_APPLICABLE", **VIOLATED),
        findings(s3="SATISFIED"),
    ],
    ids=["extra-violation", "different-class", "other-verdict"],
)
def test_any_material_section_difference_is_a_dissent(decided, direct_vm, alt):
    world, pid, rid, aid = decided
    dissent(world, direct_vm, aid, alt)
    x = world.get_reasoned_dissent(aid)
    assert len(x["disagreeing_section_ids"]) >= 1


def test_the_disagreeing_sections_are_derived_not_declared(decided, direct_vm):
    world, pid, rid, aid = decided
    dissent(world, direct_vm, aid, findings(s2="VIOLATED", s2_kw=dict(repairable=True, rationale="x"), s3="SATISFIED"))
    assert world.get_reasoned_dissent(aid)["disagreeing_section_ids"] == ["2", "3"]


# ---- atomicity -----------------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,code",
    [
        ("not json", "LLM_ERROR"),
        ({"findings": "nope"}, "LLM_ERROR:BAD_FINDINGS"),
        ({"findings": findings()[:2]}, "LLM_ERROR:BAD_FINDING_COVERAGE"),
        ({"findings": findings(s2_kw=dict(ev=[7]))}, "LLM_ERROR:BAD_EVIDENCE_REF"),
    ],
    ids=["unusable", "not-a-list", "missing-section", "unknown-evidence"],
)
def test_a_failed_dissent_stores_nothing(decided, direct_vm, raw, code):
    world, pid, rid, aid = decided
    before = snapshot(world)
    direct_vm.clear_mocks()
    mock_dissent(direct_vm, None, raw=raw)
    with direct_vm.expect_revert(code):
        world.request_reasoned_dissent(aid)
    assert snapshot(world) == before and world.get_appeal_record(aid)["dissent"] is None
    dissent(world, direct_vm, aid, INELIGIBLE_ALT)  # no id or slot was consumed: the same request now succeeds
    assert world.get_reasoned_dissent(aid)["dissent_id"] == 1


# ---- the dissent prompt: the same closed record, nothing later ---------------------------------------------------------------------------------


def test_the_dissent_prompt_carries_the_closed_record_and_the_controlling_decision_only(world, direct_vm, direct_owner, direct_alice):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED), statement="A SECRET APPEAL ARGUMENT")
    from precedent_support import add_verified_evidence

    add_verified_evidence(world, direct_vm, pid)  # late evidence
    direct_vm.sender = direct_owner
    world.update_charter_section("3", "Budget", "A newer wording of the budget rule.")
    direct_vm.sender = direct_alice
    direct_vm.clear_mocks()
    mock_dissent(
        direct_vm,
        INELIGIBLE_ALT,
        must=[
            r"A constitutional appeal has been decided\. You write a NON-CONTROLLING alternative",
            r"Your answer controls nothing",
            r"CHARTER IN FORCE AT SUBMISSION \(version 4\)",
            r"title: Atlas Docs\n",
            r"=== UNTRUSTED CONTROLLING APPELLATE DECISION \(it controls; you write a non-controlling alternative\) ===\n<<<DATA\nverdict: REPAIRABLE\nDATA>>>",
        ],
        must_not=[r"A SECRET APPEAL ARGUMENT", r"team_token_allocation", r"newer wording", r"PRECEDENT", r"historical_"],
    )
    world.request_reasoned_dissent(aid)
    assert world.get_reasoned_dissent(aid)["verdict"] == "INELIGIBLE"


# ---- validators --------------------------------------------------------------------------------------------------------------------------------------


def lead_dissent(world, vm, aid, alt, **kw):
    vm.clear_mocks()
    mock_dissent(vm, alt, **kw)
    world.request_reasoned_dissent(aid)
    stored = copy.deepcopy(vm._captured_validators[-1][0])
    vm.clear_mocks()
    return stored


def replay(vm, alt, *, leader_result=None, supported=True, raw=None, refs=()):
    vm.clear_mocks()
    mock_dissent(vm, alt, supported=supported, raw=raw)
    mock_refs(vm, refs)
    leader = leader_result if leader_result is not None else vm._captured_validators[-1][0]
    kw = {"leader_result": leader_result} if leader_result is not None else {}
    return vm.run_validator(**kw)


def test_a_validator_accepts_a_defensible_leader_dissent(decided, direct_vm):
    world, pid, rid, aid = decided
    lead_dissent(world, direct_vm, aid, INELIGIBLE_ALT)
    assert replay(direct_vm, INELIGIBLE_ALT, supported=True) is True


def test_a_validator_does_not_have_to_write_the_same_dissent(decided, direct_vm):
    world, pid, rid, aid = decided
    lead_dissent(world, direct_vm, aid, INELIGIBLE_ALT)
    other = findings(s2="VIOLATED", s2_kw=dict(repairable=True, rationale="x"), **VIOLATED)  # its own, different, alternative
    assert replay(direct_vm, other, supported=True) is True  # it checks the leader's, not its own


def test_a_validator_rejects_an_indefensible_leader_dissent(decided, direct_vm):
    world, pid, rid, aid = decided
    lead_dissent(world, direct_vm, aid, INELIGIBLE_ALT)
    assert replay(direct_vm, INELIGIBLE_ALT, supported=False) is False


def test_a_validator_rejects_a_leader_claim_of_no_dissent_when_its_own_pass_finds_one(decided, direct_vm):
    world, pid, rid, aid = decided
    # the leader reports "no material dissent"
    leader = lead_dissent_none(world, direct_vm, aid)
    assert leader["material"] is False
    assert replay(direct_vm, INELIGIBLE_ALT, leader_result=leader) is False  # the validator can write a defensible one
    assert replay(direct_vm, findings(**VIOLATED), leader_result=leader) is True  # the validator agrees there is none


def lead_dissent_none(world, vm, aid):
    vm.clear_mocks()
    mock_dissent(vm, findings(**VIOLATED))
    with vm.expect_revert("EXPECTED:NO_MATERIAL_DISSENT"):
        world.request_reasoned_dissent(aid)
    return copy.deepcopy(vm._captured_validators[-1][0])


def tamper(**changes):
    def apply(r):
        r.update(changes)

    return apply


TAMPERED = [
    ("wrong-appeal-id", tamper(appeal_id=99)),
    ("wrong-context-hash", tamper(context_hash="0x" + "ab" * 32)),
    ("wrong-decision-hash", tamper(decision_hash="0x" + "cd" * 32)),
    ("verdict-not-derived", tamper(verdict="ELIGIBLE")),
    ("claims-material-but-no-sections", tamper(disagreeing=[])),
    ("claims-extra-section", tamper(disagreeing=["1", "3"])),
    ("material-not-a-bool", tamper(material="yes")),
    ("extra-key", tamper(note="x")),
    ("findings-not-a-list", tamper(findings="nope")),
]


@pytest.mark.parametrize("mutate", [m for _n, m in TAMPERED], ids=[n for n, _m in TAMPERED])
def test_tampered_leader_dissents_are_rejected(decided, direct_vm, mutate):
    world, pid, rid, aid = decided
    stored = lead_dissent(world, direct_vm, aid, INELIGIBLE_ALT)
    mutate(stored)
    assert replay(direct_vm, INELIGIBLE_ALT, leader_result=stored) is False


def test_a_leader_dissent_that_is_not_materially_different_is_rejected_by_structure(decided, direct_vm):
    world, pid, rid, aid = decided
    stored = lead_dissent(world, direct_vm, aid, INELIGIBLE_ALT)
    stored["findings"][2].update(finding="VIOLATED", repairable=True)  # identical to the controlling decision now
    stored["verdict"], stored["disagreeing"] = "REPAIRABLE", ["3"]
    assert replay(direct_vm, INELIGIBLE_ALT, leader_result=stored) is False


def test_a_dissent_that_cites_evidence_outside_the_snapshot_is_rejected(decided, direct_vm):
    world, pid, rid, aid = decided
    stored = lead_dissent(world, direct_vm, aid, INELIGIBLE_ALT)
    stored["findings"][1].update(evidence_ids=[1])
    assert replay(direct_vm, INELIGIBLE_ALT, leader_result=stored) is False


def test_a_validator_checks_that_the_dissents_cited_evidence_materially_supports_it(world, direct_vm):
    from precedent_support import add_verified_evidence

    pid = propose(world)
    add_verified_evidence(world, direct_vm, pid)
    rid = review(world, direct_vm, pid, findings(s2_kw=dict(ev=[1]), **VIOLATED))
    aid = appeal(world, direct_vm, rid, findings(s2_kw=dict(ev=[1]), **VIOLATED), refs=[1])
    alt = findings(s2_kw=dict(ev=[1]), s3="VIOLATED", s3_kw=dict(repairable=False, rationale="Not curable."))
    lead_dissent(world, direct_vm, aid, alt)
    assert replay(direct_vm, alt, supported=True, refs=[1]) is True
    assert replay(direct_vm, alt, supported=True, refs=[]) is False  # the cited evidence does not support the alternative
