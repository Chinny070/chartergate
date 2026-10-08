"""Charter ownership, section CRUD, versioning, timestamps and validation."""

import pytest

from conftest import MISSION, TRANSPARENCY, hex_of

T0 = "2026-01-01T00:00:00Z"
T1 = "2026-02-01T09:30:00Z"
T2 = "2026-03-01T18:45:00Z"



# ---- initialisation ---------------------------------------------------------


def test_owner_and_metadata_set_on_deploy(charter, direct_owner):
    meta = charter.get_dao_metadata()
    assert meta["owner"].lower() == hex_of(direct_owner)
    assert meta["dao_name"] == "Atlas DAO"
    assert meta["charter_version"] == 1
    assert meta["section_count"] == 0
    assert meta["proposal_count"] == 0
    assert charter.get_charter_version() == 1


def test_init_timestamp_is_transaction_time(direct_vm, direct_deploy, direct_owner):
    direct_vm.sender = direct_owner
    direct_vm.warp(T0)
    c = direct_deploy("contracts/charter_gate.py", "Atlas DAO", "desc")
    meta = c.get_dao_metadata()
    assert meta["created_at"] == meta["updated_at"]
    assert meta["created_at"].startswith("2026-01-01T00:00:00")


@pytest.mark.parametrize(
    "name,desc,code",
    [("", "d", "DAO_NAME_EMPTY"), ("   ", "d", "DAO_NAME_EMPTY"), ("n", "", "DAO_DESCRIPTION_EMPTY"),
     ("x" * 121, "d", "DAO_NAME_TOO_LONG")],
)
def test_deploy_rejects_invalid_metadata(direct_vm, direct_deploy, direct_owner, name, desc, code):
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("EXPECTED:" + code):
        direct_deploy("contracts/charter_gate.py", name, desc)


# ---- owner can / stranger cannot -------------------------------------------


def test_owner_can_add_section(charter):
    charter.add_charter_section(*MISSION)
    s = charter.get_charter_section("1")
    assert (s["section_id"], s["title"], s["active"]) == ("1", "Mission", True)
    assert s["body"] == MISSION[2]
    assert charter.get_charter_section_count() == 1


