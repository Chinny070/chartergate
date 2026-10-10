"""Stage 6 hashes (docs/APPEAL_MODEL.md): appeal, appeal context, appellate decision and dissent.

Every expected value is recomputed HERE from the documented canonical strings with the SDK's keccak primitive. The contract's own
hashing helpers are never called by these tests."""

import pytest

from appeal_support import (
    GROUND,
    ITEMIZED,
    NO_BREAKDOWN,
    STATEMENT,
    VIOLATED,
    adverse_review,
    appeal,
    dissent,
    findings,
    keccak_hex,
    propose,
    review,
    world,  # noqa: F401  (fixture)
)
from precedent_support import cite

collapse = lambda s: " ".join(s.split())  # noqa: E731
SECTIONS = ("1@2", "2@3", "3@4")


def finding_line(f):
    ev = ",".join(str(i) for i in f["evidence_ids"])
    return f"section={f['section_id']}|finding={f['finding']}|repairable={'true' if f['repairable'] else 'false'}|evidence={ev}"


def appeal_hash(a, statement=None):
    lines = [
        "chartergate.appeal.v1",
        f"review_id={a['review_id']}",
        f"review_hash={a['original_review_hash']}",
        f"proposal_id={a['proposal_id']}",
        f"revision_id={a['revision_id']}",
        f"appellant={a['appellant']}",
        f"ground={a['ground']}",
        f"statement={collapse(a['statement'] if statement is None else statement)}",
        f"charter_version={a['charter_version']}",
        f"evidence_set_hash={a['evidence_set_hash']}",
        f"precedent_set_hash={a['precedent_set_hash']}",
    ]
    return keccak_hex("\n".join(lines))


def context_hash(a, review, sections=SECTIONS):
    lines = [
        "chartergate.appealcontext.v1",
        f"appeal_hash={a['appeal_hash']}",
        f"review_id={review['review_id']}",
        f"review_hash={review['review_hash']}",
        f"review_context_hash={review['review_context_hash']}",
        f"proposal_id={review['proposal_id']}",
        f"revision_id={a['revision_id']}",
        f"charter_version={a['charter_version']}",
        *[f"section={s}" for s in sections],
        f"evidence_count={a['evidence_count']}",
        f"evidence_set_hash={a['evidence_set_hash']}",
        f"precedent_set_hash={a['precedent_set_hash']}",
    ]
    return keccak_hex("\n".join(lines))


def decision_hash(ctx, verdict, kind, fs, cites=()):
    lines = ["chartergate.appellate.v1", f"appeal_context_hash={ctx}", f"verdict={verdict}", f"decision_kind={kind}"]
    lines += [finding_line(f) for f in fs]
    lines += [f"precedent=section={c['section_id']}|review={c['precedent_review_id']}|treatment={c['treatment']}" for c in cites]
    return keccak_hex("\n".join(lines))


def dissent_hash(aid, decision, verdict, fs, disagrees):
    lines = ["chartergate.dissent.v1", f"appeal_id={aid}", f"decision_hash={decision}", f"verdict={verdict}"]
    lines += [finding_line(f) for f in fs]
    lines.append("disagrees=" + ",".join(disagrees))
    return keccak_hex("\n".join(lines))


def test_the_appeal_hash_recomputes_independently(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    a = world.get_appeal(aid)
    assert a["appeal_hash"] == appeal_hash(a)
    assert a["precedent_set_hash"] == ""  # a zero-precedent original


def test_the_statement_is_hashed_after_whitespace_normalization_and_nothing_else_about_it_is_free(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED), statement="  The   budget\n rule   was misread.  ")
    a = world.get_appeal(aid)
    assert a["appeal_hash"] == appeal_hash(a, "The budget rule was misread.")  # whitespace is not material
    assert a["appeal_hash"] != appeal_hash(a, "The budget rule was misread!")  # words are


