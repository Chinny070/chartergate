"""The canonical evidence hash (docs/EVIDENCE_MODEL.md).

Every expected value below is recomputed HERE, from the documented canonical string, with the SDK's keccak
primitive. The contract's own hashing helper is never called by these tests.
"""

import pytest

from conftest import hex_of  # noqa: F401
from evidence_support import (
    CLAIM_NUMBERED,
    CLAIM_PLAIN,
    FACT,
    URL,
    atlas,  # noqa: F401  (fixture)
    mock_answer,
    mock_page,
    page,
    reset,
    submit,
    web,  # noqa: F401  (fixture)
)

HASH_VERSION = "chartergate.evidence.v2"


def keccak_hex(data: bytes) -> str:
    from genlayer.py.keccak import Keccak256

    h = Keccak256()
    h.update(data)
    return "0x" + h.hexdigest()


def expected_hash(
    *,
    claim=CLAIM_NUMBERED,
    url=URL,
    kind="STATIC_WEB",
    method="GET",
    status="VERIFIED",
    fact=FACT,
    value="46%",
    section="2",
    revision=3,
    proposal_id=1,
):
    """The documented canonical string, written out independently of the contract."""
    canonical = "\n".join(
        [
            HASH_VERSION,
            f"proposal_id={proposal_id}",
            f"source_url={url}",
            f"source_kind={kind}",
            f"retrieval_method={method}",
            f"claim={' '.join(claim.split())}",
            f"status={status}",
            f"fact={fact}",
            f"value={value}",
            f"section={section}",
            f"section_revision_version={revision}",
        ]
    )
    return keccak_hex(canonical.encode("utf-8"))


def run(c, vm, *, html=None, value="46%", excerpt=None, supported=True, **submit_kw):
    reset(vm)
    mock_page(vm, html if html is not None else page(), pattern=r".*")
    mock_answer(vm, supported=supported, value=value, excerpt=excerpt or f"Team: {value}")
    submit(c, **submit_kw)
    return c.get_evidence(c.get_evidence_count())


# ---- the primitive ------------------------------------------------------------------------------


def test_the_sdk_primitive_is_real_ethereum_keccak256(charter):  # `charter` loads the SDK into the test process
    """Known vectors. NIST SHA3-256 would give different values (different padding), so this pins the algorithm."""
    assert keccak_hex(b"") == "0xc5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470"
    assert keccak_hex(b"abc") == "0x4e03657aea45a94fc7d47ba826c8d667c0d1e6e33a64a036ec44f58fa12d6c45"


# ---- the canonical form is exactly what the docs say ------------------------------------------------


def test_the_record_hash_equals_the_independently_recomputed_hash(atlas, web):
    submit(atlas)
    r = atlas.get_evidence(1)
    assert r["content_hash"] == expected_hash()


def test_golden_vector_pins_the_exact_bytes_of_the_canonical_string(atlas, web):
    """If anyone changes the field order, a label, the separator or the version, this fails loudly."""
    submit(atlas)
    canonical = (
        "chartergate.evidence.v2\nproposal_id=1\nsource_url=https://atlas.example.org/tokenomics\n"
        "source_kind=STATIC_WEB\nretrieval_method=GET\nclaim=Atlas team token allocation is 46%.\n"
        "status=VERIFIED\nfact=team_token_allocation\nvalue=46%\nsection=2\nsection_revision_version=3"
    )
    assert atlas.get_evidence(1)["content_hash"] == keccak_hex(canonical.encode("utf-8"))


def test_every_documented_field_is_in_the_hash_and_nothing_else_is(atlas, web):
    """Flip each included field in the independent recomputation: every one must change the hash."""
    submit(atlas)
    actual = atlas.get_evidence(1)["content_hash"]
    base = dict()
    assert expected_hash(**base) == actual
    for name, other in dict(
        claim="A different claim.", url=URL + "x", kind="API", method="RENDER_TEXT", status="UNVERIFIABLE",
        fact="community_token_allocation", value="47%", section="1", revision=4, proposal_id=2,
    ).items():
        assert expected_hash(**{name: other}) != actual, name


# ---- same canonical evidence => same hash --------------------------------------------------------------


def test_same_canonical_evidence_gives_the_same_hash_regardless_of_id_time_excerpt_and_page_noise(atlas, direct_vm):
    direct_vm.warp("2026-10-08T21:31:00Z")
    a = run(atlas, direct_vm, html=page(footer="noise one"), excerpt="Team: 46%")
    direct_vm.warp("2031-01-01T00:00:00Z")
    b = run(atlas, direct_vm, html=page(footer="completely different noise", extra="<p>The team holds Team: 46% of supply.</p>"), excerpt="Team: 46%")
    assert a["evidence_id"] != b["evidence_id"] and a["retrieved_at"] != b["retrieved_at"]
    assert a["content_hash"] == b["content_hash"] == expected_hash()


