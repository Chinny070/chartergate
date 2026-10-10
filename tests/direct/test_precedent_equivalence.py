"""Stage 5 validator rule (docs/STAGE_5_EQUIVALENCE.md).

Each test runs the REAL leader once, then replays the REAL validator after changing what the (mocked) LLM returns for the validator
or after tampering with the leader's result. A validator VALIDATES the leader's cited subset; it does not have to choose the same
optional citations itself, and it never compares precedent prose."""

import copy

import pytest

from precedent_support import ITEMIZED, VIOLATED, add_verified_evidence, cite, findings, keccak_hex, propose, review, world  # noqa: F401
from review_support import fnd, mock_refs, mock_review, request


def cited_ids(result):
    fs = result.get("findings") if isinstance(result, dict) else None
    if not isinstance(fs, list):
        return []
    return sorted({i for f in fs if isinstance(f, dict) for i in f.get("evidence_ids", []) if isinstance(i, int)})


def replay(vm, vfindings=None, *, leader_result=None, raw=None):
    leader = leader_result if leader_result is not None else vm._captured_validators[-1][0]
    vm.clear_mocks()
    mock_review(vm, vfindings, raw=raw)
    mock_refs(vm, cited_ids(leader))
    kw = {"leader_result": leader_result} if leader_result is not None else {}
    return vm.run_validator(**kw)


@pytest.fixture
def case(world, direct_vm):
    """Review 1: VIOLATED on section 3. Proposal 2 is reviewed by the leader with the given findings; the validator is replayed."""
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    propose(world)  # proposal 2: the same omission

    def run(leader_findings):
        direct_vm.clear_mocks()
        mock_review(direct_vm, leader_findings)
        request(world, 2)
        stored = copy.deepcopy(direct_vm._captured_validators[-1][0])
        direct_vm.clear_mocks()
        return stored

    return run


FOLLOWED = dict(precedents={"3": [cite(1, "FOLLOWED", "Same omission as review 1.")]}, **VIOLATED)


# ---- accept ---------------------------------------------------------------------------------------------------------------


def test_identical_judgment_with_a_followed_citation_is_accepted(case, direct_vm):
    case(findings(**FOLLOWED))
    assert replay(direct_vm, findings(**FOLLOWED)) is True


def test_equivalent_judgment_with_different_precedent_prose_is_accepted(case, direct_vm):
    case(findings(**FOLLOWED))
    other = findings(precedents={"3": [cite(1, "FOLLOWED", "A completely different explanation of the same thing.")]}, **VIOLATED)
    assert replay(direct_vm, other) is True


def test_a_validator_that_cites_nothing_still_accepts_the_leaders_valid_citation(case, direct_vm):
    case(findings(**FOLLOWED))
    assert replay(direct_vm, findings(**VIOLATED)) is True  # the optional subset is validated, not re-chosen


def test_a_validator_never_runs_its_own_precedent_pass_so_its_would_be_citations_are_irrelevant(case, direct_vm):
    case(findings(**FOLLOWED))
    junk = findings(precedents={"3": [cite(99, "FOLLOWED", ""), cite(1, "OVERRULED", "x")]}, **VIOLATED)
    assert replay(direct_vm, junk) is True  # Stage 5.1: the validator has no precedent pass of its own; junk is never read


def test_a_valid_distinction_is_accepted(case, direct_vm):
    leader = findings(precedents={"3": [cite(1, "DISTINGUISHED", "The current proposal itemizes its budget.")]})
    case(leader)
    assert replay(direct_vm, findings()) is True


def test_the_untampered_result_still_passes(case, direct_vm):
    stored = case(findings(**FOLLOWED))
    assert replay(direct_vm, findings(**FOLLOWED), leader_result=stored) is True


# ---- reject: the current judgment differs (Stage 3 rules still apply) ----------------------------------------------------------


def test_a_different_current_finding_is_rejected_even_with_matching_citations(case, direct_vm):
    case(findings(**FOLLOWED))
    assert replay(direct_vm, findings(precedents=FOLLOWED["precedents"])) is False  # the validator finds section 3 SATISFIED


def test_a_different_repairability_is_rejected(case, direct_vm):
    case(findings(**FOLLOWED))
    other = findings(s3="VIOLATED", s3_kw=dict(repairable=False), precedents={"3": []})
    assert replay(direct_vm, other) is False


