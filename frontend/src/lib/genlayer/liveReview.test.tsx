import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/live-review.json";
import { decodeFinding, decodeReview, decodeRevision } from "./charterGate";
import { ReviewResultView } from "../../components/Review";
import { VERDICT_INFO } from "../review";

/** Real data read from StudioNet (Stage 3 verification deployment), decoded and rendered exactly as the app does. */
const sections = fixture.charterV4.map(decodeRevision);
const render = (entry: (typeof fixture.reviews)[number]) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <ReviewResultView
        review={decodeReview(entry.review)}
        findings={entry.findings.map(decodeFinding)}
        sections={sections}
        snapshotIds={entry.snapshot}
      />
    </MemoryRouter>,
  );

describe("live StudioNet reviews", () => {
  it("decode: all four verdicts are present and every finding decodes", () => {
    const verdicts = fixture.reviews.map((e) => decodeReview(e.review).verdict).sort();
    expect(verdicts).toEqual(["ELIGIBLE", "INELIGIBLE", "INSUFFICIENT_EVIDENCE", "REPAIRABLE"]);
    for (const e of fixture.reviews) {
      const findings = e.findings.map(decodeFinding);
      expect(findings.map((f) => f.section_id)).toEqual(["s1", "s2", "s3"]); // one finding per active section, in charter order
      expect(decodeReview(e.review).finding_count).toBe(findings.length);
    }
  });

  it("render: each verdict shows its meaning, the historical charter version and the full hashes", () => {
    for (const e of fixture.reviews) {
      const r = decodeReview(e.review);
      const html = render(e);
      expect(html).toContain(VERDICT_INFO[r.verdict].headline);
      expect(html).toContain("Version 4"); // the charter in force at submission, although the current charter is v5
      expect(html).toContain(r.evidence_set_hash);
      expect(html).toContain(r.review_context_hash);
      expect(html).toContain(r.review_hash);
      // an adjudication result is never presented as a failed or reverted transaction
      expect(html.toLowerCase()).not.toMatch(/revert|rolled back|failed/);
    }
  });

  it("render: the ineligible, repairable and insufficient-evidence results name the rule", () => {
    const by = (v: string) => fixture.reviews.find((e) => e.review.verdict === v)!;
    expect(render(by("INELIGIBLE"))).toContain("Violated rule: §s1 Mission");
    expect(render(by("REPAIRABLE"))).toContain("Currently failing: §s3 Budget");
    expect(render(by("INSUFFICIENT_EVIDENCE"))).toContain("Undetermined for lack of VERIFIED evidence: §s2 Transparency");
  });

  it("the eligible review cites only the relevant evidence, not the unrelated verified record", () => {
    const eligible = fixture.reviews.find((e) => e.review.verdict === "ELIGIBLE")!;
    expect(eligible.snapshot).toEqual([1, 2]);
    expect(eligible.findings.flatMap((f) => f.evidence_ids)).toEqual([1]);
  });
});
