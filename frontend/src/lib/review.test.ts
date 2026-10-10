import { describe, expect, it } from "vitest";
import {
  adverseFindings,
  describeEvidence,
  reviewLabel,
  reviewRequestGate,
  statusLabel,
  statusTone,
  summarizeEvidence,
  VERDICT_INFO,
} from "./review";
import { decodeFinding, decodeReview, REVIEW_VERDICTS } from "./genlayer/charterGate";

const review = {
  review_id: 1n,
  proposal_id: 1n,
  requested_by: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b",
  charter_version: 3n,
  evidence_count_at_review: 4n,
  evidence_set_hash: "0x" + "11".repeat(32),
  review_context_hash: "0x" + "22".repeat(32),
  verdict: "INSUFFICIENT_EVIDENCE",
  finding_count: 2n,
  primary_section_id: "2",
  created_at: "2026-10-09T10:00:00Z",
  review_hash: "0x" + "33".repeat(32),
};
const finding = { section_id: "2", finding: "UNCLEAR", repairable: false, evidence_ids: [3n], missing_fact: "conflict_disclosure", rationale: "x" };

describe("decoders", () => {
  it("decode a review (plain object and Map) and convert bigints", () => {
    const r = decodeReview(review);
    expect(r.review_id).toBe(1);
    expect(r.charter_version).toBe(3);
    expect(r.verdict).toBe("INSUFFICIENT_EVIDENCE");
    expect(decodeReview(new Map(Object.entries(review)))).toEqual(r);
  });

  it("reject an unknown verdict instead of rendering it", () => {
    expect(() => decodeReview({ ...review, verdict: "APPROVED" })).toThrow(/unknown value/);
    expect(() => decodeReview({ ...review, evidence_set_hash: 5 })).toThrow(/not a string/);
  });

  it("decode findings and reject malformed ones", () => {
    expect(decodeFinding(finding)).toMatchObject({ section_id: "2", finding: "UNCLEAR", evidence_ids: [3] });
    expect(() => decodeFinding({ ...finding, finding: "MAYBE" })).toThrow(/unknown value/);
    expect(() => decodeFinding({ ...finding, evidence_ids: ["3"] })).toThrow(/list of integers/);
    expect(() => decodeFinding({ ...finding, repairable: "yes" })).toThrow(/not a boolean/);
  });
});

describe("verdicts", () => {
  it("describe exactly the four contract verdicts", () => {
    expect(Object.keys(VERDICT_INFO).sort()).toEqual([...REVIEW_VERDICTS].sort());
  });

  it("say what is and is not implemented", () => {
    expect(VERDICT_INFO.ELIGIBLE.headline).toBe("Constitutional review passed.");
    expect(VERDICT_INFO.ELIGIBLE.explain).toContain("Governance voting is not implemented in this stage.");
    expect(VERDICT_INFO.REPAIRABLE.explain).toContain("repair it as a new revision");
    expect(VERDICT_INFO.INSUFFICIENT_EVIDENCE.explain).toContain("Missing proof is not a violation");
  });

  it("colour a proposal status by verdict and leave SUBMITTED neutral", () => {
    expect(statusTone("INELIGIBLE")).toBe("ineligible");
    expect(statusTone("ELIGIBLE")).toBe("eligible");
    expect(statusTone("SUBMITTED")).toBe("active");
    expect(statusLabel("INSUFFICIENT_EVIDENCE")).toBe("INSUFFICIENT EVIDENCE");
    expect(statusLabel("SUBMITTED")).toBe("SUBMITTED");
  });

  it("label a review by its id", () => {
    expect(reviewLabel({ review_id: 1 })).toBe("CONSTITUTIONAL REVIEW #001");
  });
});

describe("evidence summary", () => {
  it("counts each status and describes only the present ones", () => {
    const s = summarizeEvidence([{ status: "VERIFIED" }, { status: "VERIFIED" }, { status: "VERIFIED" }, { status: "UNVERIFIABLE" }, { status: "SOURCE_UNAVAILABLE" }]);
    expect(s).toEqual({ total: 5, verified: 3, unverifiable: 1, sourceUnavailable: 1, invalidSource: 0 });
    expect(describeEvidence(s)).toBe("5 records: 3 VERIFIED, 1 UNVERIFIABLE, 1 SOURCE UNAVAILABLE");
    expect(describeEvidence(summarizeEvidence([]))).toBe("No evidence records.");
    expect(describeEvidence(summarizeEvidence([{ status: "INVALID_SOURCE" }]))).toBe("1 record: 1 INVALID SOURCE");
  });
});

describe("who may request a review", () => {
  const ok = { connection: "ready", isProposer: true, hasReview: false, status: "SUBMITTED", activeSections: 2 };
  it("allows only the connected proposer of an unreviewed proposal", () => {
    expect(reviewRequestGate(ok)).toEqual({ allowed: true, reason: null });
  });
  it.each([
    [{ connection: "disconnected" }, /Connect your wallet/],
    [{ connection: "wrong_network" }, /StudioNet/],
    [{ isProposer: false }, /Only the proposer/],
    [{ hasReview: true }, /already has a constitutional review/],
    [{ status: "ELIGIBLE" }, /cannot be reviewed/],
    [{ activeSections: 0 }, /no active sections/],
    [{ activeSections: 13 }, /too many active sections/],
  ])("refuses %o", (over, reason) => {
    const gate = reviewRequestGate({ ...ok, ...over });
    expect(gate.allowed).toBe(false);
    expect(gate.reason).toMatch(reason);
  });
});

describe("adverse findings", () => {
  it("splits violated from unclear in order", () => {
    const f = [
      { section_id: "1", finding: "SATISFIED" },
      { section_id: "2", finding: "VIOLATED" },
      { section_id: "3", finding: "UNCLEAR" },
    ].map((x) => decodeFinding({ ...finding, ...x, missing_fact: x.finding === "UNCLEAR" ? "m" : "" }));
    const { violated, unclear } = adverseFindings(f);
    expect(violated.map((x) => x.section_id)).toEqual(["2"]);
    expect(unclear.map((x) => x.section_id)).toEqual(["3"]);
  });
});
