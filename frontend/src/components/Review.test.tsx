import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ReviewResultView } from "./Review";
import { decodeFinding, decodeReview, decodeRevision } from "../lib/genlayer/charterGate";

const base = {
  review_id: 1,
  proposal_id: 1,
  requested_by: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b",
  charter_version: 3,
  evidence_count_at_review: 4,
  evidence_set_hash: "0x" + "11".repeat(32),
  review_context_hash: "0x" + "22".repeat(32),
  verdict: "ELIGIBLE",
  finding_count: 2,
  primary_section_id: "",
  created_at: "2026-10-09T10:00:00.5Z",
  review_hash: "0x" + "33".repeat(32),
};
const sections = [
  { section_id: "1", title: "Mission", body: "b", active: true, charter_version: 2, changed_at: "t" },
  { section_id: "2", title: "Transparency", body: "b", active: true, charter_version: 3, changed_at: "t" },
].map(decodeRevision);
const fnd = (section_id: string, finding: string, over: Record<string, unknown> = {}) =>
  decodeFinding({
    section_id,
    finding,
    repairable: false,
    evidence_ids: [],
    missing_fact: finding === "UNCLEAR" ? "conflict_disclosure" : "",
    rationale: "short reason",
    ...over,
  });

const render = (verdict: string, findings: ReturnType<typeof fnd>[], ids = [1, 2, 3, 4]) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <ReviewResultView review={decodeReview({ ...base, verdict })} findings={findings} sections={sections} snapshotIds={ids} />
    </MemoryRouter>,
  );

describe("ReviewResultView", () => {
  it("shows an audit view of an ELIGIBLE review", () => {
    const html = render("ELIGIBLE", [fnd("1", "SATISFIED"), fnd("2", "SATISFIED", { evidence_ids: [1] })]);
    expect(html).toContain("CONSTITUTIONAL REVIEW #001");
    expect(html).toContain("Constitutional verdict");
    expect(html).toContain("ELIGIBLE");
    expect(html).toContain("Constitutional review passed.");
    expect(html).toContain("Governance voting is not implemented in this stage.");
    expect(html).toContain("Version 3");
    expect(html).toContain("4 records");
    expect(html).toContain("0x" + "11".repeat(32)); // evidence-set hash, in full
    expect(html).toContain("0x" + "22".repeat(32));
    expect(html).toContain("0x" + "33".repeat(32));
    expect(html).toContain("§1 Mission");
    expect(html).toContain("§2 Transparency");
    expect(html).toContain('href="/evidence/1"');
    expect(html).toContain("Oct 9, 2026");
  });

  it("says the review is not a hash of any web page and excludes the wording", () => {
    const html = render("ELIGIBLE", [fnd("1", "SATISFIED"), fnd("2", "SATISFIED")]);
    expect(html).toContain("does not commit to the explanatory wording");
    expect(html).toContain("not a hash of any web page");
  });

  it("INELIGIBLE names the violated rule and that it is not repairable", () => {
    const html = render("INELIGIBLE", [fnd("1", "SATISFIED"), fnd("2", "VIOLATED", { evidence_ids: [1] })]);
    expect(html).toContain("INELIGIBLE");
    expect(html).toContain("Violated rule: §2 Transparency");
    expect(html).toContain("NOT REPAIRABLE");
    expect(html).not.toContain("Constitutional review passed");
  });

  it("REPAIRABLE names the failing rule and says repair is not available", () => {
    const html = render("REPAIRABLE", [fnd("1", "SATISFIED"), fnd("2", "VIOLATED", { repairable: true })]);
    expect(html).toContain("Currently failing: §2 Transparency");
    expect(html).toContain("Repair is not available yet");
    expect(html).toContain("this failure looks curable");
    expect(html).not.toContain("<button");
  });

  it("INSUFFICIENT_EVIDENCE shows which fact lacks verified evidence", () => {
    const html = render("INSUFFICIENT_EVIDENCE", [fnd("1", "SATISFIED"), fnd("2", "UNCLEAR", { evidence_ids: [3] })]);
    expect(html).toContain("INSUFFICIENT EVIDENCE");
    expect(html).toContain("Undetermined for lack of VERIFIED evidence: §2 Transparency (conflict_disclosure)");
    expect(html).toContain("Verified evidence is missing for");
  });

  it("offers no repair, appeal or voting action in Stage 3", () => {
    for (const v of ["ELIGIBLE", "INELIGIBLE", "REPAIRABLE", "INSUFFICIENT_EVIDENCE"]) {
      const html = render(v, [fnd("1", "SATISFIED"), fnd("2", v === "ELIGIBLE" ? "SATISFIED" : "VIOLATED")]);
      expect(html).not.toMatch(/<button/i);
      expect(html.toLowerCase()).not.toContain("appeal");
    }
  });

  it("does not confuse the transaction outcome with the verdict", () => {
    const html = render("INELIGIBLE", [fnd("1", "SATISFIED"), fnd("2", "VIOLATED")]);
    expect(html).not.toContain("Finalized");
    expect(html).not.toContain("SUCCESS");
  });
});
