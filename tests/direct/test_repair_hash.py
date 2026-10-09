"""Stage 4 hashes (docs/PROPOSAL_REVISION_MODEL.md).

Every expected value is recomputed HERE from the documented canonical strings with the SDK's keccak primitive. The contract's
own hashing helpers are never called by these tests."""

import pytest

from repair_support import ORIGINAL, REPAIRED, accept_repair, repairable, review_revision, revision_hash_reference
from review_support import findings_of, fnd, keccak_hex, review_of

OK = [fnd("1"), fnd("2", ev=[1]), fnd("3")]
BASE = dict(proposal_id=1, revision_number=2, parent=0, source_review=1, charter_version=4, text=REPAIRED, addressed=("3",))


def test_the_stored_revision_hash_matches_the_documented_canonical_string(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    assert repairable.get_proposal_revision(1)["revision_hash"] == revision_hash_reference(**BASE)
    assert repairable.get_effective_proposal(1)["revision_hash"] == revision_hash_reference(**BASE)


def test_a_later_revision_hash_binds_its_lineage(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, [fnd("1"), fnd("2", ev=[1]), fnd("3", "VIOLATED", repairable=True)])
    text = ("Atlas RPC Gateway", REPAIRED[1] + " Plus a delivery timeline.", REPAIRED[2])
    accept_repair(repairable, direct_vm, text)
    stored = repairable.get_proposal_revision(2)["revision_hash"]
    assert stored == revision_hash_reference(proposal_id=1, revision_number=3, parent=1, source_review=2, charter_version=4, text=text, addressed=("3",))
    # the same text with the wrong lineage would hash differently
    assert stored != revision_hash_reference(proposal_id=1, revision_number=3, parent=0, source_review=1, charter_version=4, text=text, addressed=("3",))


@pytest.mark.parametrize(
    "field,value",
    [
        ("proposal_id", 2),
        ("revision_number", 3),
        ("parent", 1),
        ("source_review", 2),
        ("charter_version", 5),
        ("text", ("Atlas RPC Gateways", REPAIRED[1], REPAIRED[2])),
        ("text", (REPAIRED[0], REPAIRED[1] + " x", REPAIRED[2])),
        ("text", (REPAIRED[0], REPAIRED[1], REPAIRED[2] + " x")),
        ("addressed", ("2", "3")),
        ("addressed", ()),
    ],
    ids=["proposal", "number", "parent", "source-review", "charter", "title", "description", "action", "addressed-more", "addressed-none"],
)
def test_changing_any_material_field_changes_the_revision_hash(charter, field, value):  # `charter` loads the contract so the SDK keccak is importable
    assert revision_hash_reference(**{**BASE, field: value}) != revision_hash_reference(**BASE)


def test_harmless_whitespace_does_not_change_the_hash_but_case_does(repairable, direct_vm):
    spaced = (REPAIRED[0], REPAIRED[1].replace(", ", ",   ").replace(". ", ".\n"), REPAIRED[2])
    assert revision_hash_reference(**{**BASE, "text": spaced}) == revision_hash_reference(**BASE)
    # and the contract agrees: padded input is stored as given but hashes as the collapsed text
    accept_repair(repairable, direct_vm, spaced)
    assert repairable.get_proposal_revision(1)["revision_hash"] == revision_hash_reference(**BASE)
    assert revision_hash_reference(**{**BASE, "text": (REPAIRED[0].upper(), REPAIRED[1], REPAIRED[2])}) != revision_hash_reference(**BASE)


def test_the_hash_excludes_the_explanation_and_the_proposer(repairable, direct_vm):
    from repair_support import mock_repair, repair

    mock_repair(direct_vm, reason="First wording.")
    repair(repairable)
    assert repairable.get_proposal_revision(1)["revision_hash"] == revision_hash_reference(**BASE)  # independent of the reason text


# ---- the revision review context and result hashes -----------------------------------------------------------------------


def set_hash(c, ids):
    recs = [c.get_evidence(i) for i in ids]
    lines = ["chartergate.evidenceset.v1", "proposal_id=1", f"count={len(recs)}"]
    for r in recs:
        lines.append(f"evidence_id={r['evidence_id']}|content_hash={r['content_hash']}|status={r['status']}")
    return keccak_hex("\n".join(lines))


def context_v2(c, revision, ids, sections=("1@2", "2@3", "3@4")):
    collapse = lambda s: " ".join(s.split())  # noqa: E731
    lines = [
        "chartergate.reviewcontext.v2",
        "proposal_id=1",
        f"revision_id={revision['revision_id']}",
        f"revision_number={revision['revision_number']}",
        f"revision_hash={revision['revision_hash']}",
        f"title={collapse(revision['title'])}",
        f"description={collapse(revision['description'])}",
        f"requested_action={collapse(revision['requested_action'])}",
        f"charter_version={revision['charter_version']}",
        *[f"section={s}" for s in sections],
        f"evidence_count={len(ids)}",
        f"evidence_set_hash={set_hash(c, ids)}",
    ]
    return keccak_hex("\n".join(lines))


def context_v1(c, ids):
    p = c.get_proposal(1)
    collapse = lambda s: " ".join(s.split())  # noqa: E731
    lines = [
        "chartergate.reviewcontext.v1",
        "proposal_id=1",
        f"title={collapse(p['title'])}",
        f"description={collapse(p['description'])}",
        f"requested_action={collapse(p['requested_action'])}",
        "charter_version=4",
        "section=1@2",
        "section=2@3",
        "section=3@4",
        f"evidence_count={len(ids)}",
        f"evidence_set_hash={set_hash(c, ids)}",
    ]
    return keccak_hex("\n".join(lines))


def review_hash(ctx, verdict, findings):
    lines = ["chartergate.review.v1", f"context_hash={ctx}", f"verdict={verdict}"]
    for f in findings:
        ev = ",".join(str(i) for i in f["evidence_ids"])
        lines.append(f"section={f['section_id']}|finding={f['finding']}|repairable={'true' if f['repairable'] else 'false'}|evidence={ev}")
    return keccak_hex("\n".join(lines))


def test_the_revision_review_context_hash_matches_the_documented_v2_format(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, OK)
    revision = repairable.get_proposal_revision(1)
    r = repairable.get_review_for_revision(1)
    assert r["review_context_hash"] == context_v2(repairable, revision, [1])
    assert r["evidence_set_hash"] == set_hash(repairable, [1])


def test_the_revision_review_result_hash_matches_the_documented_format(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    review_revision(repairable, direct_vm, OK)
    r = repairable.get_review_for_revision(1)
    assert r["review_hash"] == review_hash(r["review_context_hash"], "ELIGIBLE", findings_of(repairable, 2))


def test_a_root_review_still_uses_the_v1_context_format(repairable, direct_vm):
    r = review_of(repairable)
    assert r["review_context_hash"] == context_v1(repairable, [1])
    accept_repair(repairable, direct_vm)
    assert review_of(repairable)["review_context_hash"] == context_v1(repairable, [1])  # unchanged by the repair


def test_the_revision_context_hash_changes_with_the_revision_content(repairable, direct_vm):
    accept_repair(repairable, direct_vm)
    revision = dict(repairable.get_proposal_revision(1))
    base = context_v2(repairable, revision, [1])
    for key, value in (("description", revision["description"] + " x"), ("revision_hash", "0x" + "00" * 32), ("revision_id", 9), ("revision_number", 7)):
        assert context_v2(repairable, {**revision, key: value}, [1]) != base
