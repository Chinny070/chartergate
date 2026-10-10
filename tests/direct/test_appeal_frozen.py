"""Stage 6: an appeal judges the CLOSED record the original review judged (fixtures D, E and F), and its base adjudication never
sees precedent."""

import json

from appeal_support import (
    GROUND,
    ITEMIZED,
    NO_BREAKDOWN,
    STATEMENT,
    VIOLATED,
    adverse_review,
    appeal,
    findings,
    fnd,
    mock_appeal,
    propose,
    review,
    snapshot,
    world,  # noqa: F401  (fixture)
)
from precedent_support import add_verified_evidence, cite
from review_support import mock_refs

HISTORICAL = r"historical_|UNTRUSTED PRECEDENT CONTEXT|precedent_review_id|PRECEDENT CONSISTENCY"


# ---- Fixture D: the appeal cannot see late evidence ------------------------------------------------------------------------------------------


def test_fixture_d_evidence_submitted_after_the_review_never_enters_the_appeal(world, direct_vm):
    pid = propose(world)
    rid = review(world, direct_vm, pid, findings(s2="UNCLEAR"))  # no VERIFIED allocation evidence at review time
    assert world.get_constitutional_review(rid)["evidence_count_at_review"] == 0
    original = world.get_constitutional_review(rid)
    add_verified_evidence(world, direct_vm, pid)  # evidence #1 appears AFTER the review
    assert world.get_evidence(1)["status"] == "VERIFIED"
    direct_vm.clear_mocks()
    mock_appeal(
        direct_vm,
        findings(s2="UNCLEAR"),
        must=[r"=== UNTRUSTED EVIDENCE DATA: VERIFIED \(may support facts\) ===\n\(none\)\n"],
        must_not=[r"team_token_allocation", r"46%", r"evidence_id: 1"],
        refs=[],
    )
    world.request_appeal(rid, GROUND, STATEMENT)
    r = world.get_appeal_record(1)
    assert r["evidence_ids"] == [] and r["appeal"]["evidence_count"] == 0
    assert r["appeal"]["evidence_set_hash"] == original["evidence_set_hash"]  # the original snapshot hash is unchanged
    assert world.get_constitutional_review(rid) == original
    assert world.get_appellate_decision(1)["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_an_appellate_finding_cannot_cite_evidence_that_arrived_after_the_review(world, direct_vm):
    pid = propose(world)
    rid = review(world, direct_vm, pid, findings(s2="UNCLEAR"))
    add_verified_evidence(world, direct_vm, pid)
    direct_vm.clear_mocks()
    mock_appeal(direct_vm, findings(s2_kw=dict(ev=[1])), refs=[1])  # a model that "found" the late evidence
    with direct_vm.expect_revert("LLM_ERROR:BAD_EVIDENCE_REF"):
        world.request_appeal(rid, GROUND, STATEMENT)
    assert world.get_appeal_count() == 0


def test_evidence_in_the_original_snapshot_stays_available_to_the_appeal(world, direct_vm):
    pid = propose(world)
    add_verified_evidence(world, direct_vm, pid)
    rid = review(world, direct_vm, pid, findings(s2_kw=dict(ev=[1]), **VIOLATED))
    direct_vm.clear_mocks()
    mock_appeal(
        direct_vm,
        findings(s2_kw=dict(ev=[1]), **VIOLATED),
        must=[r"evidence_id: 1\nfact: team_token_allocation"],
        refs=[1],
    )
    world.request_appeal(rid, GROUND, STATEMENT)
    assert world.get_appeal_record(1)["evidence_ids"] == [1]


# ---- Fixture E: the appeal cannot see a new charter -----------------------------------------------------------------------------------------


def test_fixture_e_a_later_charter_never_enters_the_appeal(world, direct_vm, direct_owner, direct_alice):
    pid, rid = adverse_review(world, direct_vm)
    assert world.get_constitutional_review(rid)["charter_version"] == 4
    old_budget = world.get_charter_section("3")["body"]
    direct_vm.sender = direct_owner
    world.update_charter_section("3", "Budget", "Budget breakdowns are optional and never required.")
    world.add_charter_section("4", "Timeline", "Every proposal must state a delivery date.")
    world.update_charter_section("1", "Mission", "A completely different mission.")
    assert int(world.get_charter_version()) == 7
    direct_vm.sender = direct_alice
    direct_vm.clear_mocks()
    mock_appeal(
        direct_vm,
        findings(**VIOLATED),
        must=[
            r"CHARTER IN FORCE AT SUBMISSION \(version 4\)",
            r"\[section_id: 3\] Budget\nEvery funding proposal must contain a specific budget breakdown",
        ],
        must_not=[r"optional and never required", r"Timeline", r"completely different mission", r"section_id: 4"],
    )
    world.request_appeal(rid, GROUND, STATEMENT)
    a = world.get_appeal(1)
    assert a["charter_version"] == 4
    assert world.get_appellate_decision(1)["decision_kind"] == "AFFIRMED"
    assert old_budget != world.get_charter_section("3")["body"]  # the live charter did change; the appeal ignored it


def test_the_appeal_context_hash_binds_the_historical_section_revisions(world, direct_vm, direct_owner, direct_alice):
    """Amending a section later does not change the record, so the appeal still reconstructs and verifies it."""
    pid, rid = adverse_review(world, direct_vm)
    direct_vm.sender = direct_owner
    world.update_charter_section("3", "Budget", "A later wording.")
    direct_vm.sender = direct_alice
    appeal(world, direct_vm, rid, findings(**VIOLATED))
    assert world.get_appellate_decision(1)["appeal_context_hash"] != ""


# ---- Fixture F: the appeal uses the frozen precedent snapshot ---------------------------------------------------------------------------------


def build_frozen_precedent(world, vm):
    """Reviews 1 and 2 (A, B) are the original snapshot of review 3; reviews 4, 5, 6 (C, D, E) appear AFTERWARDS."""
    review(world, vm, propose(world), findings(**VIOLATED))
    review(world, vm, propose(world), findings(**VIOLATED))
    pid3 = propose(world)
    rid = review(world, vm, pid3, findings(**VIOLATED))
    for _ in range(3):
        review(world, vm, propose(world), findings(**VIOLATED))
    return pid3, rid


def test_fixture_f_the_appeal_sees_the_original_precedent_snapshot_and_nothing_later(world, direct_vm):
    pid, rid = build_frozen_precedent(world, direct_vm)
    original = world.get_review_precedents(rid)
    assert [c["precedent_review_id"] for c in original["candidates"] if c["section_id"] == "3"] == [2, 1]
    direct_vm.clear_mocks()
    mock_appeal(
        direct_vm,
        findings(**VIOLATED),
        must_not=[HISTORICAL],  # the BASE appellate adjudication never sees precedent
        pmust=[r"precedent_review_id: 2\n", r"precedent_review_id: 1\n"],
        pmust_not=[r"precedent_review_id: 4\n", r"precedent_review_id: 5\n", r"precedent_review_id: 6\n"],
    )
    world.request_appeal(rid, GROUND, STATEMENT)
    r = world.get_appeal_record(1)
    assert r["precedent_candidates"] == original["candidates"]  # exactly the frozen snapshot
    assert r["appeal"]["precedent_set_hash"] == original["precedent_set_hash"] != ""
    assert world.get_review_precedents(rid) == original  # the original snapshot itself is untouched


def test_citations_in_an_appellate_decision_must_come_from_the_frozen_snapshot(world, direct_vm):
    pid, rid = build_frozen_precedent(world, direct_vm)
    direct_vm.clear_mocks()
    mock_appeal(direct_vm, findings(**VIOLATED), cites=[{"section_id": "3", **cite(4, "FOLLOWED", "A later case.")}])
    with direct_vm.expect_revert("LLM_ERROR:BAD_PRECEDENT_REF"):
        world.request_appeal(rid, GROUND, STATEMENT)
    assert world.get_appeal_count() == 0
    direct_vm.clear_mocks()
    mock_appeal(direct_vm, findings(**VIOLATED), cites=[{"section_id": "3", **cite(2, "FOLLOWED", "Same omission.")}])
    world.request_appeal(rid, GROUND, STATEMENT)
    assert [c["precedent_review_id"] for c in world.get_appeal_record(1)["citations"]] == [2]


def test_a_zero_precedent_original_stays_a_zero_precedent_appellate_record(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)  # the first review ever: no candidates
    review(world, direct_vm, propose(world), findings(**VIOLATED))  # later cases exist...
    direct_vm.clear_mocks()
    # ...but only the base appellate prompt is mocked: a precedent pass or a citation check would find no mock and fail
    direct_vm.mock_llm(r"\A[\s\S]*CONSTITUTIONAL APPEAL", json.dumps({"findings": findings(**VIOLATED)}))
    world.request_appeal(rid, GROUND, STATEMENT)
    r = world.get_appeal_record(1)
    assert r["precedent_candidates"] == [] and r["citations"] == [] and r["appeal"]["precedent_set_hash"] == ""


def test_the_precedent_ground_is_available_only_when_the_original_saw_precedent(world, direct_vm):
    pid, rid = build_frozen_precedent(world, direct_vm)
    direct_vm.clear_mocks()
    mock_appeal(direct_vm, findings(**VIOLATED))
    world.request_appeal(rid, "PRECEDENT_MISAPPLICATION", "The prior rulings were applied wrongly.")
    assert world.get_appeal(1)["ground"] == "PRECEDENT_MISAPPLICATION"


# ---- the base appellate prompt: structure -------------------------------------------------------------------------------------------------------


def test_the_base_appellate_prompt_states_the_authority_rules_and_carries_the_closed_record(world, direct_vm):
    pid, rid = build_frozen_precedent(world, direct_vm)
    direct_vm.clear_mocks()
    mock_appeal(
        direct_vm,
        findings(**VIOLATED),
        must=[
            r"You must INDEPENDENTLY reconstruct the judgment from the CLOSED RECORD below",
            r"The original rationale is\nnot authority, and the appeal statement is not evidence\.",
            r"=== UNTRUSTED ORIGINAL JUDGMENT UNDER CHALLENGE \(not authority, not evidence\) ===\n<<<DATA\nverdict: REPAIRABLE\nDATA>>>",
            r"=== UNTRUSTED APPEAL \(the appellant's argument; not evidence\) ===\n<<<DATA\nground: CHARTER_MISINTERPRETATION\nstatement: ",
            r"title: Atlas Docs\n",
        ],
        must_not=[HISTORICAL, r"PRECEDENT", r"prior ruling"],
    )
    world.request_appeal(rid, GROUND, STATEMENT)
    assert world.get_appeal_count() == 1


# ---- an appeal of a revision review judges the exact revision ----------------------------------------------------------------------------------


def test_an_appeal_of_a_revision_review_judges_the_exact_revision_and_binds_it(world, direct_vm):
    from repair_support import mock_repair
    from review_support import mock_review as mock_rev
    from test_appeal_hash import appeal_hash, context_hash

    pid, first = adverse_review(world, direct_vm)
    direct_vm.clear_mocks()
    mock_repair(direct_vm)
    world.submit_repair_revision(pid, *ITEMIZED)
    direct_vm.clear_mocks()
    mock_rev(direct_vm, findings(s3="VIOLATED", s3_kw=dict(repairable=True, rationale="Still short.")))
    world.request_revision_review(1)
    second = int(world.get_review_count())
    assert world.get_review_revision_id(second) == 1
    direct_vm.clear_mocks()
    mock_appeal(
        direct_vm,
        findings(),
        must=[r"title: Atlas Gateway\n", r"Budget: 8000 USD engineering"],  # the revision text
        must_not=[r"We request 18000 USD in total\. "],  # not the original proposal text
    )
    world.request_appeal(second, GROUND, STATEMENT)
    a = world.get_appeal(1)
    assert a["revision_id"] == 1 and a["review_id"] == second
    assert a["appeal_hash"] == appeal_hash(a)
    assert world.get_appellate_decision(1)["appeal_context_hash"] == context_hash(a, world.get_constitutional_review(second))
    assert world.get_review_findings_page(first, 0, 50)[2]["finding"] == "VIOLATED"  # the first review is untouched


def test_repair_then_appeal_the_new_review_works_as_a_separate_branch_of_the_lineage(world, direct_vm):
    from repair_support import mock_repair
    from review_support import mock_review as mock_rev

    pid, first = adverse_review(world, direct_vm)
    direct_vm.clear_mocks()
    mock_repair(direct_vm)
    world.submit_repair_revision(pid, *ITEMIZED)
    direct_vm.clear_mocks()
    mock_rev(direct_vm, findings(s3="VIOLATED", s3_kw=dict(repairable=True, rationale="Still short.")))
    world.request_revision_review(1)
    second = int(world.get_review_count())
    assert world.get_review_appeal_status(first)["appealable"] is False  # obsolete
    assert world.get_review_appeal_status(second)["appealable"] is True
    appeal(world, direct_vm, second, findings())
    e = world.get_effective_ruling(pid)
    assert (e["review_id"], e["effective_verdict"], e["decision_kind"]) == (second, "ELIGIBLE", "REVERSED")
