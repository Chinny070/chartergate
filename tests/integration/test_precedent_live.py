"""Precedent memory integration tests.

What is proven where
--------------------
* LOCALLY PROVEN (direct mode, tests/direct/test_precedent_*.py, with a MOCKED LLM): rule identity, bounded deterministic candidate selection,
  snapshots, citation validation, hashes, prompt boundaries and the validator rule. None of that exercises a real model.
* THIS FILE, on GLSim (no Docker): the deployed contract answers the precedent reads with the official schema, and a first review has no precedent.
* REQUIRES STUDIONET (`needs_real_genvm`): everything that needs real LLM adjudication, i.e. a second review that actually sees and cites a prior ruling. GLSim
  here has no LLM provider key, so a mocked judgment is NOT presented as a live validator test. Run:

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
    assert tx_execution_succeeded(contract.add_charter_section(args=["s3", "Budget", "Every proposal needs a budget breakdown."]).transact())
    assert tx_execution_succeeded(contract.submit_proposal(args=["Atlas RPC Gateway", "An open-source gateway. 30000 USDC.", "Grant funding"]).transact())
    return contract


def test_the_rule_index_is_empty_before_any_review(charter):
    assert charter.get_rule_precedent_count(args=["s3@2"]).call() == 0
    assert charter.get_rule_precedents_page(args=["s3@2", 0, 50]).call() == []


def test_the_precedent_schema_is_the_deployed_schema():
    methods = SCHEMA["methods"]
    for name in ("get_review_precedents", "get_rule_precedent_count", "get_rule_precedents_page", "get_precedent_case"):
        assert methods[name]["readonly"] is True
    assert len(methods["get_rule_precedents_page"]["params"]) == 3
    assert not [m for m in methods if "precedent" in m and not methods[m]["readonly"]]  # there is no method that writes precedent directly


def test_reading_the_precedents_of_an_unknown_review_reverts(charter):
    with pytest.raises(Exception):
        charter.get_review_precedents(args=[1]).call()
    with pytest.raises(Exception):
        charter.get_precedent_case(args=[1, "s3"]).call()


@needs_real_genvm
def test_live_second_review_sees_the_first_as_precedent(charter):
    assert tx_execution_succeeded(charter.request_constitutional_review(args=[1]).transact())
    assert tx_execution_succeeded(charter.submit_proposal(args=["Atlas Indexer", "An open-source indexer. 24000 USDC.", "Grant funding"]).transact())
    assert tx_execution_succeeded(charter.request_constitutional_review(args=[2]).transact())
    seen = charter.get_review_precedents(args=[2]).call()
    assert [c["precedent_review_id"] for c in seen["candidates"]] == [1]
    assert seen["precedent_set_hash"].startswith("0x")
