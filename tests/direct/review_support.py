"""Shared fixtures and helpers for the Stage 3 constitutional review tests.

No real network or LLM is used. The direct harness mocks the web and the LLM, so these tests prove the contract's
own rules (context building, validation, derivation, hashing, equivalence). They do NOT prove that a real LLM
reaches sensible findings: that needs StudioNet.
"""

import json
import re

import pytest

from conftest import MISSION, TRANSPARENCY
from evidence_support import (
    CLAIM_NUMBERED,
    FACT,
    PROPOSAL,
    T_EVIDENCE,
    URL,
    mock_answer,
    mock_page,
    page,
    reset,
    submit,
)

T_REVIEW = "2026-10-09T10:00:00Z"
DOC = r"CONSTITUTIONAL REVIEW"


def keccak_hex(text: str) -> str:
    from genlayer.py.keccak import Keccak256

    h = Keccak256()
    h.update(text.encode("utf-8"))
    return "0x" + h.hexdigest()


def fnd(section_id, finding="SATISFIED", *, repairable=False, ev=(), missing=None, rationale="ok"):
    """One finding as the LLM would return it."""
    if missing is None:
        missing = "a fact that is not verified" if finding == "UNCLEAR" else ""
    return {
        "section_id": section_id,
        "finding": finding,
        "repairable": repairable,
        "evidence_ids": list(ev),
        "missing_fact": missing,
        "rationale": rationale,
    }


def all_findings(s1=None, s2=None):
    return [s1 or fnd("1"), s2 or fnd("2", ev=[1])]


def mock_review(vm, findings, *, extra=None, raw=None, must=(), must_not=(), pmust=(), pmust_not=(), check=True, precedent_raw=None, cmust=(), cmust_not=()):
    """What the (mocked) LLM returns for the review prompt. `must` / `must_not` are regexes that the prompt
    itself must (not) match, so a test can prove what the prompt contained: no match means no mock, which
    fails the transaction.

    Stage 5.1: precedent is a SEPARATE pass. A finding that carries a "precedents" list is stripped from the base answer, and the
    citations are served to the precedent-consistency prompt (`pmust` / `pmust_not` constrain THAT prompt). `check` is what the
    validators' per-citation semantic check answers (True, False, or a callable taking the prompt)."""
    cites = []
    if raw is None:
        base = []
        for f in findings:
            if not isinstance(f, dict):
                base.append(f)
                continue
            f = dict(f)
            for c in f.pop("precedents", None) or []:
                cites.append({"section_id": f["section_id"], **c})
            base.append(f)
        findings = base
    payload = raw if raw is not None else {"findings": findings, **(extra or {})}
    pattern = r"\A" + "".join(rf"(?=[\s\S]*{m})" for m in must) + "".join(rf"(?![\s\S]*{m})" for m in must_not)
    vm.mock_llm(pattern + r"[\s\S]*" + DOC, payload if isinstance(payload, str) else json.dumps(payload))
    ppat = r"\A" + "".join(rf"(?=[\s\S]*{m})" for m in pmust) + "".join(rf"(?![\s\S]*{m})" for m in pmust_not) + r"PRECEDENT CONSISTENCY ANALYSIS[\s\S]*"
    pay = precedent_raw if precedent_raw is not None else {"precedents": cites}
    vm.mock_llm(ppat + r"[\s\S]*", pay if isinstance(pay, str) else json.dumps(pay))
    if check is not None:
        cpat = r"\A" + "".join(rf"(?=[\s\S]*{m})" for m in cmust) + "".join(rf"(?![\s\S]*{m})" for m in cmust_not) + r"PRECEDENT CITATION CHECK[\s\S]*"
        vm.mock_llm(cpat, json.dumps({"supported": bool(check)}))


def mock_refs(vm, supporting=(), *, per_section=None):
    """What the (mocked) LLM answers to the EVIDENCE REFERENCE CHECK for each finding that cites evidence.
    `per_section` maps a section id to the ids the check should call supporting; every other section gets `supporting`."""
    for section_id, ids in (per_section or {}).items():
        vm.mock_llm(
            r"EVIDENCE REFERENCE CHECK[\s\S]*=== UNTRUSTED FINDING UNDER CHECK ===\n<<<DATA\nsection_id: " + re.escape(section_id) + r"\n",
            json.dumps({"supporting_ids": list(ids)}),
        )
    vm.mock_llm(r"EVIDENCE REFERENCE CHECK", json.dumps({"supporting_ids": list(supporting)}))


def request(c, proposal_id=1):
    return c.request_constitutional_review(proposal_id)


def add_evidence(c, vm, *, html=None, status=200, body=None, answer=None, claim=CLAIM_NUMBERED, fact=FACT, kind="STATIC_WEB"):
    reset(vm)
    mock_page(vm, html if html is not None else page(), status=status, body=body)
    mock_answer(vm, **(answer or {}))
    submit(c, claim=claim, fact_key=fact, source_kind=kind)
    reset(vm)


@pytest.fixture
def reviewable(charter, direct_vm, direct_alice):
    """Charter v3 (s1 Mission, s2 Transparency). Alice's proposal 1 was submitted under v3. Evidence on it:
    #1 VERIFIED, #2 UNVERIFIABLE, #3 SOURCE_UNAVAILABLE, #4 INVALID_SOURCE. Alice is the active sender."""
    charter.add_charter_section(*MISSION)
    charter.add_charter_section(*TRANSPARENCY)
    direct_vm.sender = direct_alice
    direct_vm.warp(T_EVIDENCE)
    charter.submit_proposal(*PROPOSAL)
    add_evidence(charter, direct_vm)  # 1 VERIFIED
    add_evidence(
        charter,
        direct_vm,
        claim="Atlas team token allocation is 99%.",
        fact="claimed_allocation",
        answer=dict(supported=False, value="46%", excerpt="Team: 46% Community: 30%"),
    )  # 2 UNVERIFIABLE (the page states 46%, not the claimed 99%)
    add_evidence(charter, direct_vm, status=404, body="gone", fact="missing_page_fact")  # 3 SOURCE_UNAVAILABLE
    add_evidence(charter, direct_vm, body="", fact="empty_page_fact")  # 4 INVALID_SOURCE
    assert [charter.get_evidence(i)["status"] for i in (1, 2, 3, 4)] == [
        "VERIFIED",
        "UNVERIFIABLE",
        "SOURCE_UNAVAILABLE",
        "INVALID_SOURCE",
    ]
    direct_vm.warp(T_REVIEW)
    return charter


def review_of(c, proposal_id=1):
    return c.get_review_for_proposal(proposal_id)


def findings_of(c, review_id=1):
    return c.get_review_findings_page(review_id, 0, 50)


def world(c):
    """Everything a failed or repeated review must leave untouched."""
    n = c.get_proposal_count()
    return {
        "dao": c.get_dao_metadata(),
        "sections": c.get_charter_sections_page(0, 50),
        "proposals": c.get_proposals_page(0, 50) if n else [],
        "evidence": c.get_evidence_page(0, 50),
        "reviews": c.get_review_count(),
    }