def test_the_excerpt_is_deliberately_excluded_from_the_hash(atlas, direct_vm):
    """Two different (both grounded, both correct) quotes for the same fact and value hash the same."""
    both = page(extra="<p>The founding team holds 46% in total.</p>")
    a = run(atlas, direct_vm, html=both, excerpt="Team: 46%")
    b = run(atlas, direct_vm, html=both, excerpt="The founding team holds 46% in total.")
    assert a["excerpt"] != b["excerpt"]
    assert a["content_hash"] == b["content_hash"]


# ---- each canonical field changes the hash ----------------------------------------------------------------


def test_changing_only_the_claim_changes_the_hash(atlas, direct_vm):
    a = run(atlas, direct_vm, claim="Atlas team token allocation is 46%.")
    b = run(atlas, direct_vm, claim="The team's token allocation is stated as 46% in the documentation.")
    assert (a["source_url"], a["normalized_fact"], a["normalized_value"], a["status"]) == (
        b["source_url"], b["normalized_fact"], b["normalized_value"], b["status"],
    )
    assert a["content_hash"] != b["content_hash"]
    assert a["content_hash"] == expected_hash(claim="Atlas team token allocation is 46%.")
    assert b["content_hash"] == expected_hash(claim="The team's token allocation is stated as 46% in the documentation.")


def test_changing_only_the_fact_changes_the_hash(atlas, direct_vm):
    a = run(atlas, direct_vm, claim=CLAIM_PLAIN, fact_key="team_token_allocation")
    b = run(atlas, direct_vm, claim=CLAIM_PLAIN, fact_key="community_token_allocation")
    assert a["normalized_value"] == b["normalized_value"] == "46%"
    assert a["content_hash"] != b["content_hash"]
    assert b["content_hash"] == expected_hash(claim=CLAIM_PLAIN, fact="community_token_allocation")


def test_changing_only_the_value_changes_the_hash(atlas, direct_vm):
    a = run(atlas, direct_vm, claim=CLAIM_PLAIN, html=page(team="46%"), value="46%")
    b = run(atlas, direct_vm, claim=CLAIM_PLAIN, html=page(team="45%"), value="45%")
    assert a["content_hash"] != b["content_hash"]
    assert b["content_hash"] == expected_hash(claim=CLAIM_PLAIN, value="45%")


def test_changing_only_the_source_url_changes_the_hash(atlas, direct_vm):
    a = run(atlas, direct_vm, source_url=URL)
    other = "https://atlas.example.org/token-distribution"
    b = run(atlas, direct_vm, source_url=other)
    assert a["content_hash"] != b["content_hash"]
    assert b["content_hash"] == expected_hash(url=other)


def test_changing_only_the_retrieval_method_changes_the_hash(atlas, direct_vm):
    a = run(atlas, direct_vm, source_kind="STATIC_WEB")
    b = run(atlas, direct_vm, source_kind="DYNAMIC_WEB")
    assert a["content_hash"] != b["content_hash"]
    assert b["content_hash"] == expected_hash(kind="DYNAMIC_WEB", method="RENDER_TEXT")


def test_changing_only_the_status_changes_the_hash(atlas, direct_vm):
    a = run(atlas, direct_vm, claim=CLAIM_PLAIN, supported=True)
    b = run(atlas, direct_vm, claim=CLAIM_PLAIN, supported=False)
    assert (a["status"], b["status"]) == ("VERIFIED", "UNVERIFIABLE")
    assert a["content_hash"] != b["content_hash"]
    assert b["content_hash"] == expected_hash(claim=CLAIM_PLAIN, status="UNVERIFIABLE")


def test_changing_the_related_charter_section_changes_the_hash(atlas, direct_vm):
    a = run(atlas, direct_vm, related_section_id="2")
    b = run(atlas, direct_vm, related_section_id="1")
    c = run(atlas, direct_vm, related_section_id="")
    assert len({a["content_hash"], b["content_hash"], c["content_hash"]}) == 3
    assert a["content_hash"] == expected_hash(section="2", revision=3)
    assert b["content_hash"] == expected_hash(section="1", revision=4)
    assert c["content_hash"] == expected_hash(section="", revision=0)


