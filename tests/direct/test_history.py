"""Immutable charter history: any past charter_version can be reconstructed exactly."""

import pytest

PROPOSAL = ("Fund Atlas Protocol", "Support an open-source developer tool.", "Grant funding")

T1 = "2026-01-01T00:00:00Z"
T2 = "2026-02-01T00:00:00Z"
T3 = "2026-03-01T00:00:00Z"
T4 = "2026-04-01T00:00:00Z"


def body_at(charter, section_id, version):
    return charter.get_charter_section_at_version(section_id, version)["body"]


# ---- the required scenario --------------------------------------------------


def test_proposals_resolve_to_the_charter_text_in_force_when_submitted(charter):
    assert charter.get_charter_version() == 1
    charter.add_charter_section("1", "Mission", "OLD mission text")  # -> v2
    charter.submit_proposal(*PROPOSAL)  # proposal 1, bound to v2

    charter.update_charter_section("1", "Mission", "NEW mission text")  # -> v3
    charter.submit_proposal("Second", "Second proposal", "Another action")  # proposal 2, bound to v3

    a = charter.get_proposal(1)
    b = charter.get_proposal(2)
    assert a["charter_version_at_submission"] == 2
    assert b["charter_version_at_submission"] == 3

    # historical lookup for A returns the OLD text, for B the NEW text, current lookup the NEW text
    assert body_at(charter, "1", a["charter_version_at_submission"]) == "OLD mission text"
    assert body_at(charter, "1", b["charter_version_at_submission"]) == "NEW mission text"
    assert charter.get_charter_section("1")["body"] == "NEW mission text"


def test_old_proposal_stays_bound_after_charter_reaches_much_later_version(charter):
    charter.add_charter_section("1", "Mission", "v2 text")  # v2
    charter.add_charter_section("2", "Other", "x")  # v3
    charter.add_charter_section("3", "Third", "y")  # v4
    charter.submit_proposal(*PROPOSAL)  # bound to v4
    for i in range(5):  # v5..v9
        charter.update_charter_section("1", "Mission", f"revision {i}")
    assert charter.get_charter_version() == 9
    assert charter.get_proposal(1)["charter_version_at_submission"] == 4
    assert body_at(charter, "1", 4) == "v2 text"
    assert charter.get_charter_section_count_at_version(4) == 3
    assert charter.get_charter_section("1")["body"] == "revision 4"


# ---- history shapes ---------------------------------------------------------


def test_add_then_update_preserves_both_versions(charter):
    charter.add_charter_section("1", "Mission", "first")  # v2
    charter.update_charter_section("1", "Mission", "second")  # v3
    assert body_at(charter, "1", 2) == "first"
    assert body_at(charter, "1", 3) == "second"


def test_add_then_deactivate_preserves_the_active_historical_version(charter):
    charter.add_charter_section("1", "Mission", "text")  # v2
    charter.deactivate_charter_section("1")  # v3
    before = charter.get_charter_section_at_version("1", 2)
    after = charter.get_charter_section_at_version("1", 3)
    assert before["active"] is True
    assert after["active"] is False
    assert (before["title"], before["body"]) == (after["title"], after["body"])
    assert charter.get_charter_section("1")["active"] is False


def test_several_updates_to_one_section_are_each_reconstructable(charter):
    charter.add_charter_section("1", "Mission", "r0")  # v2
    for i in range(1, 6):  # v3..v7
        charter.update_charter_section("1", "Mission", f"r{i}")
    for version, expected in zip(range(2, 8), ["r0", "r1", "r2", "r3", "r4", "r5"]):
        assert body_at(charter, "1", version) == expected


def test_unrelated_section_changes_do_not_corrupt_another_sections_history(charter):
    charter.add_charter_section("1", "One", "one-v1")  # v2
    charter.add_charter_section("2", "Two", "two-v1")  # v3
    charter.update_charter_section("2", "Two", "two-v2")  # v4
    charter.update_charter_section("1", "One", "one-v2")  # v5
    charter.deactivate_charter_section("2")  # v6

    assert body_at(charter, "1", 2) == "one-v1"
    assert body_at(charter, "1", 4) == "one-v1"  # section 2's changes did not touch section 1
    assert body_at(charter, "1", 5) == "one-v2"
    assert body_at(charter, "1", 6) == "one-v2"
    assert body_at(charter, "2", 3) == "two-v1"
    assert body_at(charter, "2", 4) == "two-v2"
    assert body_at(charter, "2", 5) == "two-v2"
    assert charter.get_charter_section_at_version("2", 6)["active"] is False
    assert charter.get_charter_section_at_version("1", 6)["active"] is True


