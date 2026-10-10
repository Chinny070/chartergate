"""Stage 6 validator rules (docs/STAGE_6_EQUIVALENCE.md) and appellate atomicity.

Each equivalence test runs the REAL leader once, then replays the REAL validator after changing what the (mocked) LLM returns for the
validator or after tampering with the leader's result. A validator re-runs the precedent-FREE appellate adjudication from its own
reconstruction of the closed record, requires material agreement, and semantically checks the leader's chosen citations."""

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


def lead_appeal(world, vm, review_id, fs, **kw):
    vm.clear_mocks()
    mock_appeal(vm, fs, **kw)
    world.request_appeal(review_id, GROUND, STATEMENT)
    stored = copy.deepcopy(vm._captured_validators[-1][0])
    vm.clear_mocks()
    return stored


def cited_ids(result):
    return sorted({i for f in result["findings"] for i in f["evidence_ids"]})


def replay(vm, vfs, *, leader_result=None, **kw):
    leader = leader_result if leader_result is not None else vm._captured_validators[-1][0]
    vm.clear_mocks()
    mock_appeal(vm, vfs, **kw)
    mock_refs(vm, cited_ids(leader) if isinstance(leader, dict) and isinstance(leader.get("findings"), list) else [])
    extra = {"leader_result": leader_result} if leader_result is not None else {}
    return vm.run_validator(**extra)


@pytest.fixture
def case(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)

    def run(fs, **kw):
        return lead_appeal(world, direct_vm, rid, fs, **kw)

    return run


# ---- accept ------------------------------------------------------------------------------------------------------------------------------------


def test_identical_appellate_judgment_is_accepted(case, direct_vm):
    case(findings(**VIOLATED))
    assert replay(direct_vm, findings(**VIOLATED)) is True


def test_different_prose_is_accepted(case, direct_vm):
    case(findings(**VIOLATED))
    assert replay(direct_vm, findings(s3="VIOLATED", s3_kw=dict(repairable=True, rationale="Entirely other words."))) is True


def test_a_reversal_is_accepted_when_the_validator_independently_agrees(case, direct_vm):
    case(findings())
    assert replay(direct_vm, findings()) is True


def test_the_untampered_result_still_passes(case, direct_vm):
    stored = case(findings(**VIOLATED))
    assert replay(direct_vm, findings(**VIOLATED), leader_result=stored) is True


# ---- reject: the appellate judgment differs --------------------------------------------------------------------------------------------------------


def test_a_different_finding_class_is_rejected(case, direct_vm):
    case(findings(**VIOLATED))
    assert replay(direct_vm, findings()) is False


def test_a_different_repairability_is_rejected(case, direct_vm):
    case(findings(**VIOLATED))
    assert replay(direct_vm, findings(s3="VIOLATED", s3_kw=dict(repairable=False, rationale="x"))) is False


def test_a_different_verdict_is_rejected(case, direct_vm):
    case(findings(**VIOLATED))
    assert replay(direct_vm, findings(s2="UNCLEAR", **VIOLATED)) is False  # same verdict (REPAIRABLE) but section 2 changed class
    assert replay(direct_vm, findings(s2="UNCLEAR")) is False  # INSUFFICIENT_EVIDENCE


def test_an_unusable_validator_output_rejects(case, direct_vm):
    case(findings(**VIOLATED))
    assert replay(direct_vm, None, raw="not json") is False


def test_a_validator_never_runs_a_precedent_pass_of_its_own(case, direct_vm):
    case(findings(**VIOLATED))
    direct_vm.clear_mocks()
    direct_vm.mock_llm(r"\A[\s\S]*CONSTITUTIONAL APPEAL", json.dumps({"findings": findings(**VIOLATED)}))  # only the base prompt is mocked
    assert direct_vm.run_validator() is True


# ---- precedent citations are validated semantically ------------------------------------------------------------------------------------------------


