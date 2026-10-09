"""Stage 4 acceptance fixtures: the whole lineage, asserted end to end (mocked LLM; real-model behaviour needs StudioNet)."""

import copy

from conftest import hex_of
from repair_support import NFT, ORIGINAL, REPAIRED, accept_repair, mock_repair, repair, repairable, review_revision, revision_hash_reference, two_targets, world  # noqa: F401
from review_support import findings_of, fnd, mock_review, review_of


def test_fixture_a_a_valid_repair_becomes_eligible(repairable, direct_vm, direct_alice):
    # Revision 1: open-source RPC gateway, 30,000 USDC, no budget breakdown. Review 1: REPAIRABLE, section 3 violated.
    r1 = review_of(repairable)
    assert r1["verdict"] == "REPAIRABLE" and r1["primary_section_id"] == "3"
    assert [(f["section_id"], f["finding"], f["repairable"]) for f in findings_of(repairable)] == [("1", "SATISFIED", False), ("2", "SATISFIED", False), ("3", "VIOLATED", True)]
    assert repairable.get_proposal(1)["status"] == "REPAIRABLE"
    original = copy.deepcopy(repairable.get_proposal(1))

    # Revision 2: same gateway with a 12k / 8k / 6k / 4k budget. The assessment is ADMISSIBLE.
    accept_repair(repairable, direct_vm)
    rev = repairable.get_proposal_revision(1)
    assert (rev["revision_number"], rev["parent_revision_id"], rev["source_review_id"], rev["charter_version"]) == (2, 0, 1, 4)
    assert rev["addressed_section_ids"] == ["3"] and rev["revision_hash"] == revision_hash_reference()
    assert repairable.get_proposal(1)["status"] == "REVISED"

    # Review 2 judges revision 2 and finds it ELIGIBLE.
    review_revision(repairable, direct_vm, [fnd("1"), fnd("2", ev=[1]), fnd("3")])
    r2 = repairable.get_review_for_revision(1)
    assert r2["verdict"] == "ELIGIBLE" and r2["review_id"] == 2 and repairable.get_review_revision_id(2) == 1
    assert repairable.get_proposal(1)["status"] == "ELIGIBLE"

    # The whole lineage, and nothing historical changed.
    assert [x["verdict"] for x in repairable.get_proposal_reviews_page(1, 0, 50)] == ["REPAIRABLE", "ELIGIBLE"]
    assert review_of(repairable) == r1
    assert {k: v for k, v in repairable.get_proposal(1).items() if k != "status"} == {k: v for k, v in original.items() if k != "status"}
    assert repairable.get_proposal(1)["description"] == ORIGINAL[1]
    assert repairable.get_effective_proposal(1)["description"] == REPAIRED[1]
    assert repairable.get_proposal_count() == 1 and repairable.get_evidence_count() == 1


def test_fixture_b_a_bad_repair_is_rejected_and_enters_no_history(repairable, direct_vm):
    before = copy.deepcopy(world(repairable))
    mock_repair(direct_vm, purpose=False, addressed=())  # an NFT gaming marketplace is not a repair of an RPC gateway
    with direct_vm.expect_revert("EXPECTED:REPAIR_REJECTED:PURPOSE_CHANGED"):
        repair(repairable, NFT)
    assert world(repairable) == before
    assert repairable.get_proposal_revision_count(1) == 0
    assert repairable.get_effective_proposal(1)["description"] == ORIGINAL[1]
    assert repairable.get_proposal(1)["status"] == "REPAIRABLE"  # still repairable: the proposer may try again
    direct_vm.clear_mocks()
    accept_repair(repairable, direct_vm)  # and a genuine repair afterwards is revision id 1
    assert repairable.get_proposal_revision(1)["revision_id"] == 1


def test_fixture_c_a_partial_repair_is_admitted_but_is_still_repairable(two_targets, direct_vm):
    assert [t["section_id"] for t in two_targets.get_repair_targets(1)] == ["2", "3"]
    accept_repair(two_targets, direct_vm, addressed=("3",))  # fixes the budget only
    assert two_targets.get_proposal_revision(1)["addressed_section_ids"] == ["3"]
    review_revision(two_targets, direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=True, rationale="Allocation still undisclosed."), fnd("3")])
    again = two_targets.get_review_for_revision(1)
    assert again["verdict"] == "REPAIRABLE"  # admission of the repair and compliance are different decisions
    assert two_targets.get_proposal(1)["status"] == "REPAIRABLE"
    assert [t["section_id"] for t in two_targets.get_repair_targets(1)] == ["2"]
    assert [x["verdict"] for x in two_targets.get_proposal_reviews_page(1, 0, 50)] == ["REPAIRABLE", "REPAIRABLE"]
    # the next repair continues the same linear lineage
    accept_repair(two_targets, direct_vm, ("Atlas RPC Gateway", REPAIRED[1] + " The team holds 18% of the token supply.", REPAIRED[2]), addressed=("2",))
    r2 = two_targets.get_proposal_revision(2)
    assert (r2["revision_number"], r2["parent_revision_id"], r2["source_review_id"]) == (3, 1, 2)
    review_revision(two_targets, direct_vm, [fnd("1"), fnd("2", ev=[1]), fnd("3")], 2)
    assert two_targets.get_proposal(1)["status"] == "ELIGIBLE"
    assert [x["verdict"] for x in two_targets.get_proposal_reviews_page(1, 0, 50)] == ["REPAIRABLE", "REPAIRABLE", "ELIGIBLE"]
