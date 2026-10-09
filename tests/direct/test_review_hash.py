"""Stage 3 hashes (docs/CONSTITUTIONAL_REVIEW_MODEL.md).

Every expected value is recomputed HERE from the documented canonical strings with the SDK's keccak primitive.
The contract's own hashing helpers are never called by these tests.
"""

import pytest

from evidence_support import PROPOSAL
from review_support import all_findings, findings_of, fnd, keccak_hex, mock_review, request, review_of, reviewable  # noqa: F401


def expected_set_hash(c, proposal_id=1, count=None):
    records = c.get_proposal_evidence_page(proposal_id, 0, 50)
    records = records if count is None else records[:count]
    lines = ["chartergate.evidenceset.v1", f"proposal_id={proposal_id}", f"count={len(records)}"]
    for r in records:
        lines.append(f"evidence_id={r['evidence_id']}|content_hash={r['content_hash']}|status={r['status']}")
    return keccak_hex("\n".join(lines))


def expected_context_hash(c, proposal_id=1, count=None, sections=("1@2", "2@3")):
    p = c.get_proposal(proposal_id)
    version = p["charter_version_at_submission"]
    n = len(c.get_proposal_evidence_page(proposal_id, 0, 50)) if count is None else count
    lines = [
        "chartergate.reviewcontext.v1",
        f"proposal_id={proposal_id}",
        f"title={' '.join(p['title'].split())}",
        f"description={' '.join(p['description'].split())}",
        f"requested_action={' '.join(p['requested_action'].split())}",
        f"charter_version={version}",
        *[f"section={s}" for s in sections],
        f"evidence_count={n}",
        f"evidence_set_hash={expected_set_hash(c, proposal_id, count)}",
    ]
    return keccak_hex("\n".join(lines))


def expected_review_hash(context_hash, verdict, findings):
    lines = ["chartergate.review.v1", f"context_hash={context_hash}", f"verdict={verdict}"]
    for f in findings:
        ev = ",".join(str(i) for i in f["evidence_ids"])
        lines.append(f"section={f['section_id']}|finding={f['finding']}|repairable={'true' if f['repairable'] else 'false'}|evidence={ev}")
    return keccak_hex("\n".join(lines))


def run(c, vm, findings):
    mock_review(vm, findings)
    request(c)
    return review_of(c)


def test_evidence_set_hash_matches_the_documented_canonical_string(reviewable, direct_vm):
    r = run(reviewable, direct_vm, all_findings())
    assert r["evidence_set_hash"] == expected_set_hash(reviewable)


def test_context_hash_matches_the_documented_canonical_string(reviewable, direct_vm):
    r = run(reviewable, direct_vm, all_findings())
    assert r["review_context_hash"] == expected_context_hash(reviewable)


def test_review_hash_matches_the_documented_canonical_string(reviewable, direct_vm):
    r = run(reviewable, direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=True, ev=[1], rationale="missing disclosure")])
    assert r["review_hash"] == expected_review_hash(r["review_context_hash"], r["verdict"], findings_of(reviewable))


def test_review_hash_ignores_prose(reviewable, direct_vm):
    """Two equivalent judgments with different wording and missing-fact text hash the same."""
    a = [fnd("1", rationale="Short."), fnd("2", "UNCLEAR", ev=[3], missing="fact A", rationale="One.")]
    r = run(reviewable, direct_vm, a)
    # the expected hash is independent of rationale and missing_fact by construction (see expected_review_hash)
    assert r["review_hash"] == expected_review_hash(r["review_context_hash"], "INSUFFICIENT_EVIDENCE", findings_of(reviewable))


def test_review_hash_covers_the_judgment_and_not_the_wording(charter, direct_vm, direct_alice):
    """Two reviews with identical structured judgments and different prose are both explained by the same
    prose-free canonical string."""
    from conftest import MISSION, TRANSPARENCY

    # identical state, different wording: run it twice via two proposals with identical text under the same charter
    charter.add_charter_section(*MISSION)
    charter.add_charter_section(*TRANSPARENCY)
    direct_vm.sender = direct_alice
    charter.submit_proposal(*PROPOSAL)
    charter.submit_proposal(*PROPOSAL)
    mock_review(direct_vm, [fnd("1", rationale="Prose number one."), fnd("2", rationale="Another sentence.")])
    request(charter, 1)
    direct_vm.clear_mocks()
    mock_review(direct_vm, [fnd("1", rationale="Completely different words."), fnd("2", rationale="Nothing alike.")])
    request(charter, 2)
    a, b = review_of(charter, 1), review_of(charter, 2)
    # proposals 1 and 2 differ only by id, so context hashes differ; the structured judgment is the same
    assert a["review_context_hash"] != b["review_context_hash"]
    assert a["verdict"] == b["verdict"]
    assert expected_review_hash(a["review_context_hash"], "ELIGIBLE", findings_of(charter, 1)) == a["review_hash"]
    assert expected_review_hash(b["review_context_hash"], "ELIGIBLE", findings_of(charter, 2)) == b["review_hash"]
    assert [f["rationale"] for f in findings_of(charter, 1)] != [f["rationale"] for f in findings_of(charter, 2)]


