import { describe, expect, it } from "vitest";
import { ADVISORY_NOTE, describeRule, hasPrecedent, NO_PRECEDENT, precedentBySection, TREATMENT_INFO } from "./precedent";
import { decodePrecedentCase, decodeReviewPrecedents, LIMITS } from "./genlayer/charterGate";

const hash = (n: string) => "0x" + n.repeat(32);
const raw = {
  review_id: 2n,
  precedent_set_hash: hash("ab"),
  candidates: [
    { section_id: "1", rule: "1@2", precedent_review_id: 1n, precedent_review_hash: hash("11") },
    { section_id: "3", rule: "3@4", precedent_review_id: 1n, precedent_review_hash: hash("11") },
  ],
  citations: [{ section_id: "3", precedent_review_id: 1n, treatment: "DISTINGUISHED", reason: "The current proposal itemizes its budget." }],
};

describe("decodeReviewPrecedents", () => {
  it("decodes the snapshot and citations and converts bigints", () => {
    const p = decodeReviewPrecedents(raw);
    expect(p.review_id).toBe(2);
    expect(p.candidates.map((c) => [c.section_id, c.rule, c.precedent_review_id])).toEqual([["1", "1@2", 1], ["3", "3@4", 1]]);
    expect(p.citations[0]).toMatchObject({ section_id: "3", precedent_review_id: 1, treatment: "DISTINGUISHED" });
    expect(decodeReviewPrecedents(new Map(Object.entries(raw)))).toEqual(p);
  });
  it("rejects an unknown treatment, a missing list and a non-string hash", () => {
    expect(() => decodeReviewPrecedents({ ...raw, citations: [{ ...raw.citations[0], treatment: "OVERRULED" }] })).toThrow(/unknown value/);
    expect(() => decodeReviewPrecedents({ ...raw, candidates: "none" })).toThrow(/not a list/);
    expect(() => decodeReviewPrecedents({ ...raw, precedent_set_hash: 5 })).toThrow(/not a string/);
  });
  it("accepts a review with no precedent at all", () => {
    const p = decodeReviewPrecedents({ review_id: 1, precedent_set_hash: "", candidates: [], citations: [] });
    expect(hasPrecedent(p)).toBe(false);
  });
  it("rejects a malformed prior case", () => {
    expect(() => decodePrecedentCase({ review: {}, finding: {}, evidence: [] })).toThrow();
  });
  it("mirrors the contract bound it displays", () => {
    expect(LIMITS.reviewSections * 2).toBe(24); // at most two prior rulings per section
  });
});

describe("precedent presentation", () => {
  it("groups by section in review order and keeps sections with no prior ruling", () => {
    const groups = precedentBySection(decodeReviewPrecedents(raw), ["1", "2", "3"]);
    expect(groups.map((g) => [g.sectionId, g.candidates.length, g.citations.length])).toEqual([["1", 1, 0], ["2", 0, 0], ["3", 1, 1]]);
    expect(groups[1].rule).toBe("");
  });
  it("describes the exact rule identity", () => {
    expect(describeRule("s3@4")).toBe("§s3 · revision 4");
    expect(describeRule("odd")).toBe("odd");
  });
  it("says precedent is advisory and never calls it binding, controlling or law", () => {
    const text = [ADVISORY_NOTE, NO_PRECEDENT, ...Object.values(TREATMENT_INFO).map((t) => t.explain)].join(" ");
    expect(ADVISORY_NOTE).toBe("Prior rulings guide consistency but do not override the charter or current evidence.");
    expect(NO_PRECEDENT).toBe("No prior rulings available for this rule.");
    expect(text.toLowerCase()).not.toMatch(/binding|controlling|\blaw\b|overrule/);
  });
  it("defines exactly the two treatments", () => {
    expect(Object.keys(TREATMENT_INFO).sort()).toEqual(["DISTINGUISHED", "FOLLOWED"]);
  });
});
