import { describe, expect, it } from "vitest";
import {
  awaitingReview,
  buildLineage,
  diffRevision,
  hasChanges,
  MAX_REPAIR_REVISIONS,
  repairGate,
  repairRejection,
} from "./repair";
import { statusLabel, statusTone } from "./review";
import { describeContractError } from "./genlayer/tx";
import {
  decodeEffectiveProposal,
  decodeProposalRevision,
  decodeRepairTarget,
  decodeReview,
  LIMITS,
} from "./genlayer/charterGate";

const revision = {
  revision_id: 1n,
  proposal_id: 1n,
  revision_number: 2n,
  parent_revision_id: 0n,
  source_review_id: 1n,
  proposer: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b",
  title: "Atlas RPC Gateway",
  description: "Same gateway with a budget.",
  requested_action: "Grant 30000 USDC",
  charter_version: 4n,
  addressed_section_ids: ["3"],
  created_at: "2026-10-09T11:00:00Z",
  revision_hash: "0x" + "ab".repeat(32),
};
const review = (id: number, verdict: string) =>
  decodeReview({
    review_id: id,
    proposal_id: 1,
    requested_by: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b",
    charter_version: 4,
    evidence_count_at_review: 1,
    evidence_set_hash: "0x" + "11".repeat(32),
    review_context_hash: "0x" + "22".repeat(32),
    verdict,
    finding_count: 3,
    primary_section_id: "3",
    created_at: "2026-10-09T10:00:00Z",
    review_hash: "0x" + "33".repeat(32),
  });
const original = { title: "Atlas RPC Gateway", description: "Original text.", requested_action: "Grant 30000 USDC", created_at: "2026-10-09T09:00:00Z" };

describe("decoders", () => {
  it("decode a revision and convert bigints", () => {
    const r = decodeProposalRevision(revision);
    expect(r).toMatchObject({ revision_id: 1, revision_number: 2, parent_revision_id: 0, source_review_id: 1, charter_version: 4, addressed_section_ids: ["3"] });
    expect(decodeProposalRevision(new Map(Object.entries(revision)))).toEqual(r);
  });
  it("reject malformed revisions, effective proposals and targets", () => {
    expect(() => decodeProposalRevision({ ...revision, addressed_section_ids: [3] })).toThrow(/list of strings/);
    expect(() => decodeProposalRevision({ ...revision, title: 5 })).toThrow(/not a string/);
    expect(() => decodeEffectiveProposal({ proposal_id: 1 })).toThrow();
    expect(() => decodeRepairTarget({ section_id: "3", title: "Budget", body: "b", rationale: "r", evidence_ids: ["1"] })).toThrow(/list of integers/);
    expect(decodeRepairTarget({ section_id: "3", title: "Budget", body: "b", rationale: "r", evidence_ids: [2n] }).evidence_ids).toEqual([2]);
  });
  it("mirror the contract's revision limit", () => {
    expect(LIMITS.repairRevisions).toBe(MAX_REPAIR_REVISIONS);
  });
});

describe("diffRevision", () => {
  const parent = { title: "A", description: "one two", requested_action: "act" };
  it("reports changed fields only and treats whitespace as unchanged, like the contract", () => {
    const d = diffRevision(parent, { title: "A", description: "one   two\n", requested_action: "act 2" });
    expect(d.map((x) => [x.field, x.changed])).toEqual([["title", false], ["description", false], ["requested_action", true]]);
    expect(hasChanges(d)).toBe(true);
    expect(hasChanges(diffRevision(parent, { ...parent, description: " one two " }))).toBe(false);
  });
});

describe("repairRejection", () => {
  it("maps the contract's deterministic rejection codes", () => {
    expect(repairRejection("EXPECTED:REPAIR_REJECTED:PURPOSE_CHANGED")?.reason).toContain("fundamental purpose changed");
    expect(repairRejection("EXPECTED:REPAIR_REJECTED:SCOPE_CHANGED")?.code).toBe("SCOPE_CHANGED");
    expect(repairRejection("EXPECTED:REPAIR_REJECTED:NO_TARGET_ADDRESSED")?.reason).toContain("repair targets");
    expect(repairRejection("EXPECTED:NOT_PROPOSER")).toBeNull();
    expect(repairRejection(undefined)).toBeNull();
  });
  it("is not presented as a generic failure", () => {
    expect(describeContractError("EXPECTED:REPAIR_REJECTED:PURPOSE_CHANGED")).toMatch(/Repair rejected/);
    expect(describeContractError("EXPECTED:REPAIR_NOT_ALLOWED")).toMatch(/only a REPAIRABLE proposal/);
  });
});

describe("repairGate", () => {
  const ok = { connection: "ready", isProposer: true, status: "REPAIRABLE", revisionCount: 0, targets: 1 };
  it("allows only the connected proposer of a REPAIRABLE proposal", () => {
    expect(repairGate(ok)).toEqual({ allowed: true, reason: null });
  });
  it.each([
    [{ status: "ELIGIBLE" }, /only a REPAIRABLE proposal/],
    [{ status: "REVISED" }, /only a REPAIRABLE proposal/],
    [{ revisionCount: 5 }, /maximum of 5/],
    [{ targets: 0 }, /no repair targets/],
    [{ connection: "disconnected" }, /Connect your wallet/],
    [{ connection: "wrong_network" }, /StudioNet/],
    [{ isProposer: false }, /Only the proposer/],
  ])("refuses %o", (over, reason) => {
    const g = repairGate({ ...ok, ...over });
    expect(g.allowed).toBe(false);
    expect(g.reason).toMatch(reason);
  });
});

describe("lineage", () => {
  it("pairs each revision with the review that judged it and keeps both verdicts", () => {
    const entries = buildLineage(original, [decodeProposalRevision(revision)], [review(1, "REPAIRABLE"), review(2, "ELIGIBLE")]);
    expect(entries.map((e) => [e.revisionNumber, e.review?.verdict])).toEqual([[1, "REPAIRABLE"], [2, "ELIGIBLE"]]);
    expect(entries[0].revisionId).toBe(0);
    expect(entries[1].addressed).toEqual(["3"]);
    expect(awaitingReview(entries)).toBeNull();
  });
  it("shows an accepted revision awaiting review", () => {
    const entries = buildLineage(original, [decodeProposalRevision(revision)], [review(1, "REPAIRABLE")]);
    expect(awaitingReview(entries)?.revisionNumber).toBe(2);
  });
  it("never reports the original as awaiting review", () => {
    expect(awaitingReview(buildLineage(original, [], []))).toBeNull();
  });
});

describe("status presentation", () => {
  it("shows REVISED as awaiting review and not as a verdict", () => {
    expect(statusLabel("REVISED")).toBe("REVISED · AWAITING REVIEW");
    expect(statusTone("REVISED")).toBe("precedent");
  });
});
