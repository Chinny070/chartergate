"""Appeals and reasoned dissent integration tests.

What is proven where
--------------------
* LOCALLY PROVEN (direct mode, tests/direct/test_appeal_*.py and test_dissent.py, with a MOCKED LLM): eligibility, the closed record, the
  deterministic verdict and disposition, the effective verdict, repair and precedent interaction, hashes, prompt boundaries, validator rules
  and atomicity. None of that exercises a real model.
* THIS FILE, on GLSim (no Docker): the deployed contract answers the appeal reads with the official schema, refuses appeals that cannot
  exist, and reports a proposal with no review as uncontrolled. A mocked judgment is NOT presented as a live validator test.
* REQUIRES STUDIONET (`needs_real_genvm`): everything that needs real LLM adjudication, i.e. an appeal that is actually decided and a dissent
  that is actually generated. Run:

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
    assert tx_execution_succeeded(contract.add_charter_section(args=["s3", "Budget", "Every proposal needs an itemized budget breakdown."]).transact())
    assert tx_execution_succeeded(contract.submit_proposal(args=["Atlas RPC Gateway", "An open-source gateway. 30000 USDC.", "Grant funding"]).transact())
    return contract


def test_there_are_no_appeals_before_any_review(charter):
    assert charter.get_appeal_count(args=[]).call() == 0


def test_a_proposal_with_no_review_is_not_controlled_by_anything(charter):
    ruling = charter.get_effective_ruling(args=[1]).call()
    assert ruling["controlled_by"] == "NONE" and ruling["effective_verdict"] == "" and ruling["findings"] == [] and ruling["appealable"] is False


def test_the_appeal_schema_is_the_deployed_schema():
    methods = SCHEMA["methods"]
    for name in (
        "get_appeal",
        "get_appeal_count",
        "get_appeal_id_for_review",
        "get_appellate_decision",
        "get_appeal_findings_page",
        "get_appeal_record",
        "get_review_appeal_status",
        "get_reasoned_dissent",
        "get_effective_ruling",
    ):
        assert methods[name]["readonly"] is True
    assert methods["request_appeal"]["readonly"] is False and len(methods["request_appeal"]["params"]) == 3
    assert methods["request_reasoned_dissent"]["readonly"] is False and len(methods["request_reasoned_dissent"]["params"]) == 1
    assert len(methods) == 57


def test_reading_an_unknown_appeal_reverts(charter):
    for call in (charter.get_appeal(args=[1]), charter.get_appeal_record(args=[1]), charter.get_reasoned_dissent(args=[1])):
        with pytest.raises(Exception):
            call.call()


def test_an_appeal_of_an_unknown_review_is_refused(charter):
    receipt = charter.request_appeal(args=[99, "CHARTER_MISINTERPRETATION", "The ruling was wrong."]).transact()
    assert not tx_execution_succeeded(receipt)


@needs_real_genvm
def test_live_an_adverse_review_can_be_appealed_and_the_original_is_preserved(charter):
    assert tx_execution_succeeded(charter.request_constitutional_review(args=[1]).transact())
    original = charter.get_constitutional_review(args=[1]).call()
    assert tx_execution_succeeded(charter.request_appeal(args=[1, "CHARTER_MISINTERPRETATION", "The budget rule does not apply as read."]).transact())
    assert charter.get_constitutional_review(args=[1]).call() == original
    decision = charter.get_appellate_decision(args=[1]).call()
    assert decision["decision_kind"] in ("AFFIRMED", "MODIFIED", "REVERSED")
    assert charter.get_effective_ruling(args=[1]).call()["effective_verdict"] == decision["verdict"]
