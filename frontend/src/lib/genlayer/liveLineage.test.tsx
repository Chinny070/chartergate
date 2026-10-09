import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/live-lineage.json";
import { decodeEffectiveProposal, decodeProposalRevision, decodeReview, decodeRevision } from "./charterGate";
import { RevisionTimeline } from "../../components/Repair";
import { awaitingReview, buildLineage } from "../repair";

/** Real data read from StudioNet (Stage 4 verification deployment): proposal 3, an original and two repairs. */
const revisions = fixture.revisions.map(decodeProposalRevision);
const reviews = fixture.reviews.map((e) => decodeReview(e.review));
const original = { ...fixture.original, created_at: fixture.original.created_at };
const entries = buildLineage(original, revisions, reviews);

describe("live StudioNet lineage", () => {
  it("decodes the revisions with the lineage links the contract stored", () => {
    expect(revisions.map((r) => [r.revision_number, r.parent_revision_id, r.source_review_id, r.charter_version, r.addressed_section_ids])).toEqual([
      [2, 0, 3, 5, ["s3"]],
      [3, 2, 5, 5, ["s4"]],
    ]);
    expect(decodeEffectiveProposal(fixture.effective)).toMatchObject({ revision_number: 3, status: "ELIGIBLE" });
  });

  it("pairs each revision with the review that judged it, in lineage order", () => {
    expect(fixture.history).toEqual([3, 5, 6]);
    expect(entries.map((e) => [e.revisionNumber, e.review?.review_id, e.review?.verdict])).toEqual([
      [1, 3, "REPAIRABLE"],
      [2, 5, "REPAIRABLE"],
      [3, 6, "ELIGIBLE"],
    ]);
    expect(awaitingReview(entries)).toBeNull();
    // every review of the lineage applied the charter the proposal was submitted under
    expect(new Set(reviews.map((r) => r.charter_version))).toEqual(new Set([5]));
  });

  it("renders the timeline with all three verdicts and nothing replaced", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <RevisionTimeline entries={entries} sections={fixture.charterV5.map(decodeRevision)} />
      </MemoryRouter>,
    );
    expect(html).toContain("REVISION 1");
    expect(html).toContain("REVISION 3");
    expect(html).toContain("Review: REPAIRABLE");
    expect(html).toContain("Review: ELIGIBLE");
    expect(html).toContain("Review #005 judged revision 2, under charter v5.");
    expect(html.toLowerCase()).not.toContain("replaced");
  });

  it("each review's evidence snapshot is its own (the partial and full repair share evidence #2)", () => {
    expect(fixture.reviews.map((e) => e.snapshot)).toEqual([[2], [2], [2]]);
  });
});
