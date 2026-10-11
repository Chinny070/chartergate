"""Stage 8: governance and execution guardrails across the WHOLE contract.

Every public write method is classified. A stranger calling a restricted method is refused at the contract boundary (not only in the frontend) and
changes nothing. A write method that is added later and not classified here fails the completeness test, so a new privileged action cannot slip in."""

import json
from pathlib import Path

import pytest

from amendment_support import ITEMIZED, NO_BREAKDOWN, VIOLATED, amend, evaluate, findings, propose, review, version, world  # noqa: F401  (fixture)
from appeal_support import GROUND, STATEMENT, mock_appeal
from repair_support import mock_repair
from review_support import mock_review

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "docs" / "charter_gate.schema.json").read_text(encoding="utf-8"))
WRITES = sorted(m for m, v in SCHEMA["methods"].items() if not v["readonly"])

# method -> (the refusal a stranger must get, a function building the arguments from the prepared fixtures)
RESTRICTED = {
    "add_charter_section": ("NOT_OWNER", lambda f: ["9", "Nine", "Body."]),
    "update_charter_section": ("NOT_OWNER", lambda f: ["3", "Budget", "A silent edit."]),
    "deactivate_charter_section": ("NOT_OWNER", lambda f: ["3"]),
    "enable_amendment_governance": ("NOT_OWNER", lambda f: []),
    "approve_amendment": ("NOT_OWNER", lambda f: [f["amendment"]]),
    "submit_evidence": ("NOT_PROPOSER", lambda f: [f["repairable"], "https://example.org/x", "STATIC_WEB", "Claim.", "team_token_allocation", "2"]),
    "request_constitutional_review": ("NOT_PROPOSER", lambda f: [f["unreviewed"]]),
    "submit_repair_revision": ("NOT_PROPOSER", lambda f: [f["repairable"], "T", "D", "A"]),
    "request_revision_review": ("NOT_PROPOSER", lambda f: [f["revision"]]),
    "request_appeal": ("NOT_PROPOSER", lambda f: [f["adverse_review"], GROUND, STATEMENT]),
    "request_reasoned_dissent": ("NOT_PROPOSER", lambda f: [f["appeal"]]),
    "report_execution": ("NOT_PROPOSER", lambda f: [f["approved"], "ATTEMPTED", "I did it."]),
    "request_amendment_evaluation": ("NOT_AUTHORIZED", lambda f: [f["amendment"]]),
    "reject_amendment": ("NOT_AUTHORIZED", lambda f: [f["amendment"]]),
    "apply_amendment": ("NOT_AUTHORIZED", lambda f: [f["amendment"]]),
    "close_stale_amendment": ("NOT_AUTHORIZED", lambda f: [f["amendment"]]),
}
# open by design: anyone may submit a proposal or propose an amendment; nothing takes effect until the restricted steps above.
OPEN_BY_DESIGN = {"submit_proposal", "propose_amendment"}


def test_every_public_write_method_is_classified():
    assert set(RESTRICTED) | OPEN_BY_DESIGN == set(WRITES), "classify every new write method: restricted (with its refusal) or open by design"


@pytest.fixture
def prepared(world, direct_vm):
    """Alice has: an unreviewed proposal, a REPAIRABLE one with a pending revision and an appeal, an ELIGIBLE one, and an open amendment."""
    f = {}
    f["repairable"] = propose(world, NO_BREAKDOWN)
    f["adverse_review"] = review(world, direct_vm, f["repairable"], findings(**VIOLATED))
    direct_vm.clear_mocks()
    mock_appeal(direct_vm, findings(**VIOLATED))
    world.request_appeal(f["adverse_review"], GROUND, STATEMENT)
    f["appeal"] = int(world.get_appeal_count())
    other = propose(world, NO_BREAKDOWN)
    review(world, direct_vm, other, findings(**VIOLATED))
    direct_vm.clear_mocks()
    mock_repair(direct_vm)
    world.submit_repair_revision(other, *ITEMIZED)
    f["revision"] = int(world.get_proposal_revision_count(other))
    f["approved"] = propose(world, ITEMIZED)
    review(world, direct_vm, f["approved"], findings())
    f["unreviewed"] = propose(world)
    f["amendment"] = amend(world)
    return f


def broad(c):
    from amendment_support import snapshot as amendment_snapshot

    n = int(c.get_proposal_count())
    return {
        "amendments": amendment_snapshot(c),
        "proposals": c.get_proposals_page(0, 50),
        "reviews": c.get_review_count(),
        "appeals": c.get_appeal_count(),
        "evidence": c.get_evidence_count(),
        "revisions": [c.get_proposal_revision_count(p) for p in range(1, n + 1)],
        "reports": [c.get_proposal_accountability(p)["reports"] for p in range(1, n + 1)],
        "dissents": [c.get_appeal_record(a)["dissent"] for a in range(1, int(c.get_appeal_count()) + 1)],
    }