def test_stranger_cannot_add_section(charter, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("EXPECTED:NOT_OWNER"):
        charter.add_charter_section(*MISSION)
    assert charter.get_charter_section_count() == 0
    assert charter.get_charter_version() == 1


def test_owner_can_update_section(seeded):
    seeded.update_charter_section("1", "Mission v2", "New body.")
    s = seeded.get_charter_section("1")
    assert (s["title"], s["body"]) == ("Mission v2", "New body.")


def test_stranger_cannot_update_section(seeded, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("EXPECTED:NOT_OWNER"):
        seeded.update_charter_section("1", "Hacked", "Hacked")
    assert seeded.get_charter_section("1")["title"] == "Mission"


def test_owner_can_deactivate_section(seeded):
    seeded.deactivate_charter_section("2")
    assert seeded.get_charter_section("2")["active"] is False
    assert seeded.get_charter_section("1")["active"] is True


def test_stranger_cannot_deactivate_section(seeded, direct_vm, direct_alice):
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("EXPECTED:NOT_OWNER"):
        seeded.deactivate_charter_section("1")
    assert seeded.get_charter_section("1")["active"] is True


def test_ownership_is_not_transferable_by_any_method(charter):
    # Stage 1 exposes no owner-changing method: the owner is fixed at deploy.
    for name in ("transfer_ownership", "set_owner", "renounce_ownership"):
        assert not hasattr(charter, name)


# ---- collisions and missing sections ---------------------------------------


def test_duplicate_section_id_rejected_and_original_preserved(seeded):
    with pytest.raises(Exception) as exc:
        seeded.add_charter_section("1", "Imposter", "Overwrite attempt")
    assert "SECTION_ID_EXISTS" in str(exc.value)
    assert seeded.get_charter_section("1")["title"] == "Mission"
    assert seeded.get_charter_section_count() == 2
    assert seeded.get_charter_version() == 3


def test_duplicate_id_is_case_sensitive_not_normalised(charter):
    charter.add_charter_section("mission", "Mission", "body")
    charter.add_charter_section("Mission", "Mission 2", "body")  # distinct id
    assert charter.get_charter_section_count() == 2


def test_update_nonexistent_section_rejected(charter, direct_vm):
    with direct_vm.expect_revert("EXPECTED:SECTION_NOT_FOUND"):
        charter.update_charter_section("nope", "t", "b")


def test_deactivate_nonexistent_section_rejected(charter, direct_vm):
    with direct_vm.expect_revert("EXPECTED:SECTION_NOT_FOUND"):
        charter.deactivate_charter_section("nope")


def test_read_nonexistent_section_rejected(charter, direct_vm):
    with direct_vm.expect_revert("EXPECTED:SECTION_NOT_FOUND"):
        charter.get_charter_section("nope")


def test_cannot_update_or_redeactivate_inactive_section(seeded, direct_vm):
    seeded.deactivate_charter_section("1")
    with direct_vm.expect_revert("EXPECTED:SECTION_INACTIVE"):
        seeded.update_charter_section("1", "t", "b")
    with direct_vm.expect_revert("EXPECTED:SECTION_ALREADY_INACTIVE"):
        seeded.deactivate_charter_section("1")


# ---- field validation -------------------------------------------------------


@pytest.mark.parametrize(
    "section_id,title,body,code",
    [
        ("", "t", "b", "SECTION_ID_EMPTY"),
        ("a b", "t", "b", "SECTION_ID_INVALID_CHARS"),
        ("a/b", "t", "b", "SECTION_ID_INVALID_CHARS"),
        ("é", "t", "b", "SECTION_ID_INVALID_CHARS"),
        (" 1", "t", "b", "SECTION_ID_INVALID_CHARS"),
        ("x" * 65, "t", "b", "SECTION_ID_TOO_LONG"),
        ("1", "", "b", "SECTION_TITLE_EMPTY"),
        ("1", "   \n", "b", "SECTION_TITLE_EMPTY"),
        ("1", "t" * 201, "b", "SECTION_TITLE_TOO_LONG"),
        ("1", "t", "", "SECTION_BODY_EMPTY"),
        ("1", "t", "  ", "SECTION_BODY_EMPTY"),
        ("1", "t", "b" * 10001, "SECTION_BODY_TOO_LONG"),
    ],
)
def test_invalid_section_fields_rejected_without_side_effects(charter, direct_vm, section_id, title, body, code):
    with direct_vm.expect_revert("EXPECTED:" + code):
        charter.add_charter_section(section_id, title, body)
    assert charter.get_charter_section_count() == 0
    assert charter.get_charter_version() == 1


def test_invalid_update_rejected_without_side_effects(seeded, direct_vm):
    with direct_vm.expect_revert("EXPECTED:SECTION_BODY_EMPTY"):
        seeded.update_charter_section("1", "Valid title", "   ")
    s = seeded.get_charter_section("1")
    assert (s["title"], s["body"]) == (MISSION[1], MISSION[2])
    assert seeded.get_charter_version() == 3


def test_section_text_is_trimmed_and_boundary_lengths_accepted(charter):
    charter.add_charter_section("x" * 64, "  " + "t" * 200 + "  ", "b" * 10000)
    s = charter.get_charter_section("x" * 64)
    assert len(s["title"]) == 200 and len(s["body"]) == 10000


# ---- versioning -------------------------------------------------------------


def test_charter_version_increments_on_each_mutation(charter):
    assert charter.get_charter_version() == 1
    charter.add_charter_section(*MISSION)
    assert charter.get_charter_version() == 2
    charter.update_charter_section("1", "Mission", "Updated body")
    assert charter.get_charter_version() == 3
    charter.deactivate_charter_section("1")
    assert charter.get_charter_version() == 4
    assert charter.get_dao_metadata()["charter_version"] == 4


def test_failed_mutations_never_increment_version(charter, direct_vm, direct_alice):
    charter.add_charter_section(*MISSION)  # version 2
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("EXPECTED:NOT_OWNER"):
        charter.update_charter_section("1", "x", "y")
    assert charter.get_charter_version() == 2


# ---- timestamps -------------------------------------------------------------


def test_section_and_charter_timestamps_follow_transaction_time(charter, direct_vm):
    direct_vm.warp(T0)
    charter.add_charter_section(*MISSION)
    created = charter.get_charter_section("1")
    assert created["created_at"].startswith("2026-01-01T00:00:00")
    assert created["updated_at"] == created["created_at"]

    direct_vm.warp(T1)
    charter.update_charter_section("1", "Mission", "Revised")
    updated = charter.get_charter_section("1")
    assert updated["created_at"] == created["created_at"]  # creation time is immutable
    assert updated["updated_at"].startswith("2026-02-01T09:30:00")
    assert charter.get_dao_metadata()["updated_at"] == updated["updated_at"]

    direct_vm.warp(T2)
    charter.deactivate_charter_section("1")
    assert charter.get_charter_section("1")["updated_at"].startswith("2026-03-01T18:45:00")
    assert charter.get_dao_metadata()["created_at"] != charter.get_dao_metadata()["updated_at"]


def test_failed_mutation_does_not_touch_timestamps(charter, direct_vm):
    direct_vm.warp(T0)
    charter.add_charter_section(*MISSION)
    before = charter.get_charter_section("1")["updated_at"]
    direct_vm.warp(T2)
    with direct_vm.expect_revert("EXPECTED:SECTION_BODY_EMPTY"):
        charter.update_charter_section("1", "t", " ")
    assert charter.get_charter_section("1")["updated_at"] == before


# ---- reads and pagination ---------------------------------------------------


def test_section_pagination_preserves_insertion_order(seeded):
    assert seeded.get_charter_section_ids_page(0, 10) == ["1", "2"]
    assert seeded.get_charter_section_ids_page(1, 10) == ["2"]
    assert seeded.get_charter_section_ids_page(5, 10) == []
    page = seeded.get_charter_sections_page(0, 1)
    assert [s["section_id"] for s in page] == ["1"]


def test_deactivated_sections_remain_listed(seeded):
    seeded.deactivate_charter_section("1")
    page = seeded.get_charter_sections_page(0, 10)
    assert [(s["section_id"], s["active"]) for s in page] == [("1", False), ("2", True)]


@pytest.mark.parametrize("limit,code", [(0, "PAGE_LIMIT_INVALID"), (51, "PAGE_LIMIT_TOO_LARGE")])
def test_page_limits_enforced(charter, direct_vm, limit, code):
    with direct_vm.expect_revert("EXPECTED:" + code):
        charter.get_charter_sections_page(0, limit)


def test_transparency_fixture_constant_is_used(seeded):
    assert seeded.get_charter_section(TRANSPARENCY[0])["title"] == "Transparency"
