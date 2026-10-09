"""Proposal repair / revision re-review integration tests.

What is proven where
--------------------
* LOCALLY PROVEN (direct mode, tests/direct/test_repair_*.py, with a MOCKED LLM): lineage, admissibility derivation, validation of the
  structured assessment, the validator rule, revision hashes, re-review binding, evidence across revisions, prompt boundaries.
  None of that exercises a real model.
* THIS FILE, on GLSim (no Docker): the deployed contract answers the revision reads with the official schema, and the repair and
  revision-review requests are refused where the contract refuses them before any LLM is needed.
* REQUIRES STUDIONET (`needs_real_genvm`): everything that needs a real LLM adjudication by real validators, i.e. an accepted repair,
  a rejected (replacement) repair and the re-review of an accepted revision. GLSim here has no LLM provider key, so a mocked judgment is
  NOT presented as a live validator test. Run:

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
    assert tx_execution_succeeded(contract.add_charter_section(args=["s3", "Budget", "Every proposal needs a budget breakdown."]).transact())
    assert tx_execution_succeeded(contract.submit_proposal(args=["Atlas RPC Gateway", "An open-source gateway. 30000 USDC.", "Grant funding"]).transact())
    return contract


def test_revision_reads_before_any_repair(charter):
    assert charter.get_proposal_revision_count(args=[1]).call() == 0
    assert charter.get_proposal_revisions_page(args=[1, 0, 50]).call() == []
    effective = charter.get_effective_proposal(args=[1]).call()
    assert effective["revision_number"] == 1 and effective["revision_id"] == 0 and effective["status"] == "SUBMITTED"
    assert charter.get_proposal_review_count(args=[1]).call() == 0
    assert charter.get_repair_targets(args=[1]).call() == []


def test_the_repair_schema_is_the_deployed_schema():
    methods = SCHEMA["methods"]
    assert methods["submit_repair_revision"]["readonly"] is False and len(methods["submit_repair_revision"]["params"]) == 4
    assert methods["request_revision_review"]["readonly"] is False
    for name in (
        "get_proposal_revision",
        "get_proposal_revision_count",
        "get_proposal_revisions_page",
        "get_effective_proposal",
        "get_review_for_revision",
        "get_review_revision_id",
        "get_proposal_review_count",
        "get_proposal_reviews_page",
        "get_repair_targets",
    ):
        assert methods[name]["readonly"] is True
    assert not [m for m in methods if m.startswith(("edit_", "update_proposal", "set_status", "delete_"))]


def test_a_proposal_that_was_never_reviewed_cannot_be_repaired_and_nothing_changes(charter):
    receipt = charter.submit_repair_revision(args=[1, "Atlas RPC Gateway", "A repaired description with a budget.", "Grant funding"]).transact()
    assert not tx_execution_succeeded(receipt)
    assert charter.get_proposal_revision_count(args=[1]).call() == 0
    assert charter.get_proposal(args=[1]).call()["status"] == "SUBMITTED"


def test_reviewing_an_unknown_revision_reverts(charter):
    assert not tx_execution_succeeded(charter.request_revision_review(args=[1]).transact())
    assert charter.get_review_count(args=[]).call() == 0


@needs_real_genvm
def test_live_repair_assessment_and_re_review(charter):
    assert tx_execution_succeeded(charter.request_constitutional_review(args=[1]).transact())
    review = charter.get_review_for_proposal(args=[1]).call()
    if review["verdict"] != "REPAIRABLE":
        pytest.skip("the live review of the fixture was not REPAIRABLE; the repair path needs one")
    receipt = charter.submit_repair_revision(
        args=[1, "Atlas RPC Gateway", "An open-source gateway. Budget: 20000 USDC engineering, 10000 USDC audits; total 30000 USDC.", "Grant funding"]
    ).transact()
    assert tx_execution_succeeded(receipt), receipt
    assert charter.get_proposal(args=[1]).call()["status"] == "REVISED"
    assert tx_execution_succeeded(charter.request_revision_review(args=[1]).transact())
    assert charter.get_review_revision_id(args=[2]).call() == 1