@pytest.mark.parametrize("method", sorted(RESTRICTED))
def test_a_stranger_is_refused_at_the_contract_boundary_and_changes_nothing(world, direct_vm, direct_bob, prepared, method):
    code, build = RESTRICTED[method]
    before = broad(world)
    direct_vm.sender = direct_bob
    direct_vm.clear_mocks()  # no model is mocked: a refusal must come before any model call
    with direct_vm.expect_revert(f"EXPECTED:{code}"):
        getattr(world, method)(*build(prepared))
    assert broad(world) == before


@pytest.mark.parametrize("method", ["enable_amendment_governance", "approve_amendment", "add_charter_section", "update_charter_section", "deactivate_charter_section"])
def test_owner_only_methods_refuse_the_proposer_too(world, direct_vm, direct_alice, prepared, method):
    code, build = RESTRICTED[method]
    direct_vm.sender = direct_alice
    direct_vm.clear_mocks()
    with direct_vm.expect_revert(f"EXPECTED:{code}"):
        getattr(world, method)(*build(prepared))


@pytest.mark.parametrize(
    "method",
    ["submit_evidence", "request_constitutional_review", "submit_repair_revision", "request_revision_review", "request_appeal", "request_reasoned_dissent", "report_execution"],
)
def test_proposer_only_methods_refuse_the_owner_too(world, direct_vm, direct_owner, prepared, method):
    code, build = RESTRICTED[method]
    direct_vm.sender = direct_owner  # the owner governs the charter; they do not act for a proposer
    direct_vm.clear_mocks()
    with direct_vm.expect_revert(f"EXPECTED:{code}"):
        getattr(world, method)(*build(prepared))


# ---- replay: operations that happen once cannot happen twice ------------------------------------------------------------------------------------------


def test_once_only_operations_cannot_be_replayed(world, direct_vm, prepared):
    f = prepared
    direct_vm.clear_mocks()
    with direct_vm.expect_revert("EXPECTED:REVIEW_ALREADY_EXISTS"):
        world.request_constitutional_review(f["repairable"])
    with direct_vm.expect_revert("EXPECTED:APPEAL_ALREADY_EXISTS"):
        world.request_appeal(f["adverse_review"], GROUND, STATEMENT)
    with direct_vm.expect_revert("EXPECTED:REPAIR_NOT_ALLOWED"):
        world.submit_repair_revision(2, "T2", "D2", "A2")  # proposal 2 already has an unreviewed repair: its status is REVISED
    mock_review(direct_vm, findings())
    world.request_revision_review(f["revision"])
    with direct_vm.expect_revert("EXPECTED:REVIEW_ALREADY_EXISTS"):
        world.request_revision_review(f["revision"])


def test_governance_cannot_be_enabled_twice_and_the_owner_methods_stay_closed(world, direct_vm, direct_owner):
    direct_vm.sender = direct_owner
    world.enable_amendment_governance()
    with direct_vm.expect_revert("EXPECTED:GOVERNANCE_ALREADY_ENABLED"):
        world.enable_amendment_governance()
    with direct_vm.expect_revert("EXPECTED:AMENDMENT_GOVERNANCE_REQUIRED"):
        world.update_charter_section("3", "Budget", "Edit.")


# ---- stale decisions never authorize a new action ----------------------------------------------------------------------------------------------------------


def test_an_approval_given_for_one_charter_version_cannot_authorize_a_change_to_the_next(world, direct_vm, direct_owner, direct_alice):
    first = amend(world, section="4")
    second = amend(world, section="5", title="Other", body="Other.")
    for aid in (first, second):
        evaluate(world, direct_vm, aid)
    direct_vm.sender = direct_owner
    world.approve_amendment(first)
    world.approve_amendment(second)
    world.apply_amendment(first)
    with direct_vm.expect_revert("EXPECTED:AMENDMENT_STALE"):
        world.apply_amendment(second)  # approved, but for a charter that no longer exists
    assert version(world) == 5 and world.get_charter_section_count() == 4


# ---- earlier stages' guarantees survive the new ones ----------------------------------------------------------------------------------------------------


def test_an_amendment_cannot_make_precedent_or_a_review_substitute_for_the_charter_in_force(world, direct_vm, direct_owner, direct_alice):
    pid = propose(world)
    from amendment_support import lifecycle

    aid = lifecycle(world, direct_vm, direct_owner, direct_alice, action="UPDATE", section="3", title="Budget", body="Budgets are now optional.")
    world.apply_amendment(aid)
    direct_vm.clear_mocks()
    mock_review(direct_vm, findings(), must=[r"CHARTER IN FORCE AT SUBMISSION \(version 4\)"], must_not=[r"optional"])
    world.request_constitutional_review(pid)  # a proposal is judged under the charter it was submitted under, never the amended one
    assert world.get_constitutional_review(1)["charter_version"] == 4