def test_a_validator_whose_own_output_is_unusable_rejects(case, direct_vm):
    case(findings(**FOLLOWED))
    assert replay(direct_vm, raw="not json") is False


# ---- reject: tampered leader results ----------------------------------------------------------------------------------------------------


def tamper(**changes):
    def apply(r):
        r.update(changes)

    return apply


def set_citations(cs):
    def apply(r):
        r["precedents"] = cs

    return apply


def with_finding(index, **changes):
    def apply(r):
        r["findings"][index].update(changes)

    return apply


GOOD = {"section_id": "3", "review_id": 1, "treatment": "FOLLOWED", "reason": "x"}
TAMPERED = [
    ("precedent-set-hash-tampered", tamper(precedent_set_hash="0x" + "ab" * 32)),
    ("precedent-set-hash-dropped-to-empty", tamper(precedent_set_hash="")),
    ("citation-outside-the-snapshot", set_citations([{**GOOD, "review_id": 99}])),
    ("citation-of-the-current-review", set_citations([{**GOOD, "review_id": 2}])),
    ("citation-for-an-unknown-section", set_citations([{**GOOD, "section_id": "9"}])),
    ("incompatible-followed", with_finding(2, finding="SATISFIED", repairable=False)),
    ("unknown-treatment", set_citations([{**GOOD, "treatment": "OVERRULED"}])),
    ("distinguished-without-a-reason", set_citations([{**GOOD, "treatment": "DISTINGUISHED", "reason": ""}])),
    ("oversized-reason", set_citations([{**GOOD, "reason": "x" * 201}])),
    ("duplicate-citation", set_citations([GOOD, GOOD])),
    ("three-citations", set_citations([GOOD, {**GOOD, "review_id": 1}, {**GOOD, "review_id": 1}])),
    ("citation-extra-key", set_citations([{**GOOD, "weight": 5}])),
    ("citation-missing-key", set_citations([{"section_id": "3", "review_id": 1, "treatment": "FOLLOWED"}])),
    ("citations-not-a-list", tamper(precedents="review 1")),
    ("precedents-key-missing", lambda r: r.pop("precedents")),
    ("precedent-key-extra", tamper(note="x")),
    ("prior-evidence-used-as-current-evidence", with_finding(1, evidence_ids=[1])),
]


@pytest.mark.parametrize("mutate", [m for _n, m in TAMPERED], ids=[n for n, _m in TAMPERED])
def test_tampered_leader_results_are_rejected(case, direct_vm, mutate):
    stored = case(findings(**FOLLOWED))
    mutate(stored)
    assert replay(direct_vm, findings(**FOLLOWED), leader_result=stored) is False


def test_tampered_candidate_order_is_rejected(case, direct_vm, world):
    stored = case(findings(**FOLLOWED))
    cands = world.get_review_precedents(2)["candidates"]
    assert stored["precedent_set_hash"] != ""

    def canonical(order):
        lines = ["chartergate.precedents.v1", f"count={len(order)}"]
        for x in order:
            lines.append(f"section={x['section_id']}|rule={x['rule']}|precedent_review_id={x['precedent_review_id']}|precedent_review_hash={x['precedent_review_hash']}")
        return keccak_hex("\n".join(lines))

    assert canonical(cands) == stored["precedent_set_hash"]  # the documented order is the one the leader committed to
    flipped = copy.deepcopy(stored)
    flipped["precedent_set_hash"] = canonical(list(reversed(cands)))
    assert replay(direct_vm, findings(**FOLLOWED), leader_result=flipped) is False


def test_precedent_evidence_is_never_valid_as_current_evidence_in_a_leader_result(world, direct_vm):
    p1 = propose(world)
    add_verified_evidence(world, direct_vm, p1)  # evidence #1 belongs to proposal 1
    review(world, direct_vm, p1, findings(s2_kw=dict(ev=[1])))
    propose(world, ITEMIZED)
    direct_vm.clear_mocks()
    mock_review(direct_vm, findings(s2="UNCLEAR"))
    request(world, 2)
    stored = copy.deepcopy(direct_vm._captured_validators[-1][0])
    stored["findings"][1].update(finding="SATISFIED", missing_fact="", evidence_ids=[1])  # a leader that borrowed the prior evidence
    stored["verdict"] = "ELIGIBLE"
    assert replay(direct_vm, findings(s2="UNCLEAR"), leader_result=stored) is False
