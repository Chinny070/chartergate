"""Shared fixtures and helpers for the Stage 4 repair / revision tests.

No real network or LLM is used: the direct harness mocks the web and the LLM. These tests prove the contract's own rules
(lineage, admissibility derivation, validation, equivalence, hashes, re-review binding). They do NOT prove that a real
model reaches sensible repair judgments; that needs StudioNet.
"""

import json
import re

import pytest

from evidence_support import PROPOSAL
from review_support import add_evidence, fnd, keccak_hex, mock_refs, mock_review, request, review_of

T_REVIEW = "2026-10-09T10:00:00Z"
T_REPAIR = "2026-10-09T11:00:00Z"
REPAIR_DOC = r"REPAIR ASSESSMENT"

S1 = ("1", "Mission", "Funding proposals must primarily support open-source developer infrastructure.")
S2 = ("2", "Transparency", "Funding recipients must disclose their material team token allocation, supported by VERIFIED evidence.")
S3 = ("3", "Budget", "Every funding proposal must contain a specific budget breakdown listing an amount for each cost category.")

ORIGINAL = (
    "Atlas RPC Gateway",
    "Atlas RPC Gateway is an open-source RPC gateway for blockchain developers. We request 30000 USDC in total for development.",
    "Grant 30000 USDC to Atlas RPC Gateway",
)
REPAIRED = (
    "Atlas RPC Gateway",
    "Atlas RPC Gateway is an open-source RPC gateway for blockchain developers. Budget: 12000 USDC engineering, 8000 USDC "
    "infrastructure, 6000 USDC audits, 4000 USDC documentation, total 30000 USDC.",
    "Grant 30000 USDC to Atlas RPC Gateway",
)
NFT = (
    "Gaming NFT Marketplace",
    "A closed-source marketplace for trading in-game NFT items, with a 5 percent platform fee.",
    "Grant 30000 USDC to the NFT marketplace",
)


def mock_repair(vm, *, purpose=True, scope=False, addressed=("3",), reason="Adds the missing budget breakdown.", raw=None, extra=None, must=(), must_not=()):
    """What the (mocked) LLM returns for the repair-assessment prompt. `must` / `must_not` are regexes the prompt itself
    must (not) match; no match means no mock, which fails the transaction."""
    payload = raw if raw is not None else {
        "same_fundamental_purpose": purpose,
        "material_scope_change": scope,
        "addressed_section_ids": list(addressed),
        "short_reason": reason,
        **(extra or {}),
    }
    pattern = r"\A" + "".join(f"(?=[\\s\\S]*{m})" for m in must) + "".join(f"(?![\\s\\S]*{m})" for m in must_not)
    vm.mock_llm(pattern + r"[\s\S]*" + REPAIR_DOC, payload if isinstance(payload, str) else json.dumps(payload))


def repair(c, text=REPAIRED, proposal_id=1):
    return c.submit_repair_revision(proposal_id, *text)


def make_proposal_under_review(c, vm, alice, findings, *, sections=(S1, S2, S3), warp=True):
    """Charter with `sections`, Alice's proposal 1 and one VERIFIED evidence record; a mocked first review with `findings`."""
    for s in sections:
        c.add_charter_section(*s)
    vm.sender = alice
    vm.warp("2026-10-09T09:00:00Z")
    c.submit_proposal(*ORIGINAL)
    add_evidence(c, vm)  # evidence #1, VERIFIED
    vm.warp(T_REVIEW)
    mock_review(vm, findings)
    request(c)
    vm.clear_mocks()
    vm.warp(T_REPAIR)


@pytest.fixture
def repairable(charter, direct_vm, direct_alice):
    """Review 1 of proposal 1 is REPAIRABLE: only section 3 (Budget) is violated, and it is repairable. Alice is the sender."""
    make_proposal_under_review(
        charter, direct_vm, direct_alice, [fnd("1"), fnd("2", ev=[1]), fnd("3", "VIOLATED", repairable=True, rationale="No budget breakdown.")]
    )
    assert review_of(charter)["verdict"] == "REPAIRABLE"
    return charter


@pytest.fixture
def two_targets(charter, direct_vm, direct_alice):
    """Review 1 is REPAIRABLE with TWO repairable violations: section 2 (Transparency) and section 3 (Budget)."""
    make_proposal_under_review(
        charter,
        direct_vm,
        direct_alice,
        [fnd("1"), fnd("2", "VIOLATED", repairable=True, rationale="Team allocation not disclosed."), fnd("3", "VIOLATED", repairable=True, rationale="No budget breakdown.")],
    )
    assert review_of(charter)["verdict"] == "REPAIRABLE"
    return charter


def accept_repair(c, vm, text=REPAIRED, addressed=("3",), proposal_id=1):
    vm.clear_mocks()
    mock_repair(vm, addressed=addressed)
    repair(c, text, proposal_id)
    vm.clear_mocks()


def review_revision(c, vm, findings, revision_id=1):
    vm.clear_mocks()
    mock_review(vm, findings)
    c.request_revision_review(revision_id)
    vm.clear_mocks()


def world(c):
    """Everything a failed repair must leave untouched."""
    n = int(c.get_proposal_count())
    return {
        "dao": c.get_dao_metadata(),
        "proposals": c.get_proposals_page(0, 50) if n else [],
        "evidence": c.get_evidence_page(0, 50),
        "reviews": c.get_proposal_reviews_page(1, 0, 50) if n else [],
        "review_count": c.get_review_count(),
        "revisions": c.get_proposal_revisions_page(1, 0, 50) if n else [],
        "effective": c.get_effective_proposal(1) if n else None,
    }


def revision_hash_reference(*, proposal_id=1, revision_number=2, parent=0, source_review=1, charter_version=4, text=REPAIRED, addressed=("3",)):
    """The documented canonical string (docs/PROPOSAL_REVISION_MODEL.md), written out independently of the contract."""
    collapse = lambda s: " ".join(s.split())  # noqa: E731
    lines = [
        "chartergate.revision.v1",
        f"proposal_id={proposal_id}",
        f"revision_number={revision_number}",
        f"parent_revision_id={parent}",
        f"source_review_id={source_review}",
        f"charter_version={charter_version}",
        f"title={collapse(text[0])}",
        f"description={collapse(text[1])}",
        f"requested_action={collapse(text[2])}",
        f"addressed_sections={','.join(addressed)}",
    ]
    return keccak_hex("\n".join(lines))
