import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { createElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { EvidenceCard } from "../../components/Evidence";
import { canonFactKey, checkFactKey } from "../evidence";
import { decodeDaoMetadata, decodeEvidence } from "./charterGate";

/**
 * Fixture: REAL results read from the Stage 2 verification deployment on StudioNet through genlayer-js 1.1.8
 * (not mocks). It proves the frontend decoders accept exactly what the live network returns.
 */
const path = fileURLToPath(new URL("./__fixtures__/live-evidence.json", import.meta.url));
const live = JSON.parse(readFileSync(path, "utf-8")) as Record<string, unknown> & { records: Record<string, unknown>[] };

describe("the frontend decoders accept real StudioNet data", () => {
  it("decodes the DAO metadata, including evidence_count", () => {
    const m = decodeDaoMetadata(live.get_dao_metadata);
    expect(m.evidence_count).toBe(8);
    expect(m.charter_version).toBe(3);
    expect(m.proposal_count).toBe(1);
  });

  it("decodes all 8 live evidence records, from every read method", () => {
    const records = live.records.map(decodeEvidence);
    expect(records.map((r) => r.evidence_id)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    expect((live.get_evidence_page as unknown[]).map(decodeEvidence)).toEqual(records);
    expect((live.get_proposal_evidence_page as unknown[]).map(decodeEvidence)).toEqual(records);
    expect(live.get_proposal_evidence_ids_page).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
    expect(live.get_proposal_evidence_count).toBe(8);
    expect(live.get_evidence_count).toBe(8);
  });

  it("integers decode as JS numbers, hashes as 0x + 64 hex, timestamps as parseable ISO strings", () => {
    for (const raw of live.records) {
      const r = decodeEvidence(raw);
      expect(typeof r.evidence_id).toBe("number");
      expect(typeof r.related_revision_version).toBe("number");
      expect(r.content_hash).toMatch(/^0x[0-9a-f]{64}$/);
      expect(Number.isFinite(new Date(r.retrieved_at).getTime())).toBe(true);
      expect(r.retrieved_at).toBe(r.created_at);
    }
  });

  it("the real statuses and provenance are what the live smoke tests produced", () => {
    const by = Object.fromEntries(live.records.map((r) => [(r as { evidence_id: number }).evidence_id, decodeEvidence(r)]));
    expect(by[1]).toMatchObject({ status: "VERIFIED", retrieval_method: "GET", source_kind: "STATIC_WEB", normalized_fact: "copies_available" });
    expect(by[2]).toMatchObject({ status: "UNVERIFIABLE", status_reason: "NOT_SUPPORTED", normalized_value: "£51.77" });
    expect(by[3]).toMatchObject({ status: "VERIFIED", retrieval_method: "RENDER_TEXT", source_kind: "DYNAMIC_WEB", normalized_fact: "quote_author" });
    expect(by[4]).toMatchObject({ status: "UNVERIFIABLE", retrieval_method: "GET", normalized_value: "" });
    expect(by[5]).toMatchObject({ status: "SOURCE_UNAVAILABLE", status_reason: "FETCH_FAILED", retrieval_method: "RENDER_TEXT" });
    expect(by[6]).toMatchObject({ status: "SOURCE_UNAVAILABLE", status_reason: "HTTP_404" });
    expect(by[7]).toMatchObject({ status: "UNVERIFIABLE", normalized_fact: "number_of_pages", normalized_value: "" });
    expect(by[8]).toMatchObject({ status: "VERIFIED", normalized_fact: "number_of_reviews", normalized_value: "0" });
  });

  it("every live fact key is already in the contract's canonical form (the UI preview agrees with the chain)", () => {
    for (const raw of live.records) {
      const r = decodeEvidence(raw);
      expect(checkFactKey(r.normalized_fact)).toBeNull();
      expect(canonFactKey(r.normalized_fact)).toBe(r.normalized_fact);
    }
  });

  it("renders every real record, showing how it was retrieved and never mixing evidence status with transaction success", () => {
    for (const raw of live.records) {
      const r = decodeEvidence(raw);
      const html = renderToStaticMarkup(createElement(MemoryRouter, null, createElement(EvidenceCard, { record: r, detail: true })));
      expect(html).toContain(r.status === "SOURCE_UNAVAILABLE" ? "SOURCE UNAVAILABLE" : r.status);
      expect(html).toContain(r.retrieval_method === "RENDER_TEXT" ? "JAVASCRIPT RENDER" : "HTTP GET");
      expect(html).toContain(r.content_hash);
      expect(html).toContain(r.retrieved_at);
      if (r.status !== "VERIFIED") expect(html).not.toContain("Verified fact");
    }
  });
});
