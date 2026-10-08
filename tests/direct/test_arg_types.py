"""Malformed-argument hardening.

GenVM does not enforce Python annotations at the contract boundary, so a caller can send an int where a
str is expected (the live StudioNet CLI did exactly that). Every public method must reject wrong types with
a deterministic ``EXPECTED:INVALID_TYPE:<arg>`` error, never a raw TypeError/AttributeError/ValueError/
IndexError, and must leave state untouched.
"""

import pytest

from conftest import CONTRACT_PATH

BAD_STR = [1, True, False, None, 3, ["a"], {"a": 1}, b"bytes"]
BAD_INT = ["1", True, False, None, ["1"], {"a": 1}, b"1"]

PROPOSAL = ("Fund Atlas Protocol", "Support an open-source developer tool.", "Grant funding")


def snapshot(c):
    """Everything observable: metadata, current charter, every revision, every proposal."""
    meta = c.get_dao_metadata()
    version = c.get_charter_version()
    return {
        "meta": meta,
        "sections": c.get_charter_sections_page(0, 50),
        "revisions": [c.get_charter_revision(v) for v in range(2, version + 1)],
        "proposals": c.get_proposals_page(0, 50),
    }


@pytest.fixture
def populated(seeded, direct_vm):
    """Owner is the sender; two sections, an update and a proposal already exist."""
    seeded.update_charter_section("1", "Mission", "Updated mission text")
    seeded.submit_proposal(*PROPOSAL)
    return seeded


def ids(values):
    return [repr(v) for v in values]


# ---- writes: every string parameter ----------------------------------------

WRITE_STR_CASES = [
    ("add_charter_section", ("new", "Title", "Body"), 0, "section_id"),
    ("add_charter_section", ("new", "Title", "Body"), 1, "title"),
    ("add_charter_section", ("new", "Title", "Body"), 2, "body"),
    ("update_charter_section", ("1", "Title", "Body"), 0, "section_id"),
    ("update_charter_section", ("1", "Title", "Body"), 1, "title"),
    ("update_charter_section", ("1", "Title", "Body"), 2, "body"),
    ("deactivate_charter_section", ("1",), 0, "section_id"),
    ("submit_proposal", PROPOSAL, 0, "title"),
    ("submit_proposal", PROPOSAL, 1, "description"),
    ("submit_proposal", PROPOSAL, 2, "requested_action"),
]


@pytest.mark.parametrize("bad", BAD_STR, ids=ids(BAD_STR))
@pytest.mark.parametrize("method,good,position,name", WRITE_STR_CASES, ids=[f"{m}.{n}" for m, _, _, n in WRITE_STR_CASES])
def test_write_rejects_wrong_typed_string_args_and_changes_nothing(populated, direct_vm, method, good, position, name, bad):
    before = snapshot(populated)
    args = list(good)
    args[position] = bad
    with direct_vm.expect_revert(f"EXPECTED:INVALID_TYPE:{name}"):
        getattr(populated, method)(*args)
    assert snapshot(populated) == before


def test_exact_stage_1_1_live_failure_is_now_a_clean_error(populated, direct_vm):
    """The StudioNet CLI sent section_id as the int 1; that used to raise TypeError at len(int)."""
    before = snapshot(populated)
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:section_id"):
        populated.add_charter_section(1, "Mission", "Fund open-source infrastructure.")
    assert snapshot(populated) == before


# ---- failed writes consume nothing ------------------------------------------


def test_bad_proposal_does_not_consume_an_id(populated, direct_vm):
    count = populated.get_proposal_count()
    for bad in (1, True, None, ["x"]):
        with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:title"):
            populated.submit_proposal(bad, "d", "a")
    assert populated.get_proposal_count() == count
    populated.submit_proposal(*PROPOSAL)
    assert populated.get_proposal(count + 1)["proposal_id"] == count + 1  # no gap


def test_bad_charter_mutations_create_no_revision_and_no_version(populated, direct_vm):
    version = populated.get_charter_version()
    for call in (
        lambda: populated.add_charter_section(1, "t", "b"),
        lambda: populated.update_charter_section("1", 5, "b"),
        lambda: populated.deactivate_charter_section(True),
    ):
        with direct_vm.expect_revert("EXPECTED:INVALID_TYPE"):
            call()
    assert populated.get_charter_version() == version
    with direct_vm.expect_revert("EXPECTED:CHARTER_VERSION_NOT_FOUND"):
        populated.get_charter_revision(version + 1)  # no revision was created


def test_bad_types_do_not_alter_timestamps(populated, direct_vm):
    direct_vm.warp("2030-01-01T00:00:00Z")
    before = populated.get_dao_metadata()["updated_at"]
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:body"):
        populated.update_charter_section("1", "Mission", 123)
    assert populated.get_dao_metadata()["updated_at"] == before
    assert populated.get_charter_section("1")["updated_at"] != "2030-01-01T00:00:00Z"


