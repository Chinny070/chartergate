"""Stage 3 validator rule (docs/STAGE_3_EQUIVALENCE.md).

Each test runs the REAL leader once through `request_constitutional_review`, then replays the REAL validator with
`direct_vm.run_validator(...)` after changing what the (mocked) LLM returns for the validator, or after tampering with
the leader's returned result. Prose is never compared.
"""

import copy

import pytest

from review_support import all_findings, fnd, mock_review, request, reviewable  # noqa: F401  (fixture)

ELIGIBLE = lambda: all_findings(fnd("1"), fnd("2", ev=[1]))  # noqa: E731


def leader_ran(c, vm, findings):
    mock_review(vm, findings)
    request(c)
    leader = copy.deepcopy(vm._captured_validators[-1][0])
    vm.clear_mocks()
    return leader


def validator_sees(vm, findings=None, *, raw=None, leader_result=None, **kw):
    vm.clear_mocks()
    if findings is not None or raw is not None:
        mock_review(vm, findings, raw=raw)
    if leader_result is not None:
        kw["leader_result"] = leader_result
    return vm.run_validator(**kw)


# ---- accept: the same material judgment ------------------------------------------------------------


def test_identical_judgment_is_accepted(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, ELIGIBLE())
    assert validator_sees(direct_vm, ELIGIBLE()) is True


def test_different_prose_with_the_same_judgment_is_accepted(reviewable, direct_vm):
    """'The disclosure requirement is satisfied.' vs 'Verified evidence demonstrates the required disclosure.'"""
    leader_ran(reviewable, direct_vm, [fnd("1", rationale="On mission."), fnd("2", ev=[1], rationale="The disclosure requirement is satisfied.")])
    mine = [
        fnd("1", rationale="This is clearly within the DAO's stated purpose; nothing more to add!"),
        fnd("2", ev=[1], rationale="Verified evidence demonstrates the required disclosure.", missing=""),
    ]
    assert validator_sees(direct_vm, mine) is True


def test_satisfied_and_not_applicable_are_interchangeable(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1", "NOT_APPLICABLE"), fnd("2", ev=[1])])
    assert validator_sees(direct_vm, [fnd("1", "SATISFIED"), fnd("2", ev=[1])]) is True


def test_unordered_answers_and_evidence_order_do_not_matter(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1", "VIOLATED", repairable=True, ev=[1]), fnd("2")])
    assert validator_sees(direct_vm, [fnd("2"), fnd("1", "VIOLATED", repairable=True, ev=[1])]) is True


def test_validator_citing_additional_verified_evidence_is_accepted(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=False, ev=[1])])
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=False, ev=[1])]) is True


def test_a_violation_grounded_in_the_proposal_text_alone_is_accepted(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=True)])
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=True, ev=[1])]) is True


def test_different_missing_fact_wording_is_accepted(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", "UNCLEAR", missing="conflict disclosure")])
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", "UNCLEAR", missing="a statement of conflicts of interest")]) is True


# ---- reject: a materially different judgment -------------------------------------------------------------


def test_leader_eligible_validator_finds_section_2_violated_is_rejected(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, ELIGIBLE())
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=False, ev=[1])]) is False


def test_different_verdict_is_rejected(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=True)])
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=False)]) is False


def test_same_verdict_but_different_violated_section_is_rejected(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1", "VIOLATED", repairable=False), fnd("2")])
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=False)]) is False


def test_same_section_but_different_repairability_is_rejected(reviewable, direct_vm):
    # Both judge section 1 violated; section 2 keeps the verdicts equal only if repairability matched.
    leader_ran(reviewable, direct_vm, [fnd("1", "VIOLATED", repairable=True), fnd("2", "VIOLATED", repairable=False)])
    assert validator_sees(direct_vm, [fnd("1", "VIOLATED", repairable=False), fnd("2", "VIOLATED", repairable=False)]) is False


def test_same_verdict_different_unclear_section_is_rejected(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1", "UNCLEAR"), fnd("2")])
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", "UNCLEAR")]) is False


def test_leader_cites_verified_evidence_validator_says_it_does_not_support_it_is_rejected(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=False, ev=[1])])
    # same section, same repairability, but this validator does not rely on evidence #1 for the violation
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=False)]) is False


def test_leader_insufficient_validator_finds_verified_evidence_resolves_it_is_rejected(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", "UNCLEAR", ev=[3])])
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", ev=[1])]) is False


def test_validator_whose_own_llm_output_is_unusable_rejects(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, ELIGIBLE())
    assert validator_sees(direct_vm, raw="this is not json") is False
    assert validator_sees(direct_vm, [fnd("1")]) is False  # incomplete coverage


@pytest.mark.parametrize("message", ["LLM_ERROR:MALFORMED_JSON", "EXPECTED:REVIEW_TOO_MANY_SECTIONS", "anything"])
def test_a_failed_leader_is_always_rejected(reviewable, direct_vm, message):
    leader_ran(reviewable, direct_vm, ELIGIBLE())
    assert validator_sees(direct_vm, ELIGIBLE(), leader_error=Exception(message)) is False


# ---- reject: protocol-critical identity and structure --------------------------------------------------------

OTHER_HASH = "0x" + "ab" * 32


def tamper(**changes):
    def apply(r):
        r.update(changes)

    return apply


def with_finding(index, **changes):
    def apply(r):
        r["findings"][index].update(changes)

    return apply


def swap_findings(r):
    r["findings"].reverse()


def drop_key(key):
    def apply(r):
        del r[key]

    return apply


TAMPERED = [
    ("evidence-count-includes-a-future-record", tamper(evidence_count=5)),
    ("evidence-set-hash-differs", tamper(evidence_set_hash=OTHER_HASH)),
    ("review-context-differs", tamper(context_hash=OTHER_HASH)),
    ("uses-current-charter-version", tamper(charter_version=3 + 3)),
    ("different-proposal", tamper(proposal_id=2)),
    ("verdict-not-derived-from-findings", tamper(verdict="INELIGIBLE")),
    ("unknown-verdict", tamper(verdict="APPROVED")),
    ("extra-key", tamper(extra="x")),
    ("missing-key", drop_key("context_hash")),
    ("findings-not-a-list", tamper(findings="none")),
    ("findings-out-of-charter-order", swap_findings),
    ("future-section", with_finding(1, section_id="3")),
    ("nonexistent-evidence", with_finding(1, evidence_ids=[99])),
    ("future-evidence", with_finding(1, evidence_ids=[5])),
    ("non-verified-evidence-as-proof", with_finding(1, evidence_ids=[2])),
    ("unknown-finding-kind", with_finding(1, finding="MAYBE")),
    ("repairable-on-a-satisfied-finding", with_finding(1, repairable=True)),
    ("oversized-rationale", with_finding(1, rationale="x" * 301)),
    ("extra-finding-key", with_finding(1, note="x")),
]


@pytest.mark.parametrize("mutate", [m for _n, m in TAMPERED], ids=[n for n, _m in TAMPERED])
def test_tampered_leader_results_are_rejected(reviewable, direct_vm, mutate):
    stored = leader_ran(reviewable, direct_vm, ELIGIBLE())
    mutate(stored)
    assert validator_sees(direct_vm, ELIGIBLE(), leader_result=stored) is False


def test_the_untampered_result_still_passes(reviewable, direct_vm):
    stored = leader_ran(reviewable, direct_vm, ELIGIBLE())
    assert validator_sees(direct_vm, ELIGIBLE(), leader_result=stored) is True
