"""Stage 5 acceptance fixtures A to F, asserted end to end (mocked LLM; real-model behaviour needs StudioNet)."""

import copy

from precedent_support import (
    ITEMIZED,
    NO_BREAKDOWN,
    VIOLATED,
    add_verified_evidence,
    candidates_for,
    cite,
    findings,
    precedent_set_hash_reference,
    precedents_of,
    propose,
    review,
    world,  # noqa: F401  (fixture)
)
from repair_support import mock_repair
from review_support import findings_of, mock_review, request, review_of
from test_precedent_hash import context_v1, context_v3, result_hash


def test_fixture_a_followed_precedent(world, direct_vm):
    # Case A: no budget breakdown -> VIOLATED / repairable (review 1)
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    # Case B: materially the same omission
    case_b = propose(world, ("Atlas Indexer", "Atlas Indexer is an open-source blockchain indexer. We request 24000 USD in total.", "Grant 24000 USD"))
    direct_vm.clear_mocks()
    mock_review(direct_vm, findings(precedents={"3": [cite(1, "FOLLOWED", "The same omission as review 1.")]}, **VIOLATED))
    request(world, case_b)
    p = precedents_of(world, 2)
    assert candidates_for(world, 2, "3") == [1]  # Case A is in Case B's candidate snapshot
    assert [(c["section_id"], c["precedent_review_id"], c["treatment"]) for c in p["citations"]] == [("3", 1, "FOLLOWED")]
    f3 = findings_of(world, 2)[2]
    assert (f3["finding"], f3["repairable"]) == ("VIOLATED", True)  # the current finding remains VIOLATED / repairable
    r = world.get_constitutional_review(2)
    assert p["precedent_set_hash"] == precedent_set_hash_reference(world, 2)
    assert r["review_context_hash"] == context_v3(context_v1(world, 2), p["precedent_set_hash"])
    assert r["review_hash"] == result_hash(r["review_context_hash"], "REPAIRABLE", findings_of(world, 2), p["citations"])
    assert world.get_rule_precedents_page("3@4", 0, 50) == [1, 2]  # both are now in the index


def test_fixture_b_distinguished_precedent(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))  # prior: no budget breakdown -> VIOLATED
    current = propose(world, ITEMIZED)  # current: a complete itemized budget
    direct_vm.clear_mocks()
    mock_review(direct_vm, findings(precedents={"3": [cite(1, "DISTINGUISHED", "The current proposal itemizes every cost category.")]}))
    request(world, current)
    assert findings_of(world, 2)[2]["finding"] == "SATISFIED"
    assert precedents_of(world, 2)["citations"][0]["treatment"] == "DISTINGUISHED"
    assert review_of(world, current)["verdict"] == "ELIGIBLE"  # decided by the CURRENT case facts, not by the precedent's authority


def test_fixture_c_an_amended_rule_is_excluded(world, direct_vm, direct_owner, direct_alice):
    review(world, direct_vm, propose(world), findings(**VIOLATED))  # judged under s3 revision 4
    direct_vm.sender = direct_owner
    world.update_charter_section("3", "Budget", "Budget breakdowns are optional.")  # s3 revision 5
    direct_vm.sender = direct_alice
    case_b = propose(world, ITEMIZED)
    review(world, direct_vm, case_b, findings())
    assert candidates_for(world, 2, "3") == []  # same section_id, different rule revision: NOT in the snapshot
    assert candidates_for(world, 2, "1") == [1]  # rules that did not change still carry precedent
    assert world.get_rule_precedent_count("3@4") == 1 and world.get_rule_precedent_count("3@5") == 1


def test_fixture_d_precedent_is_not_evidence(world, direct_vm):
    prior = propose(world)
    add_verified_evidence(world, direct_vm, prior)  # the prior case has VERIFIED evidence: team allocation 46%
    review(world, direct_vm, prior, findings(s2_kw=dict(ev=[1])))
    current = propose(world, ITEMIZED)  # the current case has NO evidence for the same requirement
    direct_vm.clear_mocks()
    mock_review(direct_vm, findings(s2="UNCLEAR"), must=[r"=== UNTRUSTED EVIDENCE DATA: VERIFIED \(may support facts\) ===\n\(none\)\n"])
    request(world, current)
    f2 = findings_of(world, 2)[1]
    assert f2["finding"] == "UNCLEAR" and f2["evidence_ids"] == []  # not SATISFIED just because the prior case had the fact
    assert review_of(world, current)["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_fixture_e_snapshot_immutability(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))  # review A
    case_b = propose(world, ITEMIZED)
    direct_vm.clear_mocks()
    mock_review(direct_vm, findings(precedents={"3": [cite(1, "DISTINGUISHED", "Itemized.")]}))
    request(world, case_b)  # review B: precedent set = [review A]
    before = copy.deepcopy((precedents_of(world, 2), world.get_constitutional_review(2), findings_of(world, 2)))
    assert candidates_for(world, 2, "3") == [1]
    review(world, direct_vm, propose(world), findings())  # review C
    review(world, direct_vm, propose(world), findings())  # review D
    after = (precedents_of(world, 2), world.get_constitutional_review(2), findings_of(world, 2))
    assert after == before
    assert candidates_for(world, 4, "3") == [3, 2]  # later reviews have their OWN, newer snapshots


def test_fixture_f_the_same_lineage_is_excluded(world, direct_vm):
    proposal_p = propose(world)
    review(world, direct_vm, proposal_p, findings(**VIOLATED))  # review A: revision 1
    mock_repair(direct_vm)
    world.submit_repair_revision(proposal_p, *ITEMIZED)
    direct_vm.clear_mocks()
    mock_review(direct_vm, findings())
    world.request_revision_review(1)  # review B: revision 2 of the same proposal
    assert precedents_of(world, 2)["candidates"] == []  # review A is NOT external precedent for review B
    assert world.get_review_revision_id(2) == 1 and world.get_proposal_review_count(proposal_p) == 2  # its history is the Stage 4 lineage
    other = propose(world, ITEMIZED)
    review(world, direct_vm, other, findings())
    assert candidates_for(world, 3, "3") == [2, 1]  # but both ARE precedent for a different proposal