@pytest.fixture
def cited_case(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    pid, rid = adverse_review(world, direct_vm)  # review 2 has review 1 as a candidate

    def run(fs, **kw):
        return lead_appeal(world, direct_vm, rid, fs, **kw)

    return run


def test_a_supported_citation_is_accepted(cited_case, direct_vm):
    cited_case(findings(precedents={"3": [cite(1, "FOLLOWED", "Same omission.")]}, **VIOLATED))
    assert replay(direct_vm, findings(**VIOLATED), check=True) is True


def test_an_unsupported_citation_is_rejected(cited_case, direct_vm):
    cited_case(findings(precedents={"3": [cite(1, "FOLLOWED", "Same omission.")]}, **VIOLATED))
    assert replay(direct_vm, findings(**VIOLATED), check=False) is False


# ---- reject: tampered leader results -----------------------------------------------------------------------------------------------------------------


def with_finding(index, **changes):
    def apply(r):
        r["findings"][index].update(changes)

    return apply


def tamper(**changes):
    def apply(r):
        r.update(changes)

    return apply


GOOD = {"section_id": "3", "review_id": 1, "treatment": "FOLLOWED", "reason": "x"}
TAMPERED = [
    ("wrong-decision-kind", tamper(decision_kind="REVERSED")),
    ("decision-kind-missing", lambda r: r.pop("decision_kind")),
    ("wrong-appeal-context-hash", tamper(context_hash="0x" + "ab" * 32)),
    ("original-review-context-instead-of-appeal-context", None),
    ("wrong-evidence-set-hash", tamper(evidence_set_hash="0x" + "cd" * 32)),
    ("wrong-evidence-count", tamper(evidence_count=3)),
    ("wrong-charter-version", tamper(charter_version=9)),
    ("wrong-proposal", tamper(proposal_id=9)),
    ("wrong-precedent-set-hash", tamper(precedent_set_hash="0x" + "ef" * 32)),
    ("verdict-not-derived", tamper(verdict="ELIGIBLE")),
    ("extra-key", tamper(note="x")),
    ("citation-outside-the-snapshot", tamper(precedents=[{**GOOD, "review_id": 99}])),
    ("unknown-treatment", tamper(precedents=[{**GOOD, "treatment": "OVERRULED"}])),
    ("evidence-outside-the-snapshot", with_finding(1, evidence_ids=[1])),
    ("finding-class-changed-after-the-fact", with_finding(2, finding="SATISFIED", repairable=False)),
]


@pytest.mark.parametrize("name,mutate", [(n, m) for n, m in TAMPERED if m is not None], ids=[n for n, m in TAMPERED if m is not None])
def test_tampered_leader_results_are_rejected(cited_case, direct_vm, name, mutate):
    stored = cited_case(findings(precedents={"3": [cite(1, "FOLLOWED", "Same omission.")]}, **VIOLATED))
    mutate(stored)
    assert replay(direct_vm, findings(**VIOLATED), leader_result=stored) is False


def test_the_original_reviews_context_hash_is_not_the_appeals_context(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    stored = lead_appeal(world, direct_vm, rid, findings(**VIOLATED))
    assert stored["context_hash"] != world.get_constitutional_review(rid)["review_context_hash"]  # the appeal has its own identity
    stored["context_hash"] = world.get_constitutional_review(rid)["review_context_hash"]
    assert replay(direct_vm, findings(**VIOLATED), leader_result=stored) is False


# ---- atomicity: a failed appellate adjudication leaves no trace ------------------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,code",
    [
        ("not json", "LLM_ERROR"),
        ({"findings": "nope"}, "LLM_ERROR:BAD_FINDINGS"),
        ({"findings": findings()[:2]}, "LLM_ERROR:BAD_FINDING_COVERAGE"),
        ({"findings": findings(s2_kw=dict(ev=[7]))}, "LLM_ERROR:BAD_EVIDENCE_REF"),
        ({"findings": findings(s1="NOT_APPLICABLE", s2="NOT_APPLICABLE", s3="NOT_APPLICABLE")}, "LLM_ERROR:ALL_NOT_APPLICABLE"),
        ({"findings": findings(s2="UNCLEAR", s2_kw=dict(missing=""))}, "LLM_ERROR:BAD_MISSING_FACT"),
    ],
    ids=["unusable", "not-a-list", "missing-section", "unknown-evidence", "all-not-applicable", "unclear-without-missing-fact"],
)
def test_a_malformed_appellate_output_stores_nothing(world, direct_vm, raw, code):
    pid, rid = adverse_review(world, direct_vm)
    before = snapshot(world)
    direct_vm.clear_mocks()
    mock_appeal(direct_vm, None, raw=raw)
    with direct_vm.expect_revert(code):
        world.request_appeal(rid, GROUND, STATEMENT)
    assert snapshot(world) == before
    assert world.get_appeal_count() == 0 and world.get_appeal_id_for_review(rid) == 0
    assert world.get_proposal(pid)["status"] == "REPAIRABLE" and world.get_effective_ruling(pid)["controlled_by"] == "REVIEW"
    appeal(world, direct_vm, rid, findings(**VIOLATED))  # nothing was consumed: the same appeal now succeeds
    assert world.get_appeal_count() == 1


@pytest.mark.parametrize(
    "cites,code",
    [
        ([{"section_id": "3", **cite(99, "FOLLOWED", "x")}], "LLM_ERROR:BAD_PRECEDENT_REF"),
        ([{"section_id": "3", **cite(1, "DISTINGUISHED", "")}], "LLM_ERROR:BAD_PRECEDENT_REASON"),
        ([{"section_id": "3", **cite(1, "OVERRULED", "x")}], "LLM_ERROR:BAD_PRECEDENT_TREATMENT"),
    ],
    ids=["outside-snapshot", "distinguished-without-reason", "unknown-treatment"],
)
def test_an_invalid_precedent_use_stores_nothing_even_with_valid_findings(world, direct_vm, cites, code):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    pid, rid = adverse_review(world, direct_vm)
    before = snapshot(world)
    direct_vm.clear_mocks()
    mock_appeal(direct_vm, findings(**VIOLATED), cites=cites)  # the appellate FINDINGS are valid; only the annotation is not
    with direct_vm.expect_revert(code):
        world.request_appeal(rid, GROUND, STATEMENT)
    assert snapshot(world) == before and world.get_appeal_count() == 0 and world.get_effective_ruling(pid)["controlled_by"] == "REVIEW"


def test_an_unusable_precedent_pass_stores_nothing(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    pid, rid = adverse_review(world, direct_vm)
    direct_vm.clear_mocks()
    mock_appeal(direct_vm, findings(**VIOLATED), precedent_raw="not json")
    with direct_vm.expect_revert("LLM_ERROR"):
        world.request_appeal(rid, GROUND, STATEMENT)
    assert world.get_appeal_count() == 0


def test_a_failed_appeal_does_not_touch_precedent_effective_verdict_or_repair_targets(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    ruling = world.get_effective_ruling(pid)
    targets = world.get_repair_targets(pid)
    index = world.get_rule_precedents_page("3@4", 0, 50)
    direct_vm.clear_mocks()
    mock_appeal(direct_vm, None, raw={"findings": "nope"})
    with direct_vm.expect_revert("LLM_ERROR:BAD_FINDINGS"):
        world.request_appeal(rid, GROUND, STATEMENT)
    assert world.get_effective_ruling(pid) == ruling and world.get_repair_targets(pid) == targets
    assert world.get_rule_precedents_page("3@4", 0, 50) == index


def test_a_validator_checks_that_the_cited_evidence_materially_supports_each_appellate_finding(world, direct_vm):
    pid = propose(world)
    add_verified_evidence(world, direct_vm, pid)
    rid = review(world, direct_vm, pid, findings(s2_kw=dict(ev=[1]), **VIOLATED))
    fs = findings(s2_kw=dict(ev=[1]), **VIOLATED)
    lead_appeal(world, direct_vm, rid, fs, refs=[1])
    assert replay(direct_vm, fs) is True  # the validator finds the cited evidence supports the finding
    direct_vm.clear_mocks()
    mock_appeal(direct_vm, fs)
    mock_refs(direct_vm, [])  # ...or finds that it does not
    assert direct_vm.run_validator() is False


def test_a_validator_with_precedent_candidates_still_never_runs_a_precedent_pass_of_its_own(cited_case, direct_vm):
    cited_case(findings(precedents={"3": [cite(1, "FOLLOWED", "Same omission.")]}, **VIOLATED))
    direct_vm.clear_mocks()
    # only the base appellate prompt and the leader's citation check are mocked: a validator-side precedent pass would find no mock
    direct_vm.mock_llm(r"\A[\s\S]*CONSTITUTIONAL APPEAL", json.dumps({"findings": findings(**VIOLATED)}))
    direct_vm.mock_llm(r"\APRECEDENT CITATION CHECK[\s\S]*", json.dumps({"supported": True}))
    assert direct_vm.run_validator() is True