def test_the_appeal_hash_changes_with_every_identity_field(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    a = world.get_appeal(aid)
    base = appeal_hash(a)
    for key, other in [
        ("review_id", 99),
        ("original_review_hash", "0x" + "ab" * 32),
        ("proposal_id", 99),
        ("revision_id", 3),
        ("appellant", "0x" + "cd" * 20),
        ("ground", "PROCEDURAL_ERROR"),
        ("statement", "Another argument."),
        ("charter_version", 9),
        ("evidence_set_hash", "0x" + "ef" * 32),
        ("precedent_set_hash", "0x" + "12" * 32),
    ]:
        assert appeal_hash(dict(a, **{key: other})) != base, key


def test_the_appeal_context_hash_and_decision_hash_recompute_independently(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    a, original, d = world.get_appeal(aid), world.get_constitutional_review(rid), world.get_appellate_decision(aid)
    ctx = context_hash(a, original)
    assert d["appeal_context_hash"] == ctx
    fs = world.get_appeal_findings_page(aid, 0, 50)
    assert d["decision_hash"] == decision_hash(ctx, "REPAIRABLE", "AFFIRMED", fs)


def test_the_context_hash_binds_each_closed_record_component(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    a, original = world.get_appeal(aid), world.get_constitutional_review(rid)
    base = context_hash(a, original)
    assert context_hash(dict(a, appeal_hash="0x" + "11" * 32), original) != base
    assert context_hash(a, dict(original, review_hash="0x" + "22" * 32)) != base
    assert context_hash(a, dict(original, review_context_hash="0x" + "33" * 32)) != base
    assert context_hash(a, dict(original, proposal_id=9)) != base
    assert context_hash(dict(a, revision_id=2), original) != base
    assert context_hash(dict(a, charter_version=7), original) != base
    assert context_hash(a, original, ("1@2", "2@3", "3@5")) != base  # a different section revision
    assert context_hash(dict(a, evidence_count=1), original) != base
    assert context_hash(dict(a, evidence_set_hash="0x" + "44" * 32), original) != base
    assert context_hash(dict(a, precedent_set_hash="0x" + "55" * 32), original) != base


def test_the_decision_hash_binds_findings_verdict_and_disposition_but_not_prose(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    d = world.get_appellate_decision(aid)
    fs = world.get_appeal_findings_page(aid, 0, 50)
    ctx = d["appeal_context_hash"]
    assert d["decision_hash"] == decision_hash(ctx, "REPAIRABLE", "AFFIRMED", fs)
    reworded = [dict(f, rationale="completely different words", missing_fact="") for f in fs]
    assert decision_hash(ctx, "REPAIRABLE", "AFFIRMED", reworded) == d["decision_hash"]  # prose is excluded
    assert decision_hash(ctx, "REPAIRABLE", "MODIFIED", fs) != d["decision_hash"]
    assert decision_hash(ctx, "INELIGIBLE", "AFFIRMED", fs) != d["decision_hash"]
    flipped = [dict(f, repairable=False) if f["finding"] == "VIOLATED" else f for f in fs]
    assert decision_hash(ctx, "REPAIRABLE", "AFFIRMED", flipped) != d["decision_hash"]
    classed = [dict(f, finding="SATISFIED") if f["section_id"] == "3" else f for f in fs]
    assert decision_hash(ctx, "REPAIRABLE", "AFFIRMED", classed) != d["decision_hash"]
    evidenced = [dict(f, evidence_ids=[1]) if f["section_id"] == "1" else f for f in fs]
    assert decision_hash(ctx, "REPAIRABLE", "AFFIRMED", evidenced) != d["decision_hash"]


def test_precedent_use_in_an_appellate_decision_is_hashed(world, direct_vm):
    review(world, direct_vm, propose(world), findings(**VIOLATED))
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(precedents={"3": [cite(1, "FOLLOWED", "Same omission.")]}, **VIOLATED))
    a, original, d = world.get_appeal(aid), world.get_constitutional_review(rid), world.get_appellate_decision(aid)
    cites = world.get_appeal_record(aid)["citations"]
    assert a["precedent_set_hash"] != "" and a["appeal_hash"] == appeal_hash(a)
    ctx = context_hash(a, original)
    fs = world.get_appeal_findings_page(aid, 0, 50)
    assert d["decision_hash"] == decision_hash(ctx, "REPAIRABLE", "AFFIRMED", fs, cites)
    flipped = [dict(c, treatment="DISTINGUISHED") for c in cites]
    assert decision_hash(ctx, "REPAIRABLE", "AFFIRMED", fs, flipped) != d["decision_hash"]
    assert decision_hash(ctx, "REPAIRABLE", "AFFIRMED", fs, []) != d["decision_hash"]


def test_the_dissent_hash_recomputes_independently_and_excludes_prose(world, direct_vm):
    pid, rid = adverse_review(world, direct_vm)
    aid = appeal(world, direct_vm, rid, findings(**VIOLATED))
    alt = findings(s3="VIOLATED", s3_kw=dict(repairable=False, rationale="Not curable."))
    dissent(world, direct_vm, aid, alt)
    x = world.get_reasoned_dissent(aid)
    decision = world.get_appellate_decision(aid)["decision_hash"]
    assert x["decision_hash"] == decision
    assert x["dissent_hash"] == dissent_hash(aid, decision, "INELIGIBLE", x["findings"], ["3"])
    assert x["verdict"] == "INELIGIBLE" and x["disagreeing_section_ids"] == ["3"]
    reworded = [dict(f, rationale="other words") for f in x["findings"]]
    assert dissent_hash(aid, decision, "INELIGIBLE", reworded, ["3"]) == x["dissent_hash"]
    assert dissent_hash(aid, decision, "REPAIRABLE", x["findings"], ["3"]) != x["dissent_hash"]
    assert dissent_hash(aid, decision, "INELIGIBLE", x["findings"], ["2", "3"]) != x["dissent_hash"]
    assert dissent_hash(aid + 1, decision, "INELIGIBLE", x["findings"], ["3"]) != x["dissent_hash"]
    assert dissent_hash(aid, "0x" + "66" * 32, "INELIGIBLE", x["findings"], ["3"]) != x["dissent_hash"]
