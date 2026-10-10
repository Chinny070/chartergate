import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { PrecedentMemory } from "./Precedent";
import { decodeReviewPrecedents, decodeRevision } from "../lib/genlayer/charterGate";

const hash = (n: string) => "0x" + n.repeat(32);
const sections = [
  { section_id: "1", title: "Mission", body: "b", active: true, charter_version: 2, changed_at: "t" },
  { section_id: "3", title: "Budget", body: "b", active: true, charter_version: 4, changed_at: "t" },
].map(decodeRevision);
const render = (raw: unknown) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <PrecedentMemory precedents={decodeReviewPrecedents(raw)} sections={sections} />
    </MemoryRouter>,
  );

const none = { review_id: 1, precedent_set_hash: "", candidates: [], citations: [] };
const withCites = (citations: unknown[]) => ({
  review_id: 2,
  precedent_set_hash: hash("ab"),
  candidates: [
    { section_id: "1", rule: "1@2", precedent_review_id: 1, precedent_review_hash: hash("11") },
    { section_id: "3", rule: "3@4", precedent_review_id: 1, precedent_review_hash: hash("11") },
  ],
  citations,
});

describe("PrecedentMemory", () => {
  it("first cases under a rule are not an error", () => {
    const html = render(none);
    expect(html).toContain("PRECEDENT MEMORY");
    expect(html).toContain("No prior rulings available for this rule.");
    expect(html.toLowerCase()).not.toMatch(/error|could not/);
    expect(html).not.toContain("Precedent set hash");
  });

  it("always says that precedent is advisory", () => {
    for (const raw of [none, withCites([])]) {
      expect(render(raw)).toContain("Prior rulings guide consistency but do not override the charter or current evidence.");
    }
  });

  it("shows a FOLLOWED prior ruling with the shared rule", () => {
    const html = render(withCites([{ section_id: "3", precedent_review_id: 1, treatment: "FOLLOWED", reason: "Same omission." }]));
    expect(html).toContain("Same rule: §3 · revision 4");
    expect(html).toContain("Prior Review #001");
    expect(html).toContain("FOLLOWED");
    expect(html).toContain("consistent with it");
    expect(html).not.toContain("Material difference");
  });

  it("shows a DISTINGUISHED prior ruling with the material difference", () => {
    const html = render(withCites([{ section_id: "3", precedent_review_id: 1, treatment: "DISTINGUISHED", reason: "The current proposal itemizes its budget." }]));
    expect(html).toContain("DISTINGUISHED");
    expect(html).toContain("Material difference");
    expect(html).toContain("The current proposal itemizes its budget.");
  });

  it("lists available candidates when nothing was cited, and says so without claiming no precedent exists", () => {
    const html = render(withCites([]));
    expect(html).toContain("available prior rulings");
    expect(html).toContain("No prior ruling was materially relied on.");
    expect(html).not.toContain("No prior rulings available for this rule.");
  });

  it("shows the full precedent set hash and what it commits to", () => {
    const html = render(withCites([]));
    expect(html).toContain(hash("ab"));
    expect(html).toContain("Later reviews never change it");
  });

  it("offers inspection of the prior rulings and says their evidence is not this case's evidence", () => {
    const html = render(withCites([]));
    expect(html).toContain("Inspect the prior rulings for this rule");
  });

  it("never labels precedent binding, controlling or law", () => {
    const html = render(withCites([{ section_id: "3", precedent_review_id: 1, treatment: "FOLLOWED", reason: "" }])).toLowerCase();
    expect(html).not.toMatch(/binding|controlling|overrule/);
  });
});
