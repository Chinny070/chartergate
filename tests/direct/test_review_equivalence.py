"""Stage 3 validator rule (docs/STAGE_3_EQUIVALENCE.md).

Each test runs the REAL leader once through `request_constitutional_review`, then replays the REAL validator with
`direct_vm.run_validator(...)` after changing what the (mocked) LLM returns for the validator, or after tampering with
the leader's returned result. Prose is never compared.
"""

import copy

import pytest

from review_support import add_evidence, all_findings, fnd, mock_refs, mock_review, request, reviewable  # noqa: F401  (fixture)

ELIGIBLE = lambda: all_findings(fnd("1"), fnd("2", ev=[1]))  # noqa: E731


def leader_ran(c, vm, findings):
    mock_review(vm, findings)
    request(c)
    leader = copy.deepcopy(vm._captured_validators[-1][0])
    vm.clear_mocks()
    return leader


def cited(result):
    findings = result.get("findings") if isinstance(result, dict) else None
    if not isinstance(findings, list):
        return []
    return sorted({i for f in findings if isinstance(f, dict) for i in f.get("evidence_ids", []) if isinstance(i, int)})


def validator_sees(vm, findings=None, *, raw=None, leader_result=None, refs=None, per_section=None, **kw):
    """Replay the validator. By default its evidence-reference check calls every evidence id the leader cited
    supporting; `refs` / `per_section` override that to model a validator that disagrees."""
    leader = leader_result if leader_result is not None else vm._captured_validators[-1][0]
    vm.clear_mocks()
    if findings is not None or raw is not None:
        mock_review(vm, findings, raw=raw)
    mock_refs(vm, cited(leader) if refs is None else refs, per_section=per_section)
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


def test_the_same_applicability_with_different_prose_is_accepted(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1", "NOT_APPLICABLE", rationale="Not about this."), fnd("2", ev=[1], rationale="Met.")])
    assert validator_sees(direct_vm, [fnd("1", "NOT_APPLICABLE", rationale="This rule does not govern the grant."), fnd("2", ev=[1], rationale="Entirely met.")]) is True


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
    # same section, same class, same repairability, but this validator finds evidence #1 does not support the violation
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=False)], refs=[]) is False


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


# ---- SATISFIED and NOT_APPLICABLE are different constitutional interpretations -------------------------------


def test_leader_satisfied_validator_satisfied_different_prose_is_accepted(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1", rationale="On mission."), fnd("2", ev=[1])])
    assert validator_sees(direct_vm, [fnd("1", rationale="Plainly within the DAO's purpose."), fnd("2", ev=[1], rationale="Different words.")]) is True


@pytest.mark.parametrize(
    "leader,validator",
    [
        ("SATISFIED", "NOT_APPLICABLE"),
        ("NOT_APPLICABLE", "SATISFIED"),
        ("UNCLEAR", "NOT_APPLICABLE"),
        ("NOT_APPLICABLE", "UNCLEAR"),
        ("VIOLATED", "NOT_APPLICABLE"),
        ("NOT_APPLICABLE", "VIOLATED"),
        ("SATISFIED", "UNCLEAR"),
        ("UNCLEAR", "SATISFIED"),
    ],
)
def test_every_finding_class_must_match_exactly(reviewable, direct_vm, leader, validator):
    # section 2 carries the difference; section 1 stays satisfied so the review is always valid
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", leader, repairable=leader == "VIOLATED")])
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", validator, repairable=validator == "VIOLATED")]) is False


@pytest.mark.parametrize("kind", ["SATISFIED", "NOT_APPLICABLE", "UNCLEAR", "VIOLATED"])
def test_each_class_is_accepted_against_itself(reviewable, direct_vm, kind):
    findings = lambda prose: [fnd("1", rationale=prose), fnd("2", kind, repairable=kind == "VIOLATED", rationale=prose)]  # noqa: E731
    leader_ran(reviewable, direct_vm, findings("one wording"))
    assert validator_sees(direct_vm, findings("another wording entirely")) is True


# ---- stored evidence references must materially support the finding --------------------------------------------


def unrelated_verified(c, vm):
    """Evidence #5: VERIFIED, same proposal, but about a different fact."""
    add_evidence(c, vm, fact="treasury_balance", claim="Atlas team token allocation is 46%.")
    assert c.get_evidence(5)["status"] == "VERIFIED" and c.get_evidence(5)["normalized_fact"] == "treasury_balance"


def test_correct_verified_evidence_supporting_satisfied_is_accepted(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", ev=[1])])
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", ev=[1])]) is True


def test_unrelated_verified_evidence_cited_for_satisfied_is_rejected(reviewable, direct_vm):
    unrelated_verified(reviewable, direct_vm)
    direct_vm.clear_mocks()
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", ev=[5])])  # VERIFIED, in the snapshot, but not about transparency
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", ev=[1])], per_section={"2": [1]}) is False
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", ev=[5])], refs=[]) is False


def test_correct_verified_evidence_supporting_violated_is_accepted(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=False, ev=[1])])
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=False, ev=[1])]) is True


