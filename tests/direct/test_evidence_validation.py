"""Evidence input hardening: URL screening, argument types, sizes, pagination. Web and LLM are mocked."""

import pytest

from evidence_support import (
    CLAIM_PLAIN,
    atlas,  # noqa: F401  (fixture)
    mock_answer,
    mock_page,
    page,
    snapshot,
    submit,
    web,  # noqa: F401  (fixture)
)


def unchanged(c, before):
    assert c.get_evidence_count() == 0
    assert snapshot(c) == before


# ---- URL screening -----------------------------------------------------------

REJECTED_URLS = [
    ("", "SOURCE_URL_EMPTY"),
    ("    ", "SOURCE_URL_EMPTY"),
    ("ftp://example.com/a", "SOURCE_URL_UNSUPPORTED_SCHEME"),
    ("file:///etc/passwd", "SOURCE_URL_UNSUPPORTED_SCHEME"),
    ("javascript:alert(1)", "SOURCE_URL_UNSUPPORTED_SCHEME"),
    ("data:text/html,hello", "SOURCE_URL_UNSUPPORTED_SCHEME"),
    ("//example.com/a", "SOURCE_URL_UNSUPPORTED_SCHEME"),
    ("example.com/a", "SOURCE_URL_UNSUPPORTED_SCHEME"),
    ("httpx://example.com", "SOURCE_URL_UNSUPPORTED_SCHEME"),
    ("https://", "SOURCE_URL_NO_HOST"),
    ("https:///path", "SOURCE_URL_NO_HOST"),
    ("https://user:pw@example.com/", "SOURCE_URL_HAS_CREDENTIALS"),
    ("https://example.com@evil.com/", "SOURCE_URL_HAS_CREDENTIALS"),
    ("https://[::1]/", "SOURCE_URL_IP_LITERAL"),
    ("http://localhost/", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("http://localhost:8080/x", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("http://LOCALHOST./", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("http://127.0.0.1/", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("http://10.0.0.5/admin", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("http://192.168.1.1/", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("http://169.254.169.254/latest/meta-data/", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("http://2130706433/", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("http://0x7f.0.0.1/", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("http://intranet/", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("https://printer.local/", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("https://db.internal/", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("https://app.localhost/", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("https://nas.lan/", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("https://example.com:0/", "SOURCE_URL_BAD_PORT"),
    ("https://example.com:65536/", "SOURCE_URL_BAD_PORT"),
    ("https://example.com:abc/", "SOURCE_URL_BAD_PORT"),
    ("https://example.com:/", "SOURCE_URL_BAD_PORT"),
    ("https://exa mple.com/", "SOURCE_URL_INVALID_CHARS"),
    ("https://example.com/a b", "SOURCE_URL_INVALID_CHARS"),
    ("https://example.com/\\evil", "SOURCE_URL_INVALID_CHARS"),
    ("https://exa\nmple.com/", "SOURCE_URL_INVALID_CHARS"),
    ("https://exa\tmple.com/", "SOURCE_URL_INVALID_CHARS"),
    ("https://ex\x00ample.com/", "SOURCE_URL_INVALID_CHARS"),
    ("https://exämple.com/", "SOURCE_URL_INVALID_CHARS"),
    ("https://a..example.com/", "SOURCE_URL_INVALID_HOST"),
    ("https://exa_mple.com/", "SOURCE_URL_INVALID_HOST"),
    ("https://example.c/", "SOURCE_URL_HOST_NOT_PUBLIC"),
    ("https://example.com/" + "a" * 481, "SOURCE_URL_TOO_LONG"),
]


@pytest.mark.parametrize("url,code", REJECTED_URLS, ids=[f"{i}" for i in range(len(REJECTED_URLS))])
def test_unsafe_or_invalid_urls_are_rejected_before_any_web_access(atlas, direct_vm, url, code):
    # No web or LLM mock is registered: reaching the network would raise MockNotFoundError instead.
    before = snapshot(atlas)
    with direct_vm.expect_revert("EXPECTED:" + code):
        submit(atlas, source_url=url)
    unchanged(atlas, before)


ACCEPTED_URLS = [
    "https://atlas.example.org/tokenomics",
    "http://atlas.example.org/x?y=1#frag",
    "https://sub.domain.example.co.uk:8443/path/to/page.html",
    "https://xn--bcher-kva.example/",
    "HTTPS://Atlas.Example.ORG/Path",
    "https://example.com",
    "  https://atlas.example.org/padded  ",
]


@pytest.mark.parametrize("url", ACCEPTED_URLS, ids=[f"{i}" for i in range(len(ACCEPTED_URLS))])
def test_ordinary_public_urls_are_accepted(atlas, direct_vm, url):
    mock_page(direct_vm, page(), pattern=r".*")
    mock_answer(direct_vm)
    submit(atlas, source_url=url)
    assert atlas.get_evidence(1)["source_url"] == url.strip()  # stored exactly as submitted, trimmed only


# ---- argument types ----------------------------------------------------------

BAD_STR = [1, True, False, None, ["x"], {"a": 1}, b"bytes"]
BAD_INT = ["1", True, False, None, ["1"], {"a": 1}, b"1"]


@pytest.mark.parametrize("bad", BAD_STR, ids=[repr(b) for b in BAD_STR])
@pytest.mark.parametrize("param", ["source_url", "source_kind", "claim", "related_section_id"])
def test_wrong_typed_string_arguments_are_rejected_cleanly(atlas, direct_vm, param, bad):
    before = snapshot(atlas)
    with direct_vm.expect_revert(f"EXPECTED:INVALID_TYPE:{param}"):
        submit(atlas, **{param: bad})
    unchanged(atlas, before)


@pytest.mark.parametrize("bad", BAD_INT, ids=[repr(b) for b in BAD_INT])
def test_wrong_typed_proposal_id_is_rejected_cleanly(atlas, direct_vm, bad):
    before = snapshot(atlas)
    with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:proposal_id"):
        submit(atlas, proposal_id=bad)
    unchanged(atlas, before)


def test_boolean_true_is_not_proposal_one(atlas, web):
    """True == 1 in Python: without an explicit guard this would silently attach evidence to proposal 1."""
    with web.expect_revert("EXPECTED:INVALID_TYPE:proposal_id"):
        submit(atlas, proposal_id=True)
    assert atlas.get_evidence_count() == 0


@pytest.mark.parametrize("bad", [-1, -(2**64), 2**256], ids=["-1", "-2^64", "2^256"])
def test_out_of_range_proposal_ids_are_rejected(atlas, direct_vm, bad):
    with direct_vm.expect_revert("EXPECTED:INTEGER_OUT_OF_RANGE:proposal_id"):
        submit(atlas, proposal_id=bad)
    assert atlas.get_evidence_count() == 0


def test_oversized_inputs_are_rejected(atlas, direct_vm):
    with direct_vm.expect_revert("EXPECTED:CLAIM_TOO_LONG"):
        submit(atlas, claim="c" * 501)
    with direct_vm.expect_revert("EXPECTED:SOURCE_URL_TOO_LONG"):
        submit(atlas, source_url="https://example.com/" + "a" * 600)
    with direct_vm.expect_revert("EXPECTED:SECTION_ID_TOO_LONG"):
        submit(atlas, related_section_id="s" * 65)
    assert atlas.get_evidence_count() == 0


def test_boundary_sizes_are_accepted(atlas, direct_vm):
    mock_page(direct_vm, page(), pattern=r".*")
    mock_answer(direct_vm, supported=False)
    url = "https://example.com/" + "a" * 480  # exactly 500 characters
    assert len(url) == 500
    submit(atlas, source_url=url, claim="c" * 500, related_section_id="")
    assert atlas.get_evidence(1)["claim"] == "c" * 500


def test_claim_is_trimmed_not_rewritten(atlas, web):
    submit(atlas, claim="   " + CLAIM_PLAIN + "  \n")
    assert atlas.get_evidence(1)["claim"] == CLAIM_PLAIN


# ---- views -------------------------------------------------------------------


def test_get_evidence_validates_ids(atlas, web, direct_vm):
    submit(atlas)
    for bad in BAD_INT:
        with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:evidence_id"):
            atlas.get_evidence(bad)
    for missing in (0, 2, 99):
        with direct_vm.expect_revert("EXPECTED:EVIDENCE_NOT_FOUND"):
            atlas.get_evidence(missing)
    with direct_vm.expect_revert("EXPECTED:INTEGER_OUT_OF_RANGE:evidence_id"):
        atlas.get_evidence(-1)
    assert atlas.get_evidence(1)["evidence_id"] == 1


def test_proposal_scoped_views_validate_the_proposal(atlas, direct_vm):
    for view, extra in (
        ("get_proposal_evidence_count", ()),
        ("get_proposal_evidence_ids_page", (0, 10)),
        ("get_proposal_evidence_page", (0, 10)),
    ):
        fn = getattr(atlas, view)
        with direct_vm.expect_revert("EXPECTED:PROPOSAL_NOT_FOUND"):
            fn(99, *extra)
        with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:proposal_id"):
            fn(True, *extra)
        with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:proposal_id"):
            fn("1", *extra)


PAGED = [
    ("get_evidence_page", ()),
    ("get_proposal_evidence_ids_page", (1,)),
    ("get_proposal_evidence_page", (1,)),
]


@pytest.mark.parametrize("view,prefix", PAGED, ids=[v for v, _ in PAGED])
def test_pagination_arguments_are_validated(atlas, direct_vm, view, prefix):
    fn = getattr(atlas, view)
    for bad in BAD_INT:
        with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:offset"):
            fn(*prefix, bad, 10)
        with direct_vm.expect_revert("EXPECTED:INVALID_TYPE:limit"):
            fn(*prefix, 0, bad)
    with direct_vm.expect_revert("EXPECTED:PAGE_LIMIT_INVALID"):
        fn(*prefix, 0, 0)
    with direct_vm.expect_revert("EXPECTED:PAGE_LIMIT_TOO_LARGE"):
        fn(*prefix, 0, 51)
    with direct_vm.expect_revert("EXPECTED:INTEGER_OUT_OF_RANGE:offset"):
        fn(*prefix, -1, 10)
    with direct_vm.expect_revert("EXPECTED:INTEGER_OUT_OF_RANGE:limit"):
        fn(*prefix, 0, -5)


def test_pages_are_bounded_even_with_many_records(atlas, web):
    for _ in range(12):
        submit(atlas)
    assert len(atlas.get_evidence_page(0, 5)) == 5
    assert len(atlas.get_proposal_evidence_page(1, 0, 50)) == 12
    assert atlas.get_evidence_page(11, 50)[0]["evidence_id"] == 12
    assert atlas.get_proposal_evidence_ids_page(1, 10, 50) == [11, 12]


# ---- ordering of checks --------------------------------------------------------


def test_only_the_proposer_is_checked_before_the_arguments_are(atlas, direct_vm, direct_bob):
    """Authorisation first (like the charter methods), so a stranger learns nothing about argument validity."""
    direct_vm.sender = direct_bob
    with direct_vm.expect_revert("EXPECTED:NOT_PROPOSER"):
        submit(atlas, source_url="not a url", claim="")


def test_unknown_proposal_is_reported_before_arguments(atlas, direct_vm):
    with direct_vm.expect_revert("EXPECTED:PROPOSAL_NOT_FOUND"):
        submit(atlas, proposal_id=7, source_url="not a url")
