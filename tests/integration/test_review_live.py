"""Constitutional review integration tests.

What is proven where
--------------------
* LOCALLY PROVEN (direct mode, tests/direct/test_review*.py, 100+ tests with a MOCKED LLM): context building,
  historical-charter and evidence-snapshot binding, validation of the LLM's structured output, deterministic verdict
  derivation, hashes, the validator rule and immutability. None of that exercises a real model.
* THIS FILE, on GLSim (no Docker): the deployed contract answers the review reads with the official schema, and the
  review request is refused where the contract refuses it before any LLM is needed.
* REQUIRES STUDIONET (`needs_real_genvm`): everything that needs a real LLM adjudication by real validators, i.e. the four
  acceptance fixtures (ELIGIBLE, INELIGIBLE, REPAIRABLE, INSUFFICIENT_EVIDENCE). GLSim here has no LLM provider key, so a
  mocked adjudication is NOT presented as a live validator test. Run:

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
    assert tx_execution_succeeded(contract.add_charter_section(args=["s2", "Transparency", "Disclose material token allocations."]).transact())
    assert tx_execution_succeeded(contract.submit_proposal(args=["Fund Atlas", "Open-source tool", "Grant funding"]).transact())
    return contract


def test_review_reads_before_any_review(charter):
    assert charter.get_review_count(args=[]).call() == 0
    assert charter.get_review_id_for_proposal(args=[1]).call() == 0
    assert charter.get_proposal(args=[1]).call()["status"] == "SUBMITTED"


def test_the_review_schema_is_the_deployed_schema():
    methods = SCHEMA["methods"]
    assert methods["request_constitutional_review"]["readonly"] is False
    for name in (
        "get_constitutional_review",
        "get_review_for_proposal",
        "get_review_id_for_proposal",
        "get_review_count",
        "get_review_findings_page",
        "get_review_evidence_ids_page",
    ):
        assert methods[name]["readonly"] is True
    assert not [m for m in methods if m.startswith(("set_", "edit_", "override_")) and "review" in m]


def test_review_of_an_unknown_proposal_reverts_without_consuming_a_review_id(charter):
    receipt = charter.request_constitutional_review(args=[99]).transact()
    assert not tx_execution_succeeded(receipt)
    assert charter.get_review_count(args=[]).call() == 0


@needs_real_genvm
def test_live_review_produces_a_verdict_and_updates_the_proposal(charter):
    receipt = charter.request_constitutional_review(args=[1]).transact()
    assert tx_execution_succeeded(receipt), receipt
    review = charter.get_review_for_proposal(args=[1]).call()
    assert review["verdict"] in ("ELIGIBLE", "INELIGIBLE", "REPAIRABLE", "INSUFFICIENT_EVIDENCE")
    assert review["charter_version"] == 3
    assert charter.get_proposal(args=[1]).call()["status"] == review["verdict"]
    # a second review of the same proposal is refused
    assert not tx_execution_succeeded(charter.request_constitutional_review(args=[1]).transact())
    assert charter.get_review_count(args=[]).call() == 1
