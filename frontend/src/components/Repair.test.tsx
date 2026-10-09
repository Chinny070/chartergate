import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { DiffView, RepairTargets, RevisionTimeline } from "./Repair";
import { buildLineage, diffRevision } from "../lib/repair";
import { decodeProposalRevision, decodeRepairTarget, decodeReview, decodeRevision } from "../lib/genlayer/charterGate";

const r = (html: React.ReactElement) => renderToStaticMarkup(<MemoryRouter>{html}</MemoryRouter>);

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
const revision = decodeProposalRevision({
  revision_id: 1,
  proposal_id: 1,
  revision_number: 2,
  parent_revision_id: 0,
  source_review_id: 1,
  proposer: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b",
  title: "Atlas RPC Gateway",
  description: "Same gateway with a budget.",
  requested_action: "Grant 30000 USDC",
  charter_version: 4,
  addressed_section_ids: ["3"],
  created_at: "2026-10-09T11:00:00Z",
  revision_hash: "0x" + "ab".repeat(32),
});
const original = { title: "Atlas RPC Gateway", description: "Original text.", requested_action: "Grant 30000 USDC", created_at: "2026-10-09T09:00:00Z" };
const sections = [decodeRevision({ section_id: "3", title: "Budget", body: "b", active: true, charter_version: 4, changed_at: "t" })];

describe("DiffView", () => {
  it("marks changed fields with before and after, and unchanged ones without text", () => {
    const html = r(<DiffView diffs={diffRevision({ title: "T", description: "old text", requested_action: "A" }, { title: "T", description: "new text", requested_action: "A" })} />);
    expect(html).toContain("CHANGED");
    expect(html).toContain("old text");
    expect(html).toContain("new text");
    expect(html.match(/UNCHANGED/g)?.length).toBe(2);
  });
});

describe("RepairTargets", () => {
  it("shows the repair required, the governing charter version, the rule and the stored rationale", () => {
    const t = decodeRepairTarget({ section_id: "3", title: "Budget", body: "Every proposal needs a budget breakdown.", rationale: "No budget breakdown.", evidence_ids: [1] });
    const html = r(<RepairTargets targets={[t]} charterVersion={4} />);
    expect(html).toContain("REPAIR REQUIRED");
    expect(html).toContain("charter v4 governs every revision");
    expect(html).toContain("§3 Budget");
    expect(html).toContain("VIOLATED · REPAIRABLE");
    expect(html).toContain("No budget breakdown.");
    expect(html).toContain("Every proposal needs a budget breakdown.");
    expect(html).toContain('href="/evidence/1"');
  });
});

describe("RevisionTimeline", () => {
  it("shows every revision with its own verdict and never calls an earlier review replaced", () => {
    const html = r(<RevisionTimeline entries={buildLineage(original, [revision], [review(1, "REPAIRABLE"), review(2, "ELIGIBLE")])} sections={sections} />);
    expect(html).toContain("REVISION 1");
    expect(html).toContain("Original proposal");
    expect(html).toContain("Review: REPAIRABLE");
    expect(html).toContain("REVISION 2");
    expect(html).toContain("Review: ELIGIBLE");
    expect(html).toContain("Review #002 judged revision 2, under charter v4.");
    expect(html.toLowerCase()).not.toContain("replaced");
  });
  it("shows an accepted revision as awaiting review", () => {
    const html = r(<RevisionTimeline entries={buildLineage(original, [revision], [review(1, "REPAIRABLE")])} sections={sections} />);
    expect(html).toContain("AWAITING REVIEW");
  });
});
