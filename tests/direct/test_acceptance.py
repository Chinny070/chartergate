"""The Stage 1 acceptance scenario, step for step."""

from conftest import MISSION, TRANSPARENCY, hex_of

T0 = "2026-05-01T08:00:00Z"
T1 = "2026-05-02T10:15:00Z"



def test_stage1_acceptance_scenario(charter, direct_vm, direct_owner, direct_alice, direct_bob):
    # 1. Contract owner exists.
    assert charter.get_dao_metadata()["owner"].lower() == hex_of(direct_owner)
    assert charter.get_charter_version() == 1

    # 2-3. Owner creates the Mission and Transparency sections.
    charter.add_charter_section(*MISSION)
    charter.add_charter_section(*TRANSPARENCY)

    # 4. Charter version changes accordingly.
    assert charter.get_charter_version() == 3
    assert [s["section_id"] for s in charter.get_charter_sections_page(0, 10)] == ["1", "2"]

    # 5-7. A wallet submits "Fund Atlas Protocol"; it is stored as SUBMITTED with
    # the proposer, creation timestamp and current charter version.
    direct_vm.sender = direct_alice
    direct_vm.warp(T0)
    charter.submit_proposal(
        "Fund Atlas Protocol",
        "Support an open-source developer tool that makes contract testing faster.",
        "Grant funding to Atlas Protocol",
    )
    proposal = charter.get_proposal(1)
    assert proposal["status"] == "SUBMITTED"
    assert proposal["proposer"].lower() == hex_of(direct_alice)
    assert proposal["created_at"].startswith("2026-05-01T08:00:00")
    assert proposal["charter_version_at_submission"] == 3

    charter_before = charter.get_charter_sections_page(0, 10)
    meta_before = charter.get_dao_metadata()

    # 8-9. A stranger attempts to rewrite section 1; the transaction fails.
    direct_vm.sender = direct_bob
    direct_vm.warp(T1)
    with direct_vm.expect_revert("EXPECTED:NOT_OWNER"):
        charter.update_charter_section("1", "Mission", "Spend the treasury on whatever we like.")

    # 10. Existing charter and proposal state is unchanged.
    assert charter.get_charter_sections_page(0, 10) == charter_before
    assert charter.get_dao_metadata() == meta_before
    assert charter.get_proposal(1) == proposal
    assert charter.get_charter_version() == 3
