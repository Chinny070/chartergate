"""Stage 5 precedent index: rule identity, deterministic bounded candidate selection, snapshots, atomicity."""

import copy

import pytest

from conftest import MISSION, TRANSPARENCY
from precedent_support import (
    BUDGET,
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
from review_support import fnd, mock_review, request


# ---- the first case under a rule has no precedent ---------------------------------------------------------------


def test_the_first_review_has_no_precedent_context_and_keeps_the_old_formats(world, direct_vm):
    pid = propose(world)
    mock_review(direct_vm, findings(**VIOLATED), pmust_not=["PRECEDENT"])  # the prompt is byte-for-byte the Stage 3 prompt
    request(world, pid)
    p = precedents_of(world, 1)
    assert p == {"review_id": 1, "precedent_set_hash": "", "candidates": [], "citations": []}


def test_every_finished_review_enters_the_index_under_each_exact_rule(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    assert [world.get_rule_precedent_count(r) for r in ("1@2", "2@3", "3@4")] == [1, 1, 1]
    assert world.get_rule_precedents_page("3@4", 0, 50) == [1]
    assert world.get_rule_precedent_count("3@5") == 0 and world.get_rule_precedent_count("9@2") == 0
    review(world, direct_vm, propose(world, ITEMIZED), findings())
    assert world.get_rule_precedents_page("3@4", 0, 50) == [1, 2]
    assert world.get_rule_precedents_page("3@4", 1, 1) == [2]


def test_all_finding_classes_become_history(world, direct_vm):
    review(world, direct_vm, propose(world), [fnd("1", "NOT_APPLICABLE"), fnd("2", "UNCLEAR"), fnd("3", "VIOLATED", repairable=False)])
    pid = propose(world, ITEMIZED)
    direct_vm.clear_mocks()
    mock_review(
        direct_vm,
        findings(),
        pmust=[r"historical_finding: NOT_APPLICABLE", r"historical_finding: UNCLEAR", r"historical_finding: VIOLATED\n"],
    )
    request(world, pid)
    assert [x["section_id"] for x in precedents_of(world, 2)["candidates"]] == ["1", "2", "3"]


# ---- a later review sees the earlier one --------------------------------------------------------------------------


def test_a_later_review_sees_earlier_reviews_under_the_same_rule(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    p = precedents_of(world, 2)
    assert [(x["section_id"], x["rule"], x["precedent_review_id"]) for x in p["candidates"]] == [("1", "1@2", 1), ("2", "2@3", 1), ("3", "3@4", 1)]
    assert p["precedent_set_hash"] == precedent_set_hash_reference(world, 2) != ""
    # the review hash of the precedent is recorded, so the relationship is unambiguous
    assert all(x["precedent_review_hash"] == world.get_constitutional_review(1)["review_hash"] for x in p["candidates"])


def test_the_prompt_lists_the_precedent_as_untrusted_data_with_the_same_rule(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    pid = propose(world, ITEMIZED)
    mock_review(
        direct_vm,
        findings(),
        pmust=[
            r"=== UNTRUSTED PRECEDENT CONTEXT: prior rulings under the SAME charter rule\. Advisory only; NOT evidence about this case ===",
            r"<<<DATA\nsection_id: 3\nrule: 3@4\nprecedent_review_id: 1\nhistorical_verdict: REPAIRABLE\nhistorical_finding: VIOLATED \(repairable\)\n",
            r"historical_proposal_title: Atlas Docs\n",
            r"restate them\. You only annotate how they relate to earlier rulings of this DAO under the SAME charter rule",
        ],
    )
    request(world, pid)


# ---- exact rule identity: an amended rule is a different rule ------------------------------------------------------


def test_an_amended_rule_is_not_precedent_for_the_new_wording(world, direct_vm, direct_owner, direct_alice):
    review(world, direct_vm, propose(world), findings(**VIOLATED))  # judged under 3@4
    direct_vm.sender = direct_owner
    world.update_charter_section("3", "Budget", "Budget breakdowns are optional.")  # s3 becomes revision 5
    direct_vm.sender = direct_alice
    pid = propose(world, ITEMIZED)  # submitted under v5
    review(world, direct_vm, pid, findings())
    p = precedents_of(world, 2)
    assert candidates_for(world, 2, "3") == []  # same section id, different rule revision
    assert candidates_for(world, 2, "1") == [1] and candidates_for(world, 2, "2") == [1]  # untouched rules still carry precedent
    assert world.get_rule_precedent_count("3@5") == 1 and world.get_rule_precedent_count("3@4") == 1


def test_a_proposal_submitted_before_the_amendment_is_still_judged_under_the_old_rule(world, direct_vm, direct_owner, direct_alice):
    first = propose(world)
    second = propose(world, ITEMIZED)  # both submitted under v4
    review(world, direct_vm, first, findings(**VIOLATED))
    direct_vm.sender = direct_owner
    world.update_charter_section("3", "Budget", "Budget breakdowns are optional.")
    direct_vm.sender = direct_alice
    review(world, direct_vm, second, findings())  # reviewed AFTER the amendment, but under the v4 rule
    assert candidates_for(world, 2, "3") == [1]


def test_the_prompt_never_shows_the_amended_rules_old_ruling(world, direct_vm, direct_owner, direct_alice):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    direct_vm.sender = direct_owner
    world.update_charter_section("3", "Budget", "Budget breakdowns are optional.")
    direct_vm.sender = direct_alice
    pid = propose(world, ITEMIZED)
    mock_review(direct_vm, findings(), pmust=[r"section_id: 1\nrule: 1@2"], pmust_not=[r"section_id: 3\nrule: 3@4", r"rule: 3@4"])
    request(world, pid)


# ---- the proposal's own lineage is excluded ------------------------------------------------------------------------


def test_a_proposals_own_earlier_reviews_are_not_external_precedent(world, direct_vm):
    first = propose(world)
    review(world, direct_vm, first, findings(**VIOLATED))
    direct_vm.clear_mocks()
    from repair_support import mock_repair

    mock_repair(direct_vm)
    world.submit_repair_revision(first, ITEMIZED[0], ITEMIZED[1], ITEMIZED[2])
    direct_vm.clear_mocks()
    mock_review(direct_vm, findings(), pmust_not=["PRECEDENT"])  # review 1 is the same lineage: no candidates, no precedent block
    world.request_revision_review(1)
    assert precedents_of(world, 2) == {"review_id": 2, "precedent_set_hash": "", "candidates": [], "citations": []}
    assert world.get_review_revision_id(2) == 1  # Stage 4 lineage stays visible separately


def test_a_revision_review_of_another_proposal_can_become_precedent(world, direct_vm):
    from repair_support import mock_repair

    first = propose(world)
    review(world, direct_vm, first, findings(**VIOLATED))
    mock_repair(direct_vm)
    world.submit_repair_revision(first, ITEMIZED[0], ITEMIZED[1], ITEMIZED[2])
    direct_vm.clear_mocks()
    mock_review(direct_vm, findings())
    world.request_revision_review(1)  # review 2 judges the REVISION of proposal 1
    direct_vm.clear_mocks()
    other = propose(world, ITEMIZED)
    mock_review(direct_vm, findings(), pmust=[r"precedent_review_id: 2\n", r"historical_proposal_description: Atlas Gateway is an open-source RPC gateway\. Budget"])
    request(world, other)
    assert candidates_for(world, 3, "3") == [2, 1]  # newest first; both come from OTHER lineages' point of view


# ---- bounded, deterministic, newest first ----------------------------------------------------------------------------


def test_at_most_two_candidates_per_section_newest_first(world, direct_vm):
    for _ in range(4):
        review(world, direct_vm, propose(world), findings())
    assert candidates_for(world, 4, "3") == [3, 2]  # not [3, 2, 1]
    review(world, direct_vm, propose(world), findings())
    assert candidates_for(world, 5, "3") == [4, 3]
    assert len(precedents_of(world, 5)["candidates"]) == 6  # 2 per section x 3 sections


def test_candidates_are_grouped_by_section_in_charter_order(world, direct_vm):
    for _ in range(3):
        review(world, direct_vm, propose(world), findings())
    sections = [x["section_id"] for x in precedents_of(world, 3)["candidates"]]
    assert sections == ["1", "1", "2", "2", "3", "3"]


def test_the_maximum_is_twenty_four_candidates_for_twelve_sections(charter, direct_vm, direct_alice):
    for i in range(12):
        charter.add_charter_section(f"r{i}", f"Rule {i}", "short rule")
    direct_vm.sender = direct_alice
    for _ in range(3):
        charter.submit_proposal(*NO_BREAKDOWN)
        direct_vm.clear_mocks()
        mock_review(direct_vm, [fnd(f"r{i}") for i in range(12)])
        request(charter, int(charter.get_proposal_count()))
    assert len(precedents_of(charter, 3)["candidates"]) == 24
    assert len(precedents_of(charter, 2)["candidates"]) == 12


def test_repeated_construction_gives_the_identical_snapshot_and_order(world, direct_vm):
    for _ in range(3):
        review(world, direct_vm, propose(world), findings())
    pid = propose(world)
    direct_vm.clear_mocks()
    mock_review(direct_vm, None, raw="not json")  # the first attempt fails and writes nothing
    with direct_vm.expect_revert("LLM_ERROR:MALFORMED_JSON"):
        request(world, pid)
    assert world.get_rule_precedent_count("3@4") == 3
    direct_vm.clear_mocks()
    mock_review(direct_vm, findings(), pmust=[r"precedent_review_id: 3\n[\s\S]*precedent_review_id: 2\n"])  # newest first, in the prompt
    request(world, pid)
    first = precedents_of(world, 4)
    assert first["precedent_set_hash"] == precedent_set_hash_reference(world, 4)
    assert [x["precedent_review_id"] for x in first["candidates"] if x["section_id"] == "3"] == [3, 2]


# ---- the snapshot never changes, a review never sees itself --------------------------------------------------------------


def test_a_review_is_not_in_its_own_snapshot(world, direct_vm):
    review(world, direct_vm, propose(world), findings())
    review(world, direct_vm, propose(world), findings())
    assert all(x["precedent_review_id"] != 2 for x in precedents_of(world, 2)["candidates"])
    assert all(x["precedent_review_id"] < 2 for x in precedents_of(world, 2)["candidates"])


def test_later_reviews_never_change_an_earlier_snapshot(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    b = review(world, direct_vm, propose(world, ITEMIZED), findings(precedents={"3": [cite(1, "DISTINGUISHED", "This proposal itemizes its budget.")]}))
    before = (copy.deepcopy(precedents_of(world, b)), copy.deepcopy(world.get_constitutional_review(b)), copy.deepcopy(world.get_review_findings_page(b, 0, 50)))
    for _ in range(3):
        review(world, direct_vm, propose(world), findings())
    after = (precedents_of(world, b), world.get_constitutional_review(b), world.get_review_findings_page(b, 0, 50))
    assert after == before
    assert before[0]["candidates"][-1]["precedent_review_id"] == 1  # still [review 1] for section 3
    assert before[0]["citations"][0]["treatment"] == "DISTINGUISHED"


# ---- atomicity ---------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,code",
    [("not json", "MALFORMED_JSON"), ({"findings": [fnd("1")]}, "BAD_FINDING_COVERAGE")],
    ids=["malformed", "incomplete"],
)
def test_a_failed_review_creates_no_index_slot_and_no_precedent_state(world, direct_vm, raw, code):
    import json

    review(world, direct_vm, propose(world), findings())
    pid = propose(world)
    before = [world.get_rule_precedent_count(r) for r in ("1@2", "2@3", "3@4")]
    mock_review(direct_vm, None, raw=raw if isinstance(raw, str) else json.dumps(raw))
    with direct_vm.expect_revert("LLM_ERROR:" + code):
        request(world, pid)
    assert [world.get_rule_precedent_count(r) for r in ("1@2", "2@3", "3@4")] == before
    assert world.get_review_count() == 1
    with direct_vm.expect_revert("EXPECTED:REVIEW_NOT_FOUND"):
        world.get_review_precedents(2)


def test_a_review_rejected_for_a_bad_precedent_citation_is_not_indexed(world, direct_vm):
    review(world, direct_vm, propose(world), findings())
    pid = propose(world)
    direct_vm.clear_mocks()
    mock_review(direct_vm, findings(precedents={"3": [cite(99)]}))
    with direct_vm.expect_revert("LLM_ERROR:BAD_PRECEDENT_REF"):
        request(world, pid)
    assert world.get_rule_precedent_count("3@4") == 1 and world.get_review_count() == 1


# ---- reads -----------------------------------------------------------------------------------------------------------------------


def test_the_index_and_case_reads_are_bounded_and_typed(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    with direct_vm.expect_revert("EXPECTED:PAGE_LIMIT_TOO_LARGE"):
        world.get_rule_precedents_page("3@4", 0, 51)
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:rule"):
        world.get_rule_precedent_count(3)
    with direct_vm.expect_revert("EXPECTED:FINDING_NOT_FOUND"):
        world.get_precedent_case(1, "9")
    with direct_vm.expect_revert("EXPECTED:REVIEW_NOT_FOUND"):
        world.get_precedent_case(9, "3")
    case = world.get_precedent_case(1, "3")
    assert case["rule"] == "3@4" and case["finding"]["finding"] == "VIOLATED" and case["review"]["review_id"] == 1
    assert (case["title"], case["revision_number"], case["revision_id"]) == (NO_BREAKDOWN[0], 1, 0)
    assert case["evidence"] == []


def test_the_case_read_carries_the_findings_own_evidence_only(world, direct_vm):
    pid = propose(world)
    add_verified_evidence(world, direct_vm, pid)
    review(world, direct_vm, pid, findings(s2_kw=dict(ev=[1])))
    case = world.get_precedent_case(1, "2")
    assert [e["evidence_id"] for e in case["evidence"]] == [1] and case["evidence"][0]["normalized_fact"] == "team_token_allocation"
    assert world.get_precedent_case(1, "3")["evidence"] == []


def test_historical_text_is_truncated_so_the_precedent_context_stays_bounded(world, direct_vm):
    long_text = ("Atlas Docs", "Z" * 2000, "Grant 18000 USD")
    review(world, direct_vm, propose(world, long_text), findings(**VIOLATED))
    pid = propose(world, ITEMIZED)
    mock_review(
        direct_vm,
        findings(),
        pmust=[r"historical_proposal_description: Z{299}…\n"],  # 300 characters including the ellipsis
        pmust_not=[r"Z{301}"],
    )
    request(world, pid)


def test_at_most_two_historical_evidence_records_are_shown_per_candidate(world, direct_vm):
    prior = propose(world)
    for i in range(3):
        add_verified_evidence(world, direct_vm, prior, fact=f"fact_{i}")
    review(world, direct_vm, prior, findings(s2_kw=dict(ev=[1, 2, 3])))
    pid = propose(world, ITEMIZED)
    mock_review(direct_vm, findings(), pmust=[r"historical_evidence: id=1 [^\n]*\nhistorical_evidence: id=2 "], pmust_not=[r"historical_evidence: id=3 "])
    request(world, pid)
    assert world.get_precedent_case(1, "2")["evidence"][2]["evidence_id"] == 3  # the full list stays readable on demand


def test_the_prompt_states_that_precedent_is_advisory_and_never_a_current_fact(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    pid = propose(world, ITEMIZED)
    mock_review(
        direct_vm,
        findings(),
        pmust=[
            r"Precedent is advisory\. It never establishes a fact about the current proposal, and facts or evidence of a prior case are not evidence here\.\n",
            r"You cannot change, question or\n",
            r"Cite nothing for a section if no prior ruling is materially relevant\. Omitting citations is always acceptable\.",
        ],
    )
    request(world, pid)
