"""Shared fixtures and helpers for the Stage 6 appeal and reasoned-dissent tests.

No real network or LLM is used. These tests prove the contract's own rules (eligibility, the closed record, deterministic verdict and
disposition, effective verdict, repair and precedent interaction, hashes, prompt boundaries, equivalence, atomicity). They do NOT
prove that a real model reasons sensibly about an appeal; that needs StudioNet."""

import json
import re

from precedent_support import ITEMIZED, NO_BREAKDOWN, VIOLATED, findings, keccak_hex, propose, review, world  # noqa: F401
from review_support import fnd, mock_refs, mock_review, request

APPEAL_DOC = r"CONSTITUTIONAL APPEAL"
GROUND = "CHARTER_MISINTERPRETATION"
STATEMENT = "The budget rule was misread: the proposal does satisfy it."


def mock_appeal(
    vm,
    fs,
    *,
    must=(),
    must_not=(),
    pmust=(),
    pmust_not=(),
    cites=None,
    check=True,
    precedent_raw=None,
    extra=None,
    raw=None,
    refs=None,
):
    """What the (mocked) LLM returns for the appellate prompt, the precedent-consistency pass and the citation check.
    `fs` are findings as in review tests; a finding may carry "precedents" which are served to the precedent pass.
    `refs` is what the evidence-reference check answers (a list of supporting ids) when given."""
    cs = []
    if raw is None:
        base = []
        for f in fs:
            f = dict(f)
            for c in f.pop("precedents", None) or []:
                cs.append({"section_id": f["section_id"], **c})
            base.append(f)
        fs = base
    payload = raw if raw is not None else {"findings": fs, **(extra or {})}
    pattern = r"\A" + "".join(rf"(?=[\s\S]*{m})" for m in must) + "".join(rf"(?![\s\S]*{m})" for m in must_not)
    vm.mock_llm(pattern + r"[\s\S]*" + APPEAL_DOC, payload if isinstance(payload, str) else json.dumps(payload))
    ppat = r"\A" + "".join(rf"(?=[\s\S]*{m})" for m in pmust) + "".join(rf"(?![\s\S]*{m})" for m in pmust_not) + r"PRECEDENT CONSISTENCY ANALYSIS[\s\S]*"
    pay = precedent_raw if precedent_raw is not None else {"precedents": cs if cites is None else cites}
    vm.mock_llm(ppat, pay if isinstance(pay, str) else json.dumps(pay))
    if check is not None:
        vm.mock_llm(r"\APRECEDENT CITATION CHECK[\s\S]*", json.dumps({"supported": bool(check)}))
    if refs is not None:
        mock_refs(vm, refs)


def mock_dissent(vm, fs, *, must=(), must_not=(), supported=True, raw=None):
    """The dissent prompt and, for a validator, the defensibility check."""
    payload = raw if raw is not None else {"findings": fs}
    pattern = r"\A" + "".join(rf"(?=[\s\S]*{m})" for m in must) + "".join(rf"(?![\s\S]*{m})" for m in must_not)
    vm.mock_llm(pattern + r"REASONED DISSENT\n\n[\s\S]*", payload if isinstance(payload, str) else json.dumps(payload))
    if supported is not None:
        vm.mock_llm(r"\AREASONED DISSENT CHECK[\s\S]*", json.dumps({"supported": bool(supported)}))


def appeal(c, vm, review_id, fs, *, ground=GROUND, statement=STATEMENT, **kw):
    """File a (mocked) appeal and return its id."""
    vm.clear_mocks()
    mock_appeal(vm, fs, **kw)
    c.request_appeal(review_id, ground, statement)
    vm.clear_mocks()
    return int(c.get_appeal_count())


def dissent(c, vm, appeal_id, fs, **kw):
    vm.clear_mocks()
    mock_dissent(vm, fs, **kw)
    c.request_reasoned_dissent(appeal_id)
    vm.clear_mocks()
    return int(c.get_appeal_count())


def snapshot(c):
    """Everything an appeal or a dissent must leave exactly as it was (apart from what the test says changes)."""
    n = int(c.get_proposal_count())
    reviews = int(c.get_review_count())
    return {
        "proposals": c.get_proposals_page(0, 50) if n else [],
        "reviews": [c.get_constitutional_review(i) for i in range(1, reviews + 1)],
        "findings": [c.get_review_findings_page(i, 0, 50) for i in range(1, reviews + 1)],
        "precedents": [c.get_review_precedents(i) for i in range(1, reviews + 1)],
        "evidence": c.get_evidence_page(0, 50),
        "sections": c.get_charter_sections_page(0, 50),
        "targets": [c.get_repair_targets(p) for p in range(1, n + 1)],
    }


def effective(c, proposal_id):
    return c.get_effective_ruling(proposal_id)


def adverse_review(c, vm, text=NO_BREAKDOWN, fs=None):
    """A proposal whose review is REPAIRABLE on section 3. Returns (proposal_id, review_id)."""
    pid = propose(c, text)
    rid = review(c, vm, pid, fs if fs is not None else findings(**VIOLATED))
    return pid, rid


def reversed_fs():
    """Appellate findings that correct the original (section 3 satisfied)."""
    return findings()


__all__ = [
    "ITEMIZED",
    "NO_BREAKDOWN",
    "VIOLATED",
    "findings",
    "fnd",
    "keccak_hex",
    "propose",
    "review",
    "world",
    "request",
    "re",
]