def test_effective_revision_reports_the_version_that_made_it_effective(charter):
    charter.add_charter_section("1", "Mission", "a")  # v2
    charter.add_charter_section("2", "Other", "b")  # v3
    charter.add_charter_section("3", "Third", "c")  # v4
    # section 1 has not changed since v2, so at v4 it is still the v2 revision
    assert charter.get_charter_section_at_version("1", 4)["charter_version"] == 2


# ---- the revision log -------------------------------------------------------


def test_every_mutation_produces_one_revision_for_its_resulting_version(charter, direct_vm):
    direct_vm.warp(T1)
    charter.add_charter_section("1", "Mission", "a")  # v2
    direct_vm.warp(T2)
    charter.update_charter_section("1", "Mission", "b")  # v3
    direct_vm.warp(T3)
    charter.deactivate_charter_section("1")  # v4

    revs = [charter.get_charter_revision(v) for v in (2, 3, 4)]
    assert [r["charter_version"] for r in revs] == [2, 3, 4]
    assert [r["body"] for r in revs] == ["a", "b", "b"]
    assert [r["active"] for r in revs] == [True, True, False]
    assert revs[0]["changed_at"].startswith("2026-01-01")
    assert revs[1]["changed_at"].startswith("2026-02-01")
    assert revs[2]["changed_at"].startswith("2026-03-01")
    assert {r["section_id"] for r in revs} == {"1"}


def test_version_one_has_no_revision(charter, direct_vm):
    with direct_vm.expect_revert("EXPECTED:CHARTER_VERSION_HAS_NO_REVISION"):
        charter.get_charter_revision(1)


def test_revision_changed_at_matches_section_timestamps(charter, direct_vm):
    direct_vm.warp(T1)
    charter.add_charter_section("1", "Mission", "a")
    direct_vm.warp(T2)
    charter.update_charter_section("1", "Mission", "b")
    current = charter.get_charter_section("1")
    assert charter.get_charter_revision(2)["changed_at"] == current["created_at"]
    assert charter.get_charter_revision(3)["changed_at"] == current["updated_at"]


# ---- failure modes ----------------------------------------------------------


def test_failed_mutations_create_no_revision_and_no_version(seeded, direct_vm, direct_alice):
    assert seeded.get_charter_version() == 3
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("EXPECTED:NOT_OWNER"):
        seeded.update_charter_section("1", "Hacked", "Hacked")
    with direct_vm.expect_revert("EXPECTED:NOT_OWNER"):
        seeded.add_charter_section("9", "t", "b")
    with direct_vm.expect_revert("EXPECTED:NOT_OWNER"):
        seeded.deactivate_charter_section("1")

    assert seeded.get_charter_version() == 3
    with direct_vm.expect_revert("EXPECTED:CHARTER_VERSION_NOT_FOUND"):
        seeded.get_charter_revision(4)  # no revision was created for a version that never happened


def test_owner_validation_failures_create_no_revision(seeded, direct_vm):
    for call, code in (
        (lambda: seeded.add_charter_section("1", "dup", "dup"), "SECTION_ID_EXISTS"),
        (lambda: seeded.update_charter_section("1", "t", " "), "SECTION_BODY_EMPTY"),
        (lambda: seeded.update_charter_section("zz", "t", "b"), "SECTION_NOT_FOUND"),
        (lambda: seeded.deactivate_charter_section("zz"), "SECTION_NOT_FOUND"),
    ):
        with direct_vm.expect_revert("EXPECTED:" + code):
            call()
    assert seeded.get_charter_version() == 3
    assert body_at(seeded, "1", 3) == seeded.get_charter_section("1")["body"]


@pytest.mark.parametrize("version", [0, 99])
def test_unknown_historical_versions_fail_cleanly(seeded, direct_vm, version):
    with direct_vm.expect_revert("EXPECTED:CHARTER_VERSION_NOT_FOUND"):
        seeded.get_charter_section_at_version("1", version)
    with direct_vm.expect_revert("EXPECTED:CHARTER_VERSION_NOT_FOUND"):
        seeded.get_charter_section_count_at_version(version)
    with direct_vm.expect_revert("EXPECTED:CHARTER_VERSION_NOT_FOUND"):
        seeded.get_charter_sections_at_version_page(version, 0, 10)
    with direct_vm.expect_revert("EXPECTED:CHARTER_VERSION_NOT_FOUND"):
        seeded.get_charter_revision(version)


