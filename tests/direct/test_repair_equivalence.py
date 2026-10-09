"""Stage 4 validator rule (docs/STAGE_4_EQUIVALENCE.md).

Each test runs the REAL leader once through `submit_repair_revision`, then replays the REAL validator with
`direct_vm.run_validator(...)` after changing what the (mocked) LLM returns for the validator, or after tampering with the
leader's returned result. The explanation is never compared."""

import copy

import pytest

from repair_support import REPAIRED, mock_repair, repair, repairable, two_targets  # noqa: F401  (fixtures)


def leader_ran(c, vm, **llm):
    mock_repair(vm, **llm)
    repair(c)
    leader = copy.deepcopy(vm._captured_validators[-1][0])
    vm.clear_mocks()
    return leader


def validator_sees(vm, *, raw=None, leader_result=None, leader_error=None, **llm):
    vm.clear_mocks()
    mock_repair(vm, raw=raw, **llm)
    kw = {"leader_result": leader_result} if leader_result is not None else {}
    if leader_error is not None:
        kw["leader_error"] = leader_error
    return vm.run_validator(**kw)


# ---- accept ------------------------------------------------------------------------------------------------------


def test_identical_assessment_is_accepted(repairable, direct_vm):
    leader_ran(repairable, direct_vm)
    assert validator_sees(direct_vm) is True


def test_equivalent_assessment_with_different_prose_is_accepted(repairable, direct_vm):
    leader_ran(repairable, direct_vm, reason="The revision adds the missing budget breakdown.")
    assert validator_sees(direct_vm, reason="A cost-by-category budget is now supplied, which the charter requires.") is True


def test_partial_repair_agreed_by_both_is_accepted(two_targets, direct_vm):
    leader_ran(two_targets, direct_vm, addressed=("3",))
    assert validator_sees(direct_vm, addressed=("3",)) is True


def test_the_same_inadmissible_assessment_is_accepted_so_the_rejection_can_finalize(repairable, direct_vm):
    mock_repair(direct_vm, purpose=False)
    with direct_vm.expect_revert("EXPECTED:REPAIR_REJECTED:PURPOSE_CHANGED"):
        repair(repairable)
    leader = copy.deepcopy(direct_vm._captured_validators[-1][0])
    assert validator_sees(direct_vm, purpose=False, leader_result=leader) is True


# ---- reject: a materially different assessment ---------------------------------------------------------------------


def test_leader_same_purpose_validator_says_the_purpose_changed_is_rejected(repairable, direct_vm):
    leader_ran(repairable, direct_vm)
    assert validator_sees(direct_vm, purpose=False) is False


def test_leader_no_scope_change_validator_says_scope_changed_is_rejected(repairable, direct_vm):
    leader_ran(repairable, direct_vm)
    assert validator_sees(direct_vm, scope=True) is False


def test_both_agree_on_purpose_but_disagree_whether_any_target_is_addressed_is_rejected(repairable, direct_vm):
    leader_ran(repairable, direct_vm, addressed=("3",))
    assert validator_sees(direct_vm, addressed=()) is False


def test_leader_addressed_nothing_validator_says_a_target_was_addressed_is_rejected(repairable, direct_vm):
    mock_repair(direct_vm, addressed=())
    with direct_vm.expect_revert("EXPECTED:REPAIR_REJECTED:NO_TARGET_ADDRESSED"):
        repair(repairable)
    leader = copy.deepcopy(direct_vm._captured_validators[-1][0])
    assert validator_sees(direct_vm, addressed=("3",), leader_result=leader) is False


@pytest.mark.parametrize(
    "leader_ids,validator_ids",
    [(("2", "3"), ("3",)), (("3",), ("2", "3")), (("2",), ("3",)), (("3",), ("2",))],
    ids=["leader-more", "validator-more", "disjoint-a", "disjoint-b"],
)
def test_different_addressed_target_sets_are_rejected(two_targets, direct_vm, leader_ids, validator_ids):
    leader_ran(two_targets, direct_vm, addressed=leader_ids)
    assert validator_sees(direct_vm, addressed=validator_ids) is False


def test_a_validator_whose_own_llm_output_is_unusable_rejects(repairable, direct_vm):
    leader_ran(repairable, direct_vm)
    assert validator_sees(direct_vm, raw="not json") is False
    assert validator_sees(direct_vm, addressed=("1",)) is False  # a claim about a non-target section
    assert validator_sees(direct_vm, raw={"same_fundamental_purpose": True}) is False


@pytest.mark.parametrize("message", ["LLM_ERROR:MALFORMED_JSON", "EXPECTED:REPAIR_NOT_ALLOWED", "anything"])
def test_a_failed_leader_is_always_rejected(repairable, direct_vm, message):
    leader_ran(repairable, direct_vm)
    assert validator_sees(direct_vm, leader_error=Exception(message)) is False


# ---- reject: protocol identity and structure --------------------------------------------------------------------------


def tamper(**changes):
    def apply(r):
        r.update(changes)

    return apply


def drop(key):
    def apply(r):
        del r[key]

    return apply


TAMPERED = [
    ("different-proposal", tamper(proposal_id=2)),
    ("different-parent-revision", tamper(parent_revision_id=1)),
    ("different-source-review", tamper(source_review_id=2)),
    ("uses-current-charter-version", tamper(charter_version=7)),
    ("different-target-set", tamper(target_ids=["3", "9"])),
    ("leader-claims-a-non-target-section", tamper(addressed_section_ids=["1", "3"])),
    ("leader-claims-an-unknown-section", tamper(addressed_section_ids=["99"])),
    ("addressed-not-sorted", tamper(addressed_section_ids=["3", "3"])),
    ("addressed-not-a-list", tamper(addressed_section_ids="3")),
    ("purpose-not-bool", tamper(same_fundamental_purpose="yes")),
    ("scope-not-bool", tamper(material_scope_change=0)),
    ("oversized-reason", tamper(short_reason="x" * 301)),
    ("reason-not-string", tamper(short_reason=None)),
    ("extra-key", tamper(admissible=True)),
    ("missing-key", drop("short_reason")),
    ("proposal-id-bool", tamper(proposal_id=True)),
]


@pytest.mark.parametrize("mutate", [m for _n, m in TAMPERED], ids=[n for n, _m in TAMPERED])
def test_tampered_leader_results_are_rejected(repairable, direct_vm, mutate):
    stored = leader_ran(repairable, direct_vm)
    mutate(stored)
    assert validator_sees(direct_vm, leader_result=stored) is False


def test_the_untampered_result_still_passes(repairable, direct_vm):
    stored = leader_ran(repairable, direct_vm)
    assert validator_sees(direct_vm, leader_result=stored) is True
