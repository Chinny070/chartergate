"""Stage 5 citations: FOLLOWED / DISTINGUISHED, structural validation, and the rule that precedent is never evidence."""

import copy

import pytest

from precedent_support import (
    ITEMIZED,
    NO_BREAKDOWN,
    VIOLATED,
    add_verified_evidence,
    cite,
    findings,
    precedents_of,
    propose,
    review,
    world,  # noqa: F401  (fixture)
)
from review_support import fnd, findings_of, mock_review, request, review_of


@pytest.fixture
def prior(world, direct_vm):
    """Review 1 (proposal 1): no budget breakdown -> VIOLATED (repairable) on section 3. Proposal 2 is ready for review."""
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    propose(world, ITEMIZED)
    return world


def attempt(c, vm, fs, proposal_id=2, **kw):
    vm.clear_mocks()
    mock_review(vm, fs, **kw)
    request(c, proposal_id)


# ---- the two treatments -----------------------------------------------------------------------------------------------


def test_followed_is_stored_and_the_current_finding_stays_primary(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    pid = propose(world)  # materially the same omission
    attempt(world, direct_vm, findings(precedents={"3": [cite(1, "FOLLOWED", "Same omission as review 1.")]}, **VIOLATED), pid)
    p = precedents_of(world, 2)
    assert p["citations"] == [{"section_id": "3", "precedent_review_id": 1, "treatment": "FOLLOWED", "reason": "Same omission as review 1."}]
    f3 = findings_of(world, 2)[2]
    assert (f3["finding"], f3["repairable"]) == ("VIOLATED", True)  # the current finding is still VIOLATED / repairable
    assert review_of(world, pid)["verdict"] == "REPAIRABLE"


def test_distinguished_requires_a_reason_and_is_stored(prior, direct_vm):
    attempt(prior, direct_vm, findings(precedents={"3": [cite(1, "DISTINGUISHED", "The current proposal itemizes its budget.")]}))
    assert precedents_of(prior, 2)["citations"][0]["treatment"] == "DISTINGUISHED"
    assert findings_of(prior, 2)[2]["finding"] == "SATISFIED"  # the distinction rests on the CURRENT case, not on authority


def test_distinguished_without_a_reason_is_rejected(prior, direct_vm):
    for reason in ("", "   "):
        with direct_vm.expect_revert("LLM_ERROR:BAD_PRECEDENT_REASON"):
            attempt(prior, direct_vm, findings(precedents={"3": [cite(1, "DISTINGUISHED", reason)]}))


def test_citations_are_optional_and_empty_citations_are_never_an_error(prior, direct_vm):
    attempt(prior, direct_vm, findings())  # candidates exist, nothing is cited
    assert precedents_of(prior, 2)["citations"] == [] and len(precedents_of(prior, 2)["candidates"]) == 3
    direct_vm.clear_mocks()


@pytest.mark.parametrize("empty", [[], None], ids=["empty-list", "null"])
def test_an_explicitly_empty_precedents_field_is_fine(prior, direct_vm, empty):
    attempt(prior, direct_vm, findings(precedents={"3": empty}) if empty is not None else findings())
    assert precedents_of(prior, 2)["citations"] == []


def test_the_current_finding_is_valid_with_every_citation_removed(prior, direct_vm):
    """Charter + current case + current evidence must carry the finding on their own."""
    with_cites = copy.deepcopy(findings(precedents={"3": [cite(1, "DISTINGUISHED", "Itemized budget.")]}))
    without = copy.deepcopy(with_cites)
    for f in without:
        f.pop("precedents", None)
    attempt(prior, direct_vm, without)
    verdict_without = review_of(prior, 2)["verdict"]
    assert verdict_without == "ELIGIBLE" and precedents_of(prior, 2)["citations"] == []


def test_at_most_two_citations_and_no_duplicates(world, direct_vm):
    for _ in range(3):
        review(world, direct_vm, propose(world), findings())
    pid = propose(world)
    two = [cite(2, "DISTINGUISHED", "x"), cite(3, "DISTINGUISHED", "y")]
    attempt(world, direct_vm, findings(precedents={"3": two}), pid)
    assert [c["precedent_review_id"] for c in precedents_of(world, 4)["citations"]] == [2, 3]  # stored sorted by review id
    pid = propose(world)
    for bad in ([cite(2, "DISTINGUISHED", "x"), cite(3, "DISTINGUISHED", "y"), cite(1, "DISTINGUISHED", "z")], [cite(3, "DISTINGUISHED", "x"), cite(3, "DISTINGUISHED", "y")]):
        with direct_vm.expect_revert("LLM_ERROR:BAD_PRECEDENT_REF"):
            attempt(world, direct_vm, findings(precedents={"3": bad}), pid)


# ---- FOLLOWED must be consistent ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current,kw",
    [
        ("SATISFIED", {}),  # a VIOLATED precedent followed by a SATISFIED finding
        ("UNCLEAR", {}),
        ("NOT_APPLICABLE", {}),
        ("VIOLATED", dict(repairable=False)),  # same class, different repairability
    ],
    ids=["satisfied", "unclear", "not-applicable", "violated-not-repairable"],
)
def test_followed_must_be_compatible_with_the_precedents_finding(prior, direct_vm, current, kw):
    fs = findings(s3=current, s3_kw=kw, precedents={"3": [cite(1, "FOLLOWED", "x")]})
    with direct_vm.expect_revert("LLM_ERROR:PRECEDENT_INCOMPATIBLE"):
        attempt(prior, direct_vm, fs)
    assert prior.get_review_count() == 1