def test_review_hash_changes_when_the_material_judgment_changes(reviewable, direct_vm):
    run(reviewable, direct_vm, [fnd("1"), fnd("2", "VIOLATED", repairable=True)])
    r = review_of(reviewable)
    base = findings_of(reviewable)
    ctx = r["review_context_hash"]
    flipped = copy_with(base, 1, repairable=False)
    assert expected_review_hash(ctx, "INELIGIBLE", flipped) != r["review_hash"]
    assert expected_review_hash(ctx, "REPAIRABLE", copy_with(base, 1, evidence_ids=[1])) != r["review_hash"]
    assert expected_review_hash(ctx, "REPAIRABLE", base) == r["review_hash"]


def copy_with(findings, index, **changes):
    out = [dict(f) for f in findings]
    out[index].update(changes)
    return out


def test_context_hash_commits_to_the_proposal_text_and_evidence_set(reviewable, direct_vm, direct_alice):
    """A second proposal with different text and no evidence has a different context and evidence-set hash."""
    reviewable.submit_proposal("Another proposal", "Different description.", "Different action")
    run(reviewable, direct_vm, all_findings())
    direct_vm.clear_mocks()
    mock_review(direct_vm, [fnd("1"), fnd("2")])
    request(reviewable, 2)
    a, b = review_of(reviewable, 1), review_of(reviewable, 2)
    assert a["evidence_set_hash"] != b["evidence_set_hash"]
    assert a["review_context_hash"] != b["review_context_hash"]
    assert b["evidence_set_hash"] == expected_set_hash(reviewable, 2)
    assert b["evidence_count_at_review"] == 0
    assert b["review_context_hash"] == expected_context_hash(reviewable, 2)


def test_changing_satisfied_to_not_applicable_changes_the_review_hash(charter, direct_vm, direct_alice):
    """SATISFIED (applies and is met) and NOT_APPLICABLE (does not govern this proposal) are different constitutional
    interpretations, so the finding class is part of the review hash.

    Two identical proposals are reviewed with different classes for section 1. Each stored hash equals the documented
    canonical string for ITS findings, and re-hashing review 1 with section 1 changed to NOT_APPLICABLE (same context,
    same verdict) gives a different value."""
    from conftest import MISSION, TRANSPARENCY

    charter.add_charter_section(*MISSION)
    charter.add_charter_section(*TRANSPARENCY)
    direct_vm.sender = direct_alice
    charter.submit_proposal(*PROPOSAL)
    charter.submit_proposal(*PROPOSAL)
    mock_review(direct_vm, [fnd("1", "SATISFIED"), fnd("2")])
    request(charter, 1)
    direct_vm.clear_mocks()
    mock_review(direct_vm, [fnd("1", "NOT_APPLICABLE"), fnd("2")])
    request(charter, 2)
    sat, na = review_of(charter, 1), review_of(charter, 2)
    assert sat["verdict"] == na["verdict"] == "ELIGIBLE"
    assert findings_of(charter, 1)[0]["finding"] == "SATISFIED" and findings_of(charter, 2)[0]["finding"] == "NOT_APPLICABLE"
    assert sat["review_hash"] == expected_review_hash(sat["review_context_hash"], "ELIGIBLE", findings_of(charter, 1))
    assert na["review_hash"] == expected_review_hash(na["review_context_hash"], "ELIGIBLE", findings_of(charter, 2))
    swapped = copy_with(findings_of(charter, 1), 0, finding="NOT_APPLICABLE")
    assert expected_review_hash(sat["review_context_hash"], "ELIGIBLE", swapped) != sat["review_hash"]
    assert sat["review_hash"] != na["review_hash"]