# ---- constructor ------------------------------------------------------------


@pytest.mark.parametrize("bad", BAD_STR, ids=ids(BAD_STR))
def test_constructor_rejects_wrong_typed_dao_name(direct_vm, direct_deploy, direct_owner, bad):
    # One deploy per test: the direct harness cannot reload the contract module twice in one test.
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:dao_name"):
        direct_deploy(CONTRACT_PATH, bad, "A description")


@pytest.mark.parametrize("bad", BAD_STR, ids=ids(BAD_STR))
def test_constructor_rejects_wrong_typed_dao_description(direct_vm, direct_deploy, direct_owner, bad):
    direct_vm.sender = direct_owner
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:dao_description"):
        direct_deploy(CONTRACT_PATH, "A name", bad)


# ---- views: string parameters ----------------------------------------------


@pytest.mark.parametrize("bad", BAD_STR, ids=ids(BAD_STR))
def test_views_reject_wrong_typed_section_id(populated, direct_vm, bad):
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:section_id"):
        populated.get_charter_section(bad)
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:section_id"):
        populated.get_charter_section_at_version(bad, 2)


# ---- views: integer parameters ---------------------------------------------


INT_CALLS = [
    # (method, args with a "@" placeholder at the integer under test, argument name)
    ("get_charter_section_ids_page", ("@", 10), "offset"),
    ("get_charter_section_ids_page", (0, "@"), "limit"),
    ("get_charter_sections_page", ("@", 10), "offset"),
    ("get_charter_sections_page", (0, "@"), "limit"),
    ("get_proposals_page", ("@", 10), "offset"),
    ("get_proposals_page", (0, "@"), "limit"),
    ("get_charter_sections_at_version_page", ("@", 0, 10), "charter_version"),
    ("get_charter_sections_at_version_page", (2, "@", 10), "offset"),
    ("get_charter_sections_at_version_page", (2, 0, "@"), "limit"),
    ("get_charter_section_at_version", ("1", "@"), "charter_version"),
    ("get_charter_section_count_at_version", ("@",), "charter_version"),
    ("get_charter_revision", ("@",), "charter_version"),
    ("get_proposal", ("@",), "proposal_id"),
]


def _fill(args, value):
    return tuple(value if a == "@" else a for a in args)


@pytest.mark.parametrize("bad", BAD_INT, ids=ids(BAD_INT))
@pytest.mark.parametrize("method,args,name", INT_CALLS, ids=[f"{m}.{n}.{i}" for i, (m, _, n) in enumerate(INT_CALLS)])
def test_views_reject_wrong_typed_integer_args(populated, direct_vm, method, args, name, bad):
    with direct_vm.expect_revert(f"EXPECTED:INVALID_TYPE:{name}"):
        getattr(populated, method)(*_fill(args, bad))


@pytest.mark.parametrize("bad", [-1, -(2**64), 2**256], ids=["-1", "-2^64", "2^256"])
@pytest.mark.parametrize("method,args,name", INT_CALLS, ids=[f"{m}.{n}.{i}" for i, (m, _, n) in enumerate(INT_CALLS)])
def test_views_reject_out_of_range_integers(populated, direct_vm, method, args, name, bad):
    with direct_vm.expect_revert(f"EXPECTED:INTEGER_OUT_OF_RANGE:{name}"):
        getattr(populated, method)(*_fill(args, bad))


def test_negative_page_offset_no_longer_leaks_an_index_error(populated, direct_vm):
    """Before hardening, offset=-1 raised IndexError from DynArray indexing."""
    with direct_vm.expect_revert("EXPECTED:INTEGER_OUT_OF_RANGE:offset"):
        populated.get_charter_sections_page(-1, 5)


# ---- ordering and regressions ----------------------------------------------


def test_stranger_is_rejected_for_ownership_before_argument_types(populated, direct_vm, direct_alice):
    """Documented ordering: caller authorisation first, then argument validation."""
    direct_vm.sender = direct_alice
    with direct_vm.expect_revert("EXPECTED:NOT_OWNER"):
        populated.add_charter_section(1, 2, 3)


def test_valid_arguments_still_work_after_hardening(populated):
    populated.add_charter_section("fresh", "Fresh", "Fresh body")
    assert populated.get_charter_section("fresh")["title"] == "Fresh"
    populated.submit_proposal("Another", "Another description", "Another action")
    assert populated.get_proposal(2)["title"] == "Another"
    assert populated.get_charter_sections_page(0, 50)[0]["section_id"] == "1"


def test_bool_is_not_accepted_as_an_integer(populated, direct_vm):
    """True == 1 in Python, so without an explicit guard get_proposal(True) would return proposal 1."""
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:proposal_id"):
        populated.get_proposal(True)
    assert populated.get_proposal(1)["proposal_id"] == 1
