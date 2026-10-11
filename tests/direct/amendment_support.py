"""Shared fixtures and helpers for the Stage 7 to 9 tests (amendments, governance guardrails, accountability).

No real LLM is used: these tests prove the contract's own rules (the lifecycle, authorization, staleness, atomicity, hashes, the prompt boundary,
the validator rule and the accountability records). They do NOT prove that a real model judges compatibility sensibly; that needs StudioNet."""

import json

from precedent_support import ITEMIZED, NO_BREAKDOWN, VIOLATED, findings, keccak_hex, propose, review, world  # noqa: F401
from review_support import mock_review, request

AMENDMENT_DOC = r"CHARTER AMENDMENT COMPATIBILITY CHECK"
RATIONALE = "The DAO needs this rule."
NEW_TITLE = "Timeline"
NEW_BODY = "Every funding proposal must state a delivery date."


def mock_amendment(vm, compatible=True, conflicts=(), *, must=(), must_not=(), raw=None):
    """What the (mocked) LLM returns for the amendment compatibility prompt."""
    payload = raw if raw is not None else {"compatible": compatible, "conflicting_section_ids": list(conflicts)}
    pattern = r"\A" + "".join(rf"(?=[\s\S]*{m})" for m in must) + "".join(rf"(?![\s\S]*{m})" for m in must_not)
    vm.mock_llm(pattern + r"[\s\S]*" + AMENDMENT_DOC, payload if isinstance(payload, str) else json.dumps(payload))


def version(c):
    return int(c.get_charter_version())


def amend(c, action="ADD", section="4", title=NEW_TITLE, body=NEW_BODY, base=None, rationale=RATIONALE, source=0):
    """Propose an amendment (against the current charter version unless `base` says otherwise) and return its id."""
    c.propose_amendment(action, section, title, body, version(c) if base is None else base, rationale, source)
    return int(c.get_amendment_count())


def evaluate(c, vm, amendment_id, compatible=True, conflicts=(), **kw):
    vm.clear_mocks()
    mock_amendment(vm, compatible, conflicts, **kw)
    c.request_amendment_evaluation(amendment_id)
    vm.clear_mocks()


def as_owner(vm, owner):
    vm.sender = owner


def lifecycle(c, vm, owner, proposer, **kw):
    """Propose (proposer), evaluate COMPATIBLE (proposer), approve (owner). Returns the id; the sender is left as the proposer."""
    vm.sender = proposer
    aid = amend(c, **kw)
    evaluate(c, vm, aid)
    vm.sender = owner
    c.approve_amendment(aid)
    vm.sender = proposer
    return aid


def snapshot(c):
    """Everything an amendment refusal must leave exactly as it was."""
    n = int(c.get_amendment_count())
    return {
        "version": version(c),
        "meta": c.get_dao_metadata(),
        "sections": c.get_charter_sections_page(0, 50),
        "amendments": [c.get_amendment_accountability(i) for i in range(1, n + 1)],
        "governance": c.get_governance_status(),
    }


__all__ = ["ITEMIZED", "NO_BREAKDOWN", "VIOLATED", "findings", "keccak_hex", "propose", "review", "world", "request", "mock_review"]