def test_unrelated_verified_evidence_cited_for_violated_is_rejected(reviewable, direct_vm):
    unrelated_verified(reviewable, direct_vm)
    direct_vm.clear_mocks()
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=False, ev=[5])])
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=False)], refs=[]) is False


def test_evidence_from_the_same_proposal_about_the_wrong_fact_is_rejected(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1", ev=[1]), fnd("2")])
    # evidence #1 (team allocation) is VERIFIED and in the snapshot, but does not support the MISSION finding
    assert validator_sees(direct_vm, [fnd("1", ev=[1]), fnd("2")], per_section={"1": []}) is False


@pytest.mark.parametrize("evidence_id", [2, 3, 4])
@pytest.mark.parametrize("kind", ["SATISFIED", "VIOLATED"])
def test_non_verified_evidence_used_as_factual_support_is_rejected(reviewable, direct_vm, evidence_id, kind):
    stored = leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", kind, ev=[1])])
    stored["findings"][1]["evidence_ids"] = [evidence_id]  # a leader that cited an unverified record as proof
    # rejected on structure alone, even if the validator's reference check would call it supporting
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", kind, ev=[1])], leader_result=stored, refs=[evidence_id]) is False


def test_a_finding_grounded_in_the_proposal_text_alone_needs_no_reference_check(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=True)])
    direct_vm.clear_mocks()
    mock_review(direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=True)])  # NO reference-check mock at all
    assert direct_vm.run_validator() is True


def test_not_applicable_needs_no_reference_check(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1", "NOT_APPLICABLE"), fnd("2")])
    direct_vm.clear_mocks()
    mock_review(direct_vm, [fnd("1", "NOT_APPLICABLE"), fnd("2")])
    assert direct_vm.run_validator() is True


def test_every_cited_id_must_be_supported_not_just_one(reviewable, direct_vm):
    unrelated_verified(reviewable, direct_vm)
    direct_vm.clear_mocks()
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", ev=[1, 5])])
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", ev=[1])], refs=[1]) is False
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", ev=[1, 5])], refs=[1, 5]) is True


def test_every_finding_that_cites_evidence_is_checked(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1", ev=[1]), fnd("2", ev=[1])])
    assert validator_sees(direct_vm, [fnd("1", ev=[1]), fnd("2", ev=[1])], per_section={"1": [1], "2": []}) is False
    assert validator_sees(direct_vm, [fnd("1", ev=[1]), fnd("2", ev=[1])], per_section={"1": [], "2": [1]}) is False
    assert validator_sees(direct_vm, [fnd("1", ev=[1]), fnd("2", ev=[1])], per_section={"1": [1], "2": [1]}) is True


def test_unclear_findings_may_cite_a_failed_attempt_that_is_about_the_missing_fact(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", "UNCLEAR", ev=[3])])
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", "UNCLEAR", ev=[3])]) is True
    assert validator_sees(direct_vm, [fnd("1"), fnd("2", "UNCLEAR", ev=[3])], refs=[]) is False


@pytest.mark.parametrize(
    "answer",
    ['{"supporting_ids": "1"}', '{"supporting_ids": ["1"]}', '{"supporting_ids": [true]}', '{"other": [1]}', "not json"],
    ids=["string", "string-ids", "bool", "wrong-key", "prose"],
)
def test_an_unusable_reference_check_rejects(reviewable, direct_vm, answer):
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", ev=[1])])
    direct_vm.clear_mocks()
    mock_review(direct_vm, [fnd("1"), fnd("2", ev=[1])])
    direct_vm.mock_llm(r"EVIDENCE REFERENCE CHECK", answer)
    assert direct_vm.run_validator() is False


def test_the_reference_check_prompt_is_built_from_the_immutable_record_only(reviewable, direct_vm):
    leader_ran(reviewable, direct_vm, [fnd("1"), fnd("2", ev=[1])])
    direct_vm.clear_mocks()
    mock_review(direct_vm, [fnd("1"), fnd("2", ev=[1])])
    record = reviewable.get_evidence(1)
    direct_vm.mock_llm(
        r"\AEVIDENCE REFERENCE CHECK(?=[\s\S]*evidence_id: 1\nstatus: VERIFIED\nfact: "
        + record["normalized_fact"]
        + r"\nvalue: "
        + record["normalized_value"]
        + r")(?=[\s\S]*=== CHARTER SECTION)[\s\S]*",
        '{"supporting_ids": [1]}',
    )
    assert direct_vm.run_validator() is True
