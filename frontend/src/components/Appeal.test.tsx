import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AppellateHistory, DissentView } from "./Appeal";
import { decodeAppealRecord, decodeReasonedDissent, decodeRevision } from "../lib/genlayer/charterGate";

const hash = (n: string) => "0x" + n.repeat(32);
const sections = [
  { section_id: "1", title: "Mission", body: "b", active: true, charter_version: 2, changed_at: "t" },
  { section_id: "3", title: "Budget", body: "b", active: true, charter_version: 4, changed_at: "t" },
].map(decodeRevision);

const finding = (section_id: string, kind: string, repairable = false) => ({
  section_id,
  finding: kind,
  repairable,
  evidence_ids: [],
  missing_fact: "",
  rationale: `rationale ${section_id}`,
});
const review = (verdict: string) => ({
  review_id: 1,
  proposal_id: 1,
  requested_by: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b",
  charter_version: 4,
  evidence_count_at_review: 0,
  evidence_set_hash: hash("e1"),
  review_context_hash: hash("c1"),
  verdict,
  finding_count: 2,
  primary_section_id: "3",
  created_at: "2026-10-10T12:00:00Z",
  review_hash: hash("a1"),
});

function record(kind: string, original: string, appellate: string) {
  const violated = [finding("1", "SATISFIED"), finding("3", "VIOLATED", true)];
  const ok = [finding("1", "SATISFIED"), finding("3", "SATISFIED")];
  return {
    appeal: {
      appeal_id: 1,
      review_id: 1,
      proposal_id: 1,
      revision_id: 0,
      appellant: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b",
      ground: "CHARTER_MISINTERPRETATION",
      statement: "The budget rule was misread.",
      original_verdict: original,
      original_review_hash: hash("a1"),
      charter_version: 4,
      evidence_count: 0,
      evidence_set_hash: hash("e1"),
      precedent_set_hash: "",
      created_at: "2026-10-10T13:00:00Z",
      appeal_hash: hash("b1"),
    },
    review: review(original),
    original_findings: violated,
    decision: {
      appeal_id: 1,
      review_id: 1,
      verdict: appellate,
      decision_kind: kind,
      finding_count: 2,
      appeal_context_hash: hash("d1"),
      decision_hash: hash("d2"),
      created_at: "2026-10-10T13:00:00Z",
    },
    findings: kind === "REVERSED" ? ok : violated,
    citations: [],
    precedent_candidates: [],
    evidence_ids: [],
    dissent: null,
  };
}

const render = (raw: unknown, effective: string) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <AppellateHistory record={decodeAppealRecord(raw)} effectiveVerdict={effective} sections={sections} />
    </MemoryRouter>,
  );

describe("AppellateHistory", () => {
  it("keeps the original review, the appeal and the appellate decision as three separate things", () => {
    const html = render(record("REVERSED", "REPAIRABLE", "ELIGIBLE"), "ELIGIBLE");
    expect(html).toContain("Original review #001");
    expect(html).toContain(">Appeal<");
    expect(html).toContain("Appellate decision");
    expect(html).toContain("The original judgment is preserved exactly as it was issued.");
  });

  it("shows the original, appellate and effective judgments of a reversal side by side", () => {
    const html = render(record("REVERSED", "INELIGIBLE", "ELIGIBLE"), "ELIGIBLE");
    expect(html).toContain("Original judgment");
    expect(html).toContain("Appellate judgment");
    expect(html).toContain("Effective constitutional verdict");
    expect(html).toContain("INELIGIBLE");
    expect(html).toContain("REVERSED");
    expect(html).toContain("An appeal is a genuine re-judgment");
  });

  it("says what each disposition means and what happens to precedent", () => {
    expect(render(record("AFFIRMED", "REPAIRABLE", "REPAIRABLE"), "REPAIRABLE")).toContain("stays eligible as automatic precedent");
    for (const kind of ["MODIFIED", "REVERSED"]) {
      const html = render(record(kind, "REPAIRABLE", kind === "REVERSED" ? "ELIGIBLE" : "REPAIRABLE"), "ELIGIBLE");
      expect(html).toContain("no longer appears as automatic precedent");
      expect(html).toContain("not yet automatic precedent");
    }
  });

  it("states that the appeal statement is an argument and not evidence, and describes the closed record", () => {
    const html = render(record("AFFIRMED", "REPAIRABLE", "REPAIRABLE"), "REPAIRABLE");
    expect(html).toContain("Your statement is an argument, not evidence.");
    expect(html).toContain("Later evidence, later charter amendments and later precedents never enter it");
  });

  it("lists the sections an appeal changed", () => {
    const html = render(record("REVERSED", "REPAIRABLE", "ELIGIBLE"), "ELIGIBLE");
    expect(html).toContain("Sections changed by the appeal");
    expect(html).toContain("§3");
  });
});

const dissent = {
  dissent_id: 1,
  appeal_id: 1,
  decision_hash: hash("d2"),
  verdict: "INELIGIBLE",
  disagreeing_section_ids: ["3"],
  finding_count: 2,
  created_at: "2026-10-10T14:00:00Z",
  dissent_hash: hash("f1"),
  findings: [finding("1", "SATISFIED"), finding("3", "VIOLATED", false)],
};

describe("DissentView", () => {
  const html = renderToStaticMarkup(
    <MemoryRouter>
      <DissentView dissent={decodeReasonedDissent(dissent)} sections={sections} />
    </MemoryRouter>,
  );

  it("is labelled truthfully as a non-controlling, AI-generated alternative", () => {
    expect(html).toContain("REASONED DISSENT");
    expect(html).toContain("NON-CONTROLLING ALTERNATIVE INTERPRETATION");
    expect(html).toContain("AI-generated");
    expect(html).toContain("does not change the effective judgment");
    expect(html).toContain("Alternative verdict (does not control)");
  });

  it("never claims to be a validator vote, evidence, precedent, binding or law", () => {
    expect(html).toContain("It is not a validator vote or minority");
    const lower = html.toLowerCase();
    expect(lower).not.toContain("validator minority opinion");
    expect(lower).not.toMatch(/\b(binding|controlling law)\b/);
  });

  it("shows the sections where it disagrees and its hash", () => {
    expect(html).toContain("§3");
    expect(html).toContain(hash("f1"));
  });
});
