"""Stage 5 hashes (docs/PRECEDENT_MEMORY_MODEL.md).

Every expected value is recomputed HERE from the documented canonical strings with the SDK's keccak primitive. The contract's own
hashing helpers are never called by these tests."""

import pytest

from precedent_support import ITEMIZED, NO_BREAKDOWN, VIOLATED, cite, findings, keccak_hex, precedent_set_hash_reference, precedents_of, propose, review, world  # noqa: F401
from review_support import findings_of, fnd, mock_review, request

collapse = lambda s: " ".join(s.split())  # noqa: E731


def evidence_set_empty(pid):
    return keccak_hex(f"chartergate.evidenceset.v1\nproposal_id={pid}\ncount=0")


def context_v1(c, pid, sections=("1@2", "2@3", "3@4")):
    p = c.get_proposal(pid)
    lines = [
        "chartergate.reviewcontext.v1",
        f"proposal_id={pid}",
        f"title={collapse(p['title'])}",
        f"description={collapse(p['description'])}",
        f"requested_action={collapse(p['requested_action'])}",
        f"charter_version={p['charter_version_at_submission']}",
        *[f"section={s}" for s in sections],
        "evidence_count=0",
        f"evidence_set_hash={evidence_set_empty(pid)}",
    ]
    return keccak_hex("\n".join(lines))


def context_v3(base, set_hash):
    return keccak_hex("\n".join(["chartergate.reviewcontext.v3", f"base_context_hash={base}", f"precedent_set_hash={set_hash}"]))


def result_hash(ctx, verdict, fs, citations):
    version = "chartergate.review.v2" if citations else "chartergate.review.v1"
    lines = [version, f"context_hash={ctx}", f"verdict={verdict}"]
    for f in fs:
        ev = ",".join(str(i) for i in f["evidence_ids"])
        lines.append(f"section={f['section_id']}|finding={f['finding']}|repairable={'true' if f['repairable'] else 'false'}|evidence={ev}")
    for c in citations:
        lines.append(f"precedent=section={c['section_id']}|review={c['precedent_review_id']}|treatment={c['treatment']}")
    return keccak_hex("\n".join(lines))


# ---- zero precedent keeps the old formats exactly ----------------------------------------------------------------------------


