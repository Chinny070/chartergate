import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { EvidenceCard, EvidenceNotes } from "./Evidence";
import { decodeEvidence, type EvidenceRecord } from "../lib/genlayer/charterGate";

const base = {
  evidence_id: 4,
  proposal_id: 1,
  submitter: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b",
  source_url: "https://atlas.example.org/tokenomics",
  source_kind: "DYNAMIC_WEB",
  retrieval_method: "RENDER_TEXT",
  claim: "Atlas team token allocation is 46%.",
  status: "VERIFIED",
  status_reason: "SUPPORTED",
  normalized_fact: "team_token_allocation",
  normalized_value: "46%",
  excerpt: "Team: 46%",
  content_hash: "0x" + "ab".repeat(32),
  retrieved_at: "2026-10-08T21:30:00.123456Z",
  created_at: "2026-10-08T21:30:00.123456Z",
  related_section_id: "2",
  related_revision_version: 3,
};

const render = (record: EvidenceRecord, detail = false) =>
  renderToStaticMarkup(
    <MemoryRouter>
      <EvidenceCard record={record} detail={detail} />
    </MemoryRouter>,
  );
const rec = (over: Record<string, unknown> = {}) => decodeEvidence({ ...base, ...over });

describe("EvidenceCard", () => {
  it("shows the provenance a reviewer needs", () => {
    const html = render(rec());
    expect(html).toContain("EVIDENCE #004");
    expect(html).toContain("VERIFIED");
    expect(html).toContain("JAVASCRIPT RENDER");
    expect(html).toContain("atlas.example.org/tokenomics");
    expect(html).toContain("Atlas team token allocation is 46%.");
    expect(html).toContain("team_token_allocation = 46%");
    expect(html).toContain("Team: 46%");
    expect(html).toContain("§2");
    expect(html).toContain("charter v3");
    expect(html).toContain("2026-10-08T21:30:00.123456Z"); // canonical protocol timestamp is shown
    expect(html).toContain("Oct 8, 2026"); // alongside the human-readable form
  });

  it("never reduces a render to 'URL checked'", () => {
    expect(render(rec())).toContain("JAVASCRIPT RENDER");
    expect(render(rec({ source_kind: "STATIC_WEB", retrieval_method: "GET" }))).toContain("HTTP GET · STATIC PAGE");
    expect(render(rec({ source_kind: "API", retrieval_method: "GET" }))).toContain("HTTP GET · JSON API");
  });

  it("labels an unverified observation as what the source says, not a verified fact", () => {
    const html = render(rec({ status: "UNVERIFIABLE", status_reason: "VALUE_NOT_IN_CLAIM", normalized_value: "42%", excerpt: "Team: 42%" }));
    expect(html).toContain("UNVERIFIABLE");
    expect(html).toContain("What the source says");
    expect(html).not.toContain("Verified fact");
    expect(html).toContain("team_token_allocation = 42%");
  });

  it("shows failures without inventing a fact", () => {
    const html = render(rec({ status: "SOURCE_UNAVAILABLE", status_reason: "HTTP_404", normalized_value: "", excerpt: "" }));
    expect(html).toContain("SOURCE UNAVAILABLE");
    expect(html).toContain("The server answered HTTP 404.");
    expect(html).toContain("Fact checked");
    expect(html).toContain("team_token_allocation: nothing was recorded from this source.");  // the asked fact is kept
    expect(html).not.toContain("Verified fact");
    expect(html).not.toContain("<blockquote");
  });

  it("handles a record with no charter relationship", () => {
    expect(render(rec({ related_section_id: "", related_revision_version: 0 }))).toContain("None");
  });

  it("detail view adds the full URL, hash, submitter and proposal link", () => {
    const html = render(rec(), true);
    expect(html).toContain("https://atlas.example.org/tokenomics");
    expect(html).toContain(base.content_hash);
    expect(html).toContain(base.submitter);
    expect(html).toContain("/proposals/1");
  });

  it("only links the source when it is http(s)", () => {
    expect(render(rec())).toContain('href="https://atlas.example.org/tokenomics"');
    expect(render(rec({ source_url: "javascript:alert(1)" }))).not.toContain("href=\"javascript:");
  });

  it("escapes hostile text from a page or a claim", () => {
    const html = render(rec({ claim: "<script>alert(1)</script>", excerpt: "<img src=x onerror=alert(1)>" }));
    expect(html).not.toContain("<script>alert(1)</script>");
    expect(html).not.toContain("<img src=x");
    expect(html).toContain("&lt;script&gt;");
  });

  it("uses no constitutional verdict words anywhere", () => {
    for (const status of ["VERIFIED", "UNVERIFIABLE", "SOURCE_UNAVAILABLE", "INVALID_SOURCE"]) {
      const html = render(rec({ status }), true);
      expect(html, status).not.toMatch(/INELIGIBLE|ELIGIBLE|REPAIRABLE|APPROVED|REJECTED/);
    }
  });
});

describe("wording that must match what is stored", () => {
  it("does not promise a value 'below' when nothing was recorded", () => {
    const none = render(rec({ status: "UNVERIFIABLE", status_reason: "NOT_SUPPORTED", normalized_value: "", excerpt: "" }));
    expect(none).toContain("Nothing about this fact was recorded.");
    expect(none).not.toContain("shown above");
    const some = render(rec({ status: "UNVERIFIABLE", status_reason: "NOT_SUPPORTED", normalized_value: "£51.77", excerpt: "Price (excl. tax) £51.77" }));
    expect(some).toContain("What the source does say about this fact is shown above.");
  });

  it("does not double the quotation marks when the page's own excerpt already begins with one", () => {
    const quoted = render(rec({ excerpt: "“The world as we have created it” by Albert Einstein" }));
    expect(quoted).not.toContain("““");
    expect(quoted).toContain("“The world as we have created it");
    expect(render(rec({ excerpt: "Team: 46%" }))).toContain("“Team: 46%”");
  });
});

describe("EvidenceNotes", () => {
  const html = renderToStaticMarkup(<EvidenceNotes />);
  it("states exactly what the hash is not", () => {
    expect(html).toContain("hash of the normalised evidence");
    expect(html).toContain("the submitted claim");  // Stage 2.1 put the claim into the hash
    expect(html).toContain("not</strong> a hash of the web page");
    expect(html).toContain("page itself is not archived");
  });
  it("says the time is protocol time and that this is not a ruling", () => {
    expect(html).toContain("protocol time");
    expect(html).toContain("not a ruling");
  });
});
