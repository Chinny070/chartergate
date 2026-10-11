"""Amendments, governance guardrails and accountability integration tests.

What is proven where
--------------------
* LOCALLY PROVEN (direct mode, tests/direct/test_amendment_*.py, test_accountability.py, test_governance_guardrails.py, with a MOCKED LLM): the lifecycle,
  authorization, staleness, atomicity, hashes, the prompt boundary and the validator rule. None of that exercises a real model.
* THIS FILE, on GLSim (no Docker): the deployed contract answers the new reads with the official schema, and the deterministic steps (proposing, rejecting, the
  governance switch, refusals) behave as specified. A mocked judgment is NOT presented as a live validator test.
* REQUIRES STUDIONET (`needs_real_genvm`): the compatibility evaluation, which needs real LLM validators. Run:

      CHARTERGATE_REAL_GENVM=1 gltest tests/integration/ -v -s --network studionet

Start a fresh GLSim for repeatable runs (it keeps state across deployments in one process).
"""

import json
import os
from pathlib import Path

import pytest
from gltest import get_contract_factory
from gltest.assertions import tx_execution_succeeded
from gltest.contracts.contract import Contract

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "docs" / "charter_gate.schema.json").read_text(encoding="utf-8"))

REAL_GENVM = os.environ.get("CHARTERGATE_REAL_GENVM") == "1"
needs_real_genvm = pytest.mark.skipif(
    not REAL_GENVM,
    reason="needs real GenVM with LLM-backed validators; GLSim here has no LLM key. Set CHARTERGATE_REAL_GENVM=1 on StudioNet",
)


@pytest.fixture(scope="module")
def charter():
    factory = get_contract_factory("CharterGate")
    deployed = factory.deploy(args=["Atlas DAO", "A DAO that funds open-source infrastructure."])
    contract = Contract.new(address=deployed.address, schema=SCHEMA, account=deployed.account)
    assert tx_execution_succeeded(contract.add_charter_section(args=["s1", "Mission", "Fund open-source infrastructure."]).transact())
    assert tx_execution_succeeded(contract.add_charter_section(args=["s3", "Budget", "Every proposal needs an itemized budget."]).transact())
    return contract


def test_governance_starts_off_and_the_charter_is_at_version_three(charter):
    g = charter.get_governance_status(args=[]).call()
    assert g["governance_enabled"] is False and g["charter_version"] == 3 and g["amendment_count"] == 0


def test_the_new_schema_is_the_deployed_schema():
    methods = SCHEMA["methods"]
    writes = ("enable_amendment_governance", "propose_amendment", "request_amendment_evaluation", "approve_amendment", "reject_amendment", "apply_amendment", "close_stale_amendment", "report_execution")
    reads = ("get_governance_status", "get_amendment", "get_amendment_count", "get_amendments_page", "get_amendment_accountability", "get_proposal_accountability", "get_precedent_overview")
    for name in writes:
        assert methods[name]["readonly"] is False
    for name in reads:
        assert methods[name]["readonly"] is True
    assert len(methods["propose_amendment"]["params"]) == 7 and len(methods) == 72


def test_the_precedent_overview_lists_every_active_rule_with_no_reviews_yet(charter):
    rules = charter.get_precedent_overview(args=[]).call()
    assert [(r["section_id"], r["rule"], r["review_count"]) for r in rules] == [("s1", "s1@2", 0), ("s3", "s3@3", 0)]


def test_a_stale_or_invalid_amendment_is_refused_and_a_valid_one_is_recorded(charter):
    stale = charter.propose_amendment(args=["ADD", "s4", "Timeline", "State a delivery date.", 1, "Needed.", 0]).transact()
    assert not tx_execution_succeeded(stale)  # written against version 1, but the charter is at 3
    bad = charter.propose_amendment(args=["DELETE", "s4", "Timeline", "Body.", 3, "Needed.", 0]).transact()
    assert not tx_execution_succeeded(bad)
    assert charter.get_amendment_count(args=[]).call() == 0
    assert tx_execution_succeeded(charter.propose_amendment(args=["ADD", "s4", "Timeline", "State a delivery date.", 3, "Needed.", 0]).transact())
    acc = charter.get_amendment_accountability(args=[1]).call()
    assert acc["amendment"]["status"] == "PROPOSED" and acc["execution_state"] == "NOT_APPROVED" and acc["contract_verified"] is True
    assert [e["kind"] for e in acc["events"]] == ["PROPOSED"]


def test_an_unevaluated_amendment_cannot_be_approved_or_applied(charter):
    assert not tx_execution_succeeded(charter.approve_amendment(args=[1]).transact())
    assert not tx_execution_succeeded(charter.apply_amendment(args=[1]).transact())
    assert charter.get_amendment(args=[1]).call()["status"] == "PROPOSED"
    assert charter.get_charter_version(args=[]).call() == 3


def test_execution_cannot_be_reported_for_an_unreviewed_proposal(charter):
    assert tx_execution_succeeded(charter.submit_proposal(args=["Atlas Gateway", "An open-source gateway.", "Grant funding"]).transact())
    assert not tx_execution_succeeded(charter.report_execution(args=[1, "ATTEMPTED", "Started."]).transact())
    acc = charter.get_proposal_accountability(args=[1]).call()
    assert (acc["approved"], acc["execution_state"], acc["verified"], acc["reports"]) == (False, "NOT_APPROVED", False, [])


def test_the_governance_switch_closes_the_direct_owner_methods(charter):
    assert tx_execution_succeeded(charter.reject_amendment(args=[1]).transact())  # the proposer withdraws
    assert charter.get_amendment(args=[1]).call()["status"] == "REJECTED"
    assert tx_execution_succeeded(charter.enable_amendment_governance(args=[]).transact())
    assert charter.get_governance_status(args=[]).call()["governance_enabled"] is True
    assert not tx_execution_succeeded(charter.add_charter_section(args=["s9", "Nine", "Body."]).transact())
    assert not tx_execution_succeeded(charter.enable_amendment_governance(args=[]).transact())  # one way
    assert charter.get_charter_version(args=[]).call() == 3


@needs_real_genvm
def test_live_evaluation_advises_and_the_owner_decides(charter):
    assert tx_execution_succeeded(charter.propose_amendment(args=["ADD", "s5", "Timeline", "State a delivery date.", 3, "Needed.", 0]).transact())
    assert tx_execution_succeeded(charter.request_amendment_evaluation(args=[2]).transact())
    a = charter.get_amendment(args=[2]).call()
    assert a["status"] == "EVALUATED" and a["eval_verdict"] in ("COMPATIBLE", "CONFLICTING")