def test_a_review_with_no_candidates_uses_the_v1_context_and_v1_result_hash(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    r = world.get_constitutional_review(1)
    assert r["review_context_hash"] == context_v1(world, 1)
    assert r["review_hash"] == result_hash(r["review_context_hash"], "REPAIRABLE", findings_of(world, 1), [])


# ---- the precedent set hash ----------------------------------------------------------------------------------------------------


def test_the_stored_precedent_set_hash_matches_the_documented_canonical_string(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    review(world, direct_vm, propose(world), findings())
    p = precedents_of(world, 2)
    assert p["precedent_set_hash"] == precedent_set_hash_reference(world, 2) != ""
    assert p["candidates"][0]["precedent_review_hash"] == world.get_constitutional_review(1)["review_hash"]


def test_a_precedent_aware_review_uses_the_v3_context_over_the_old_context(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    review(world, direct_vm, propose(world), findings())
    r = world.get_constitutional_review(2)
    base = context_v1(world, 2)
    assert r["review_context_hash"] == context_v3(base, precedents_of(world, 2)["precedent_set_hash"])
    assert r["review_context_hash"] != base  # the precedent snapshot is bound


def test_candidates_without_citations_use_the_v3_context_and_the_v1_result_format(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    review(world, direct_vm, propose(world), findings())
    r = world.get_constitutional_review(2)
    assert r["review_hash"] == result_hash(r["review_context_hash"], "ELIGIBLE", findings_of(world, 2), [])


def test_citations_use_the_v2_result_format_and_hash_treatment_and_association_not_prose(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    review(world, direct_vm, propose(world, ITEMIZED), findings(precedents={"3": [cite(1, "DISTINGUISHED", "Prose one that is not hashed.")]}))
    review(world, direct_vm, propose(world), findings(precedents={"3": [cite(2, "DISTINGUISHED", "Entirely different prose.")]}))
    for rid in (2, 3):
        r = world.get_constitutional_review(rid)
        cites = precedents_of(world, rid)["citations"]
        assert r["review_hash"] == result_hash(r["review_context_hash"], "ELIGIBLE", findings_of(world, rid), cites)
        assert r["review_context_hash"] == context_v3(context_v1(world, rid), precedents_of(world, rid)["precedent_set_hash"])


# ---- every material change changes the hash --------------------------------------------------------------------------------------


@pytest.fixture
def base_case(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    review(world, direct_vm, propose(world, ITEMIZED), findings(precedents={"3": [cite(1, "DISTINGUISHED", "x")]}))
    r = world.get_constitutional_review(2)
    return world, r, findings_of(world, 2), precedents_of(world, 2)


def set_hash(cands):
    lines = ["chartergate.precedents.v1", f"count={len(cands)}"]
    for x in cands:
        lines.append(f"section={x['section_id']}|rule={x['rule']}|precedent_review_id={x['precedent_review_id']}|precedent_review_hash={x['precedent_review_hash']}")
    return keccak_hex("\n".join(lines))


@pytest.mark.parametrize(
    "change",
    [
        lambda c: [{**c[0], "precedent_review_id": 9}] + c[1:],
        lambda c: [{**c[0], "precedent_review_hash": "0x" + "00" * 32}] + c[1:],
        lambda c: [{**c[0], "section_id": "9"}] + c[1:],
        lambda c: [{**c[0], "rule": "1@9"}] + c[1:],
        lambda c: list(reversed(c)),
        lambda c: c[:-1],
    ],
    ids=["candidate-review-id", "candidate-review-hash", "section-association", "rule-identity", "order", "membership"],
)
def test_changing_any_candidate_field_changes_the_precedent_set_hash(base_case, change):
    _c, _r, _f, p = base_case
    assert set_hash(change(p["candidates"])) != p["precedent_set_hash"]


def test_changing_citation_treatment_or_review_or_the_current_finding_changes_the_result_hash(base_case):
    _c, r, fs, p = base_case
    ctx = r["review_context_hash"]
    base = result_hash(ctx, "ELIGIBLE", fs, p["citations"])
    assert base == r["review_hash"]
    assert result_hash(ctx, "ELIGIBLE", fs, [{**p["citations"][0], "treatment": "FOLLOWED"}]) != base  # FOLLOWED vs DISTINGUISHED
    assert result_hash(ctx, "ELIGIBLE", fs, [{**p["citations"][0], "precedent_review_id": 7}]) != base
    assert result_hash(ctx, "ELIGIBLE", fs, [{**p["citations"][0], "section_id": "2"}]) != base
    assert result_hash(ctx, "ELIGIBLE", fs, []) != base  # no citation uses the v1 format
    other = [dict(f) for f in fs]
    other[2]["finding"] = "NOT_APPLICABLE"
    assert result_hash(ctx, "ELIGIBLE", other, p["citations"]) != base
    assert result_hash(context_v3(context_v1(base_case[0], 2), "0x" + "11" * 32), "ELIGIBLE", fs, p["citations"]) != base


def test_a_revision_review_binds_precedent_over_the_v2_revision_context(world, direct_vm):
    from repair_support import mock_repair

    review(world, direct_vm, propose(world), findings(**VIOLATED))  # review 1, proposal 1
    other = propose(world)
    review(world, direct_vm, other, findings(**VIOLATED))  # review 2, proposal 2 (sees review 1)
    mock_repair(direct_vm)
    world.submit_repair_revision(other, ITEMIZED[0], ITEMIZED[1], ITEMIZED[2])
    direct_vm.clear_mocks()
    mock_review(direct_vm, findings(precedents={"3": [cite(1, "DISTINGUISHED", "Itemized budget.")]}))
    world.request_revision_review(1)  # review 3 judges proposal 2's revision; candidates exclude review 2 (same lineage)
    p = precedents_of(world, 3)
    assert {x["precedent_review_id"] for x in p["candidates"]} == {1}
    rev = world.get_proposal_revision(1)
    v2 = keccak_hex(
        "\n".join(
            [
                "chartergate.reviewcontext.v2",
                "proposal_id=2",
                f"revision_id={rev['revision_id']}",
                f"revision_number={rev['revision_number']}",
                f"revision_hash={rev['revision_hash']}",
                f"title={collapse(rev['title'])}",
                f"description={collapse(rev['description'])}",
                f"requested_action={collapse(rev['requested_action'])}",
                "charter_version=4",
                "section=1@2",
                "section=2@3",
                "section=3@4",
                "evidence_count=0",
                f"evidence_set_hash={evidence_set_empty(2)}",
            ]
        )
    )
    r = world.get_constitutional_review(3)
    assert r["review_context_hash"] == context_v3(v2, p["precedent_set_hash"])
    assert r["review_hash"] == result_hash(r["review_context_hash"], "ELIGIBLE", findings_of(world, 3), p["citations"])
