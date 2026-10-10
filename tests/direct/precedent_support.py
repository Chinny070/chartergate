"""Shared fixtures and helpers for the Stage 5 precedent-memory tests.

No real network or LLM is used. These tests prove the contract's own rules (rule identity, deterministic bounded candidate
selection, snapshots, citation validation, hashes, prompt boundaries, equivalence). They do NOT prove that a real model reasons
sensibly about precedent; that needs StudioNet."""

import json
import re

import pytest

from conftest import MISSION, TRANSPARENCY
from evidence_support import mock_answer, mock_page, page, reset, submit
from review_support import fnd, keccak_hex, mock_refs, mock_review, request

BUDGET = ("3", "Budget", "Every funding proposal must contain a specific budget breakdown listing an amount for each cost category.")
T = "2026-10-09T10:00:00Z"
RULE = lambda sid, rev: f"{sid}@{rev}"  # noqa: E731  (rule identity: section id + revision version)

NO_BREAKDOWN = ("Atlas Docs", "Atlas Docs is an open-source documentation tool. We request 18000 USD in total.", "Grant 18000 USD")
ITEMIZED = ("Atlas Gateway", "Atlas Gateway is an open-source RPC gateway. Budget: 8000 USD engineering, 6000 USD audits, 4000 USD docs.", "Grant 18000 USD")


def f3(kind="SATISFIED", **kw):
    return fnd("3", kind, **kw)


def findings(s3="SATISFIED", s3_kw=None, s1="SATISFIED", s2="SATISFIED", s2_kw=None, precedents=None):
    """LLM findings for the three-section charter. `precedents` maps a section id to a list of citations."""
    out = [fnd("1", s1), fnd("2", s2, **(s2_kw or {})), fnd("3", s3, **(s3_kw or {}))]
    for f in out:
        cites = (precedents or {}).get(f["section_id"])
        if cites is not None:
            f["precedents"] = cites
    return out


def cite(review_id, treatment="FOLLOWED", reason=""):
    return {"review_id": review_id, "treatment": treatment, "reason": reason}


VIOLATED = dict(s3="VIOLATED", s3_kw=dict(repairable=True, rationale="No budget breakdown."))


@pytest.fixture
def world(charter, direct_vm, direct_alice):
    """Charter v4 (s1 Mission, s2 Transparency, s3 Budget; revisions s1@2 s2@3 s3@4). Alice is the sender."""
    for s in (MISSION, TRANSPARENCY, BUDGET):
        charter.add_charter_section(*s)
    direct_vm.sender = direct_alice
    direct_vm.warp(T)
    return charter


def propose(c, text=NO_BREAKDOWN):
    c.submit_proposal(*text)
    return int(c.get_proposal_count())


def review(c, vm, proposal_id, fs):
    """Request a (mocked) review of `proposal_id` and return its review id."""
    vm.clear_mocks()
    mock_review(vm, fs)
    request(c, proposal_id)
    vm.clear_mocks()
    return int(c.get_review_count())


def precedents_of(c, review_id):
    return c.get_review_precedents(review_id)


def candidates_for(c, review_id, section):
    return [x["precedent_review_id"] for x in c.get_review_precedents(review_id)["candidates"] if x["section_id"] == section]


def precedent_set_hash_reference(c, review_id):
    """The documented canonical string (docs/PRECEDENT_MEMORY_MODEL.md), written out independently of the contract."""
    cands = c.get_review_precedents(review_id)["candidates"]
    lines = ["chartergate.precedents.v1", f"count={len(cands)}"]
    for x in cands:
        lines.append(f"section={x['section_id']}|rule={x['rule']}|precedent_review_id={x['precedent_review_id']}|precedent_review_hash={x['precedent_review_hash']}")
    return keccak_hex("\n".join(lines)) if cands else ""


def add_verified_evidence(c, vm, proposal_id, fact="team_token_allocation", claim="Atlas team token allocation is 46%.", section="2"):
    reset(vm)
    mock_page(vm, page())
    mock_answer(vm)
    submit(c, proposal_id=proposal_id, claim=claim, fact_key=fact, related_section_id=section)
    reset(vm)
