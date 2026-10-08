"""Proposal creation, identity, charter-version binding and the absence of status control."""

import pytest

from conftest import hex_of

T0 = "2026-01-01T00:00:00Z"
T1 = "2026-04-05T12:00:00Z"

PROPOSAL = ("Fund Atlas Protocol", "Support an open-source developer tool.", "Grant 30,000 USDC to Atlas Protocol")



def test_any_wallet_can_submit_and_proposer_is_recorded(charter, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    charter.submit_proposal(*PROPOSAL)
    p = charter.get_proposal(1)
    assert p["proposer"].lower() == hex_of(direct_alice)
    assert (p["title"], p["description"], p["requested_action"]) == PROPOSAL
    assert p["status"] == "SUBMITTED"


def test_proposer_is_caller_not_owner(charter, direct_vm, direct_alice, direct_owner):
    charter.submit_proposal(*PROPOSAL)
    direct_vm.sender = direct_alice
    charter.submit_proposal(*PROPOSAL)
    assert charter.get_proposal(1)["proposer"].lower() == hex_of(direct_owner)
    assert charter.get_proposal(2)["proposer"].lower() == hex_of(direct_alice)


def test_proposal_ids_increment_from_one(charter):
    assert charter.get_proposal_count() == 0
    for expected in (1, 2, 3):
        charter.submit_proposal(*PROPOSAL)
        assert charter.get_proposal_count() == expected
        assert charter.get_proposal(expected)["proposal_id"] == expected
    assert charter.get_dao_metadata()["proposal_count"] == 3


def test_proposal_binds_to_current_charter_version(seeded, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    seeded.submit_proposal(*PROPOSAL)  # charter_version == 3
    assert seeded.get_proposal(1)["charter_version_at_submission"] == 3


def test_old_proposals_keep_their_original_charter_version(charter, direct_vm, direct_alice, direct_owner):
    charter.submit_proposal(*PROPOSAL)  # version 1
    charter.add_charter_section("1", "Mission", "body")  # version 2
    charter.submit_proposal(*PROPOSAL)  # version 2
    charter.update_charter_section("1", "Mission", "changed")  # version 3
    assert charter.get_proposal(1)["charter_version_at_submission"] == 1
    assert charter.get_proposal(2)["charter_version_at_submission"] == 2
    assert charter.get_charter_version() == 3


def test_proposal_timestamp_is_transaction_time(charter, direct_vm):
    direct_vm.warp(T0)
    charter.submit_proposal(*PROPOSAL)
    direct_vm.warp(T1)
    charter.submit_proposal(*PROPOSAL)
    assert charter.get_proposal(1)["created_at"].startswith("2026-01-01T00:00:00")
    assert charter.get_proposal(2)["created_at"].startswith("2026-04-05T12:00:00")


def test_proposal_does_not_modify_charter(seeded):
    before = seeded.get_dao_metadata()
    seeded.submit_proposal(*PROPOSAL)
    after = seeded.get_dao_metadata()
    assert after["charter_version"] == before["charter_version"]
    assert after["updated_at"] == before["updated_at"]


@pytest.mark.parametrize(
    "title,desc,action,code",
    [
        ("", "d", "a", "PROPOSAL_TITLE_EMPTY"),
        ("   ", "d", "a", "PROPOSAL_TITLE_EMPTY"),
        ("t", "", "a", "PROPOSAL_DESCRIPTION_EMPTY"),
        ("t", "\n\t", "a", "PROPOSAL_DESCRIPTION_EMPTY"),
        ("t", "d", "", "PROPOSAL_ACTION_EMPTY"),
        ("t" * 201, "d", "a", "PROPOSAL_TITLE_TOO_LONG"),
        ("t", "d" * 10001, "a", "PROPOSAL_DESCRIPTION_TOO_LONG"),
        ("t", "d", "a" * 2001, "PROPOSAL_ACTION_TOO_LONG"),
    ],
)
def test_invalid_proposals_rejected_without_consuming_an_id(charter, direct_vm, title, desc, action, code):
    with direct_vm.expect_revert("EXPECTED:" + code):
        charter.submit_proposal(title, desc, action)
    assert charter.get_proposal_count() == 0
    charter.submit_proposal(*PROPOSAL)
    assert charter.get_proposal(1)["proposal_id"] == 1  # no gap after the failed attempt


def test_unknown_proposal_rejected(charter, direct_vm):
    with direct_vm.expect_revert("EXPECTED:PROPOSAL_NOT_FOUND"):
        charter.get_proposal(1)
    charter.submit_proposal(*PROPOSAL)
    with direct_vm.expect_revert("EXPECTED:PROPOSAL_NOT_FOUND"):
        charter.get_proposal(0)
    with direct_vm.expect_revert("EXPECTED:PROPOSAL_NOT_FOUND"):
        charter.get_proposal(2)


def test_no_caller_controlled_status_transitions_exist(charter):
    # Stage 1 must not expose anything that moves a proposal beyond SUBMITTED.
    for name in (
        "approve_proposal", "reject_proposal", "set_proposal_status", "update_proposal_status",
        "adjudicate_proposal", "request_review", "cancel_proposal", "update_proposal", "delete_proposal",
    ):
        assert not hasattr(charter, name), name


def test_proposals_are_immutable_after_submission(charter, direct_vm, direct_alice):
    charter.submit_proposal(*PROPOSAL)
    snapshot = charter.get_proposal(1)
    direct_vm.sender = direct_alice
    charter.submit_proposal("Another", "Another description", "Another action")
    assert charter.get_proposal(1) == snapshot


def test_proposal_pagination(charter):
    for i in range(5):
        charter.submit_proposal(f"P{i}", "d", "a")
    page = charter.get_proposals_page(0, 2)
    assert [p["proposal_id"] for p in page] == [1, 2]
    assert [p["proposal_id"] for p in charter.get_proposals_page(4, 10)] == [5]
    assert charter.get_proposals_page(9, 10) == []


def test_proposal_page_limit_enforced(charter, direct_vm):
    with direct_vm.expect_revert("EXPECTED:PAGE_LIMIT_INVALID"):
        charter.get_proposals_page(0, 0)