def test_future_version_is_not_queryable_until_it_exists(charter, direct_vm):
    charter.add_charter_section("1", "Mission", "a")  # now at v2
    with direct_vm.expect_revert("EXPECTED:CHARTER_VERSION_NOT_FOUND"):
        charter.get_charter_section_at_version("1", 3)
    charter.update_charter_section("1", "Mission", "b")  # v3 now exists
    assert body_at(charter, "1", 3) == "b"


def test_section_did_not_exist_yet_at_an_earlier_version(charter, direct_vm):
    charter.add_charter_section("1", "One", "a")  # v2
    charter.add_charter_section("2", "Two", "b")  # v3
    with direct_vm.expect_revert("EXPECTED:SECTION_NOT_FOUND_AT_VERSION"):
        charter.get_charter_section_at_version("2", 2)
    with direct_vm.expect_revert("EXPECTED:SECTION_NOT_FOUND_AT_VERSION"):
        charter.get_charter_section_at_version("1", 1)
    with direct_vm.expect_revert("EXPECTED:SECTION_NOT_FOUND_AT_VERSION"):
        charter.get_charter_section_at_version("never-existed", 3)


# ---- effective charter at a version (paginated) -----------------------------


def test_charter_at_version_lists_only_sections_that_existed_then(charter):
    assert charter.get_charter_section_count_at_version(1) == 0
    assert charter.get_charter_sections_at_version_page(1, 0, 10) == []

    charter.add_charter_section("1", "One", "one-v1")  # v2
    charter.add_charter_section("2", "Two", "two-v1")  # v3
    charter.update_charter_section("1", "One", "one-v2")  # v4
    charter.add_charter_section("3", "Three", "three-v1")  # v5

    def snapshot(version):
        page = charter.get_charter_sections_at_version_page(version, 0, 10)
        return [(r["section_id"], r["body"]) for r in page]

    assert snapshot(2) == [("1", "one-v1")]
    assert snapshot(3) == [("1", "one-v1"), ("2", "two-v1")]
    assert snapshot(4) == [("1", "one-v2"), ("2", "two-v1")]
    assert snapshot(5) == [("1", "one-v2"), ("2", "two-v1"), ("3", "three-v1")]
    assert [charter.get_charter_section_count_at_version(v) for v in (1, 2, 3, 4, 5)] == [0, 1, 2, 2, 3]


def test_charter_at_version_is_paginated_and_bounded(charter, direct_vm):
    for i in range(1, 6):
        charter.add_charter_section(str(i), f"S{i}", f"b{i}")  # v2..v6
    page = charter.get_charter_sections_at_version_page(6, 1, 2)
    assert [r["section_id"] for r in page] == ["2", "3"]
    assert charter.get_charter_sections_at_version_page(6, 9, 5) == []
    with direct_vm.expect_revert("EXPECTED:PAGE_LIMIT_TOO_LARGE"):
        charter.get_charter_sections_at_version_page(6, 0, 51)
    with direct_vm.expect_revert("EXPECTED:PAGE_LIMIT_INVALID"):
        charter.get_charter_sections_at_version_page(6, 0, 0)


def test_deactivated_sections_stay_in_the_historical_charter(charter):
    charter.add_charter_section("1", "One", "a")  # v2
    charter.deactivate_charter_section("1")  # v3
    at2 = charter.get_charter_sections_at_version_page(2, 0, 10)
    at3 = charter.get_charter_sections_at_version_page(3, 0, 10)
    assert [r["active"] for r in at2] == [True]
    assert [r["active"] for r in at3] == [False]


# ---- immutability -----------------------------------------------------------


def test_no_public_method_can_rewrite_history(charter):
    for name in (
        "delete_charter_section", "revert_charter", "rollback_charter", "set_charter_version",
        "update_charter_revision", "delete_charter_revision", "rewrite_history", "restore_charter_section",
        "reactivate_charter_section", "set_proposal_charter_version", "upgrade_proposal",
    ):
        assert not hasattr(charter, name), name


def test_history_is_unchanged_by_later_activity(charter, direct_vm, direct_alice):
    charter.add_charter_section("1", "Mission", "original")  # v2
    snapshot = charter.get_charter_revision(2)
    charter.update_charter_section("1", "Mission", "changed")  # v3
    charter.deactivate_charter_section("1")  # v4
    direct_vm.sender = direct_alice
    charter.submit_proposal(*PROPOSAL)
    assert charter.get_charter_revision(2) == snapshot
    assert body_at(charter, "1", 2) == "original"


def test_current_lookup_still_works_after_history_changes(seeded):
    seeded.update_charter_section("1", "Mission", "latest")
    current = seeded.get_charter_section("1")
    assert current["body"] == "latest"
    assert current["active"] is True
    assert seeded.get_charter_section_at_version("1", seeded.get_charter_version())["body"] == "latest"