def test_a_violated_precedent_may_be_distinguished_by_a_satisfied_current_finding(prior, direct_vm):
    attempt(prior, direct_vm, findings(precedents={"3": [cite(1, "DISTINGUISHED", "Itemized budget supplied.")]}))
    assert precedents_of(prior, 2)["citations"][0]["treatment"] == "DISTINGUISHED"


# ---- membership: only the section's own snapshot may be cited ------------------------------------------------------------------


@pytest.mark.parametrize("review_id", [0, 2, 9, 99], ids=["zero", "the-current-review", "future-review", "nonexistent"])
def test_a_citation_outside_the_snapshot_is_rejected(prior, direct_vm, review_id):
    with direct_vm.expect_revert("LLM_ERROR:BAD_PRECEDENT_REF"):
        attempt(prior, direct_vm, findings(precedents={"3": [cite(review_id, "DISTINGUISHED", "x")]}))
    assert prior.get_review_count() == 1


def test_a_citation_for_a_section_with_no_candidates_is_rejected(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    pid = propose(world)
    # section 9 does not exist; and review 1 is a candidate for sections 1-3 only
    fs = findings()
    fs[0]["precedents"] = [cite(7, "FOLLOWED", "")]
    with direct_vm.expect_revert("LLM_ERROR:BAD_PRECEDENT_REF"):
        attempt(world, direct_vm, fs, pid)


def test_a_precedent_cannot_be_cited_under_a_different_rule(world, direct_vm, direct_owner, direct_alice):
    review(world, direct_vm, propose(world), findings(**VIOLATED))  # 3@4
    direct_vm.sender = direct_owner
    world.update_charter_section("3", "Budget", "Budget breakdowns are optional.")  # 3@5
    direct_vm.sender = direct_alice
    pid = propose(world, ITEMIZED)
    with direct_vm.expect_revert("LLM_ERROR:BAD_PRECEDENT_REF"):
        attempt(world, direct_vm, findings(precedents={"3": [cite(1, "DISTINGUISHED", "Amended rule.")]}), pid)


def test_same_lineage_reviews_cannot_be_cited(world, direct_vm):
    from repair_support import mock_repair

    first = propose(world)
    review(world, direct_vm, first, findings(**VIOLATED))
    mock_repair(direct_vm)
    world.submit_repair_revision(first, ITEMIZED[0], ITEMIZED[1], ITEMIZED[2])
    direct_vm.clear_mocks()
    # the lineage's own review is not a candidate, so the revision review has no candidates and runs NO precedent pass at all
    mock_review(direct_vm, findings(), precedent_raw={"precedents": [{"section_id": "3", **cite(1, "DISTINGUISHED", "My own earlier review.")}]})
    world.request_revision_review(1)
    assert precedents_of(world, 2)["candidates"] == [] and precedents_of(world, 2)["citations"] == []


@pytest.mark.parametrize(
    "item,code",
    [
        ({"review_id": 1, "treatment": "OVERRULED", "reason": "x"}, "BAD_PRECEDENT_TREATMENT"),
        ({"review_id": 1, "treatment": 5, "reason": "x"}, "BAD_PRECEDENT_TREATMENT"),
        ({"review_id": 1, "treatment": "DISTINGUISHED", "reason": "x" * 201}, "BAD_PRECEDENT_REASON"),
        ({"review_id": 1, "treatment": "DISTINGUISHED", "reason": 5}, "BAD_PRECEDENT_REASON"),
        ({"review_id": "abc", "treatment": "DISTINGUISHED", "reason": "x"}, "BAD_PRECEDENT_REF"),
        ({"review_id": True, "treatment": "DISTINGUISHED", "reason": "x"}, "BAD_PRECEDENT_REF"),
        ({"treatment": "DISTINGUISHED", "reason": "x"}, "BAD_PRECEDENT_REF"),
    ],
    ids=["unknown-treatment", "treatment-not-string", "reason-too-long", "reason-not-string", "id-not-numeric", "id-bool", "id-missing"],
)
def test_malformed_citations_fail_closed(prior, direct_vm, item, code):
    with direct_vm.expect_revert("LLM_ERROR:" + code):
        attempt(prior, direct_vm, findings(precedents={"3": [item]}))
    assert prior.get_review_count() == 1


def test_a_non_list_precedents_field_fails_closed(prior, direct_vm):
    with direct_vm.expect_revert("LLM_ERROR:BAD_PRECEDENT_REF"):
        attempt(prior, direct_vm, findings(), precedent_raw={"precedents": "review 1"})


def test_treatment_case_and_a_numeric_string_id_are_tolerated(prior, direct_vm):
    attempt(prior, direct_vm, findings(precedents={"3": [{"review_id": "1", "treatment": " distinguished ", "reason": "  Itemized   budget. "}]}))
    c = precedents_of(prior, 2)["citations"][0]
    assert (c["precedent_review_id"], c["treatment"], c["reason"]) == (1, "DISTINGUISHED", "Itemized budget.")


# ---- precedent is not evidence -----------------------------------------------------------------------------------------------------


@pytest.fixture
def evidenced(world, direct_vm):
    """Review 1: proposal 1 has VERIFIED evidence #1 (team allocation) and section 2 is SATISFIED on it. Proposal 2 has none."""
    p1 = propose(world)
    add_verified_evidence(world, direct_vm, p1)
    review(world, direct_vm, p1, findings(s2_kw=dict(ev=[1])))
    propose(world, ITEMIZED)
    return world


def test_the_prior_evidence_is_shown_only_inside_the_precedent_block_never_as_current_evidence(evidenced, direct_vm):
    mock_review(
        direct_vm,
        findings(s2="UNCLEAR"),
        pmust=[
            r"=== UNTRUSTED CURRENT CASE DATA: its VERIFIED evidence ===\n\(none\)",  # the CURRENT proposal has no evidence
            r"historical_evidence: id=1 fact=team_token_allocation value=46% ",  # the prior case's evidence, labelled historical
        ],
        pmust_not=[r"its VERIFIED evidence ===\n<<<DATA\nevidence_id: 1"],
    )
    request(evidenced, 2)
    assert review_of(evidenced, 2)["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_precedent_cannot_turn_unclear_into_satisfied_the_prior_evidence_id_is_not_citable(evidenced, direct_vm):
    # a model that "reused" the prior case's evidence for the current finding cites an id that is not in THIS proposal's snapshot
    with direct_vm.expect_revert("LLM_ERROR:BAD_EVIDENCE_REF"):
        attempt(evidenced, direct_vm, findings(s2_kw=dict(ev=[1])))
    assert review_of(evidenced, 1)["verdict"] == "ELIGIBLE" and evidenced.get_review_count() == 1


def test_following_an_evidence_backed_ruling_with_an_unsupported_satisfied_finding_is_rejected(evidenced, direct_vm):
    """Precedent cannot rescue an unsupported finding: SATISFIED + FOLLOWED + no current evidence is refused."""
    fs = findings(precedents={"2": [cite(1, "FOLLOWED", "The prior case disclosed 46%.")]})
    with direct_vm.expect_revert("LLM_ERROR:PRECEDENT_NOT_EVIDENCE"):
        attempt(evidenced, direct_vm, fs)
    assert evidenced.get_review_count() == 1


def test_a_current_finding_without_current_evidence_stays_unclear_even_when_the_prior_case_is_cited(evidenced, direct_vm):
    attempt(evidenced, direct_vm, findings(s2="UNCLEAR", precedents={"2": [cite(1, "DISTINGUISHED", "No current evidence of the allocation.")]}))
    f2 = findings_of(evidenced, 2)[1]
    assert f2["finding"] == "UNCLEAR" and f2["evidence_ids"] == [] and f2["missing_fact"] != ""
    assert review_of(evidenced, 2)["verdict"] == "INSUFFICIENT_EVIDENCE"


def test_with_current_evidence_a_followed_satisfied_finding_is_accepted(evidenced, direct_vm):
    add_verified_evidence(evidenced, direct_vm, 2, fact="team_token_allocation")  # evidence #2 belongs to proposal 2
    attempt(evidenced, direct_vm, findings(s2_kw=dict(ev=[2]), precedents={"2": [cite(1, "FOLLOWED", "Same disclosure, now evidenced.")]}))
    assert precedents_of(evidenced, 2)["citations"][0]["treatment"] == "FOLLOWED"
    assert findings_of(evidenced, 2)[1]["evidence_ids"] == [2]