def test_the_relevant_charter_revision_is_in_the_hash(atlas, direct_vm, direct_owner, direct_alice):
    """Section 2 is revised after proposal 1; a later proposal sees the newer revision and hashes differently."""
    first = run(atlas, direct_vm, related_section_id="2")  # proposal 1, charter v4, section 2 as of revision 3
    direct_vm.sender = direct_owner
    atlas.update_charter_section("2", "Transparency", "Rewritten transparency rule")  # v5
    direct_vm.sender = direct_alice
    atlas.submit_proposal("Second proposal", "Second description", "Second action")  # proposal 2, bound to v5
    second = run(atlas, direct_vm, proposal_id=2, related_section_id="2")
    assert (first["related_revision_version"], second["related_revision_version"]) == (3, 5)
    assert first["content_hash"] == expected_hash(proposal_id=1, revision=3)
    assert second["content_hash"] == expected_hash(proposal_id=2, revision=5)
    assert first["content_hash"] != second["content_hash"]


# ---- intentional canonicalisation (and what is NOT normalised) -----------------------------------------------


@pytest.mark.parametrize(
    "claim",
    [
        CLAIM_NUMBERED,
        "  " + CLAIM_NUMBERED + "  ",
        CLAIM_NUMBERED.replace(" ", "   "),
        CLAIM_NUMBERED.replace(" ", "\n"),
        CLAIM_NUMBERED.replace(" ", "\t"),
    ],
    ids=["plain", "padded", "multiple-spaces", "newlines", "tabs"],
)
def test_whitespace_in_the_claim_is_normalised_before_hashing(atlas, direct_vm, claim):
    r = run(atlas, direct_vm, claim=claim)
    assert r["content_hash"] == expected_hash(claim=CLAIM_NUMBERED)


@pytest.mark.parametrize("key", ["team_token_allocation", "TEAM_TOKEN_ALLOCATION", "Team Token-Allocation", " team-token allocation "])
def test_fact_key_formatting_is_normalised_before_hashing(atlas, direct_vm, key):
    assert run(atlas, direct_vm, fact_key=key)["content_hash"] == expected_hash()


@pytest.mark.parametrize("shown", ["46%", "46.0%", "46.00%", "46 %"])
def test_equivalent_percent_formatting_is_normalised_before_hashing(atlas, direct_vm, shown):
    r = run(atlas, direct_vm, html=page(team=shown), value=shown, excerpt=f"Team: {shown}", claim=CLAIM_PLAIN)
    assert r["content_hash"] == expected_hash(claim=CLAIM_PLAIN, value="46%")


def test_things_that_are_not_normalised_do_change_the_hash(atlas, direct_vm):
    """Documented: claim case, URL case and 0.46 vs 46% are different evidence. Nothing is guessed."""
    base = run(atlas, direct_vm, claim=CLAIM_NUMBERED)
    assert run(atlas, direct_vm, claim=CLAIM_NUMBERED.upper())["content_hash"] != base["content_hash"]
    assert run(atlas, direct_vm, source_url=URL.replace("tokenomics", "Tokenomics"))["content_hash"] != base["content_hash"]
    frac = run(atlas, direct_vm, html=page(team="0.46"), value="0.46", excerpt="Team: 0.46", claim=CLAIM_PLAIN)
    assert frac["normalized_value"] == "0.46"
    assert frac["content_hash"] != expected_hash(claim=CLAIM_PLAIN, value="46%")


# ---- failed retrievals are hashed too, with the fact that was asked ----------------------------------------------


def test_a_failed_retrieval_hashes_the_asked_fact_and_an_empty_value(atlas, direct_vm):
    reset(direct_vm)
    mock_page(direct_vm, status=404, body="", pattern=r".*")
    submit(atlas)
    r = atlas.get_evidence(1)
    assert (r["status"], r["normalized_fact"], r["normalized_value"]) == ("SOURCE_UNAVAILABLE", FACT, "")
    assert r["content_hash"] == expected_hash(status="SOURCE_UNAVAILABLE", value="")


def test_the_hash_can_be_recomputed_from_the_stored_record_alone(atlas, direct_vm):
    """Auditability: every input to the hash is a stored field, so anyone can verify a record."""
    run(atlas, direct_vm)
    run(atlas, direct_vm, claim=CLAIM_PLAIN, supported=False)
    reset(direct_vm)
    mock_page(direct_vm, status=500, body="", pattern=r".*")
    submit(atlas, source_kind="DYNAMIC_WEB")
    for r in atlas.get_evidence_page(0, 50):
        assert r["content_hash"] == expected_hash(
            proposal_id=r["proposal_id"], url=r["source_url"], kind=r["source_kind"], method=r["retrieval_method"],
            claim=r["claim"], status=r["status"], fact=r["normalized_fact"], value=r["normalized_value"],
            section=r["related_section_id"], revision=r["related_revision_version"],
        )
