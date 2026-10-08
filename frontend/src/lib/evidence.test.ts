import { describe, expect, it } from "vitest";
import { decodeDaoMetadata, decodeEvidence } from "./genlayer/charterGate";
import {
  canonFactKey,
  checkFactKey,
  checkSourceUrl,
  describeRetrieval,
  displayHost,
  evidenceLabel,
  reasonText,
  shortHash,
  STATUS_INFO,
} from "./evidence";

/** The same cases as tests/direct/test_evidence_validation.py, so the pre-check cannot drift from the contract. */
const REJECTED: [string, string][] = [
  ["", "SOURCE_URL_EMPTY"],
  ["    ", "SOURCE_URL_EMPTY"],
  ["ftp://example.com/a", "SOURCE_URL_UNSUPPORTED_SCHEME"],
  ["file:///etc/passwd", "SOURCE_URL_UNSUPPORTED_SCHEME"],
  ["javascript:alert(1)", "SOURCE_URL_UNSUPPORTED_SCHEME"],
  ["data:text/html,hello", "SOURCE_URL_UNSUPPORTED_SCHEME"],
  ["//example.com/a", "SOURCE_URL_UNSUPPORTED_SCHEME"],
  ["example.com/a", "SOURCE_URL_UNSUPPORTED_SCHEME"],
  ["httpx://example.com", "SOURCE_URL_UNSUPPORTED_SCHEME"],
  ["https://", "SOURCE_URL_NO_HOST"],
  ["https:///path", "SOURCE_URL_NO_HOST"],
  ["https://user:pw@example.com/", "SOURCE_URL_HAS_CREDENTIALS"],
  ["https://example.com@evil.com/", "SOURCE_URL_HAS_CREDENTIALS"],
  ["https://[::1]/", "SOURCE_URL_IP_LITERAL"],
  ["http://localhost/", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["http://localhost:8080/x", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["http://LOCALHOST./", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["http://127.0.0.1/", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["http://10.0.0.5/admin", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["http://192.168.1.1/", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["http://169.254.169.254/latest/meta-data/", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["http://2130706433/", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["http://0x7f.0.0.1/", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["http://intranet/", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["https://printer.local/", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["https://db.internal/", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["https://app.localhost/", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["https://nas.lan/", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["https://example.com:0/", "SOURCE_URL_BAD_PORT"],
  ["https://example.com:65536/", "SOURCE_URL_BAD_PORT"],
  ["https://example.com:abc/", "SOURCE_URL_BAD_PORT"],
  ["https://example.com:/", "SOURCE_URL_BAD_PORT"],
  ["https://exa mple.com/", "SOURCE_URL_INVALID_CHARS"],
  ["https://example.com/a b", "SOURCE_URL_INVALID_CHARS"],
  ["https://example.com/\\evil", "SOURCE_URL_INVALID_CHARS"],
  ["https://exa\nmple.com/", "SOURCE_URL_INVALID_CHARS"],
  ["https://exa\tmple.com/", "SOURCE_URL_INVALID_CHARS"],
  ["https://ex\u0000ample.com/", "SOURCE_URL_INVALID_CHARS"],
  ["https://exämple.com/", "SOURCE_URL_INVALID_CHARS"],
  ["https://a..example.com/", "SOURCE_URL_INVALID_HOST"],
  ["https://exa_mple.com/", "SOURCE_URL_INVALID_HOST"],
  ["https://example.c/", "SOURCE_URL_HOST_NOT_PUBLIC"],
  ["https://example.com/" + "a".repeat(481), "SOURCE_URL_TOO_LONG"],
];

const ACCEPTED = [
  "https://atlas.example.org/tokenomics",
  "http://atlas.example.org/x?y=1#frag",
  "https://sub.domain.example.co.uk:8443/path/to/page.html",
  "https://xn--bcher-kva.example/",
  "HTTPS://Atlas.Example.ORG/Path",
  "https://example.com",
  "  https://atlas.example.org/padded  ",
];

describe("checkSourceUrl mirrors the contract's URL screening", () => {
  it.each(REJECTED)("rejects %j with %s", (url, code) => {
    expect(checkSourceUrl(url)?.code).toBe(code);
  });
  it.each(ACCEPTED)("accepts %j", (url) => {
    expect(checkSourceUrl(url)).toBeNull();
  });
  it("accepts a URL of exactly 500 characters", () => {
    const url = "https://example.com/" + "a".repeat(480);
    expect(url.length).toBe(500);
    expect(checkSourceUrl(url)).toBeNull();
  });
});

const record = {
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

describe("decodeEvidence", () => {
  it("decodes a record, converting bigint integers", () => {
    const r = decodeEvidence({ ...record, evidence_id: 4n, related_revision_version: 3n });
    expect(r.evidence_id).toBe(4);
    expect(r.related_revision_version).toBe(3);
    expect(r.status).toBe("VERIFIED");
  });
  it("accepts a Map (genlayer-js may return either)", () => {
    expect(decodeEvidence(new Map(Object.entries(record))).normalized_value).toBe("46%");
  });
  it("rejects unknown enum values instead of displaying them", () => {
    expect(() => decodeEvidence({ ...record, status: "ELIGIBLE" })).toThrow(/unknown value/);
    expect(() => decodeEvidence({ ...record, retrieval_method: "SCREENSHOT" })).toThrow(/unknown value/);
    expect(() => decodeEvidence({ ...record, source_kind: "PDF" })).toThrow(/unknown value/);
  });
  it("fails loudly on wrong shapes", () => {
    expect(() => decodeEvidence({ ...record, evidence_id: "4" })).toThrow(/integer/);
    expect(() => decodeEvidence({ ...record, claim: 5 })).toThrow(/string/);
    expect(() => decodeEvidence(null)).toThrow(/object/);
    const { content_hash: _omit, ...missing } = record;
    void _omit;
    expect(() => decodeEvidence(missing)).toThrow();
  });
});

describe("decodeDaoMetadata evidence_count", () => {
  const meta = {
    dao_name: "Atlas DAO",
    dao_description: "d",
    owner: "0xabc",
    charter_version: 4,
    created_at: "x",
    updated_at: "y",
    section_count: 2,
    proposal_count: 1,
  };
  it("is 0 for a pre-Stage-2 contract that has no such field", () => {
    expect(decodeDaoMetadata(meta).evidence_count).toBe(0);
  });
  it("is read when present, and a wrong value still fails loudly", () => {
    expect(decodeDaoMetadata({ ...meta, evidence_count: 7n }).evidence_count).toBe(7);
    expect(() => decodeDaoMetadata({ ...meta, evidence_count: "7" })).toThrow(/integer/);
  });
});

describe("provenance wording", () => {
  it("always says how the source was retrieved", () => {
    expect(describeRetrieval({ source_kind: "DYNAMIC_WEB", retrieval_method: "RENDER_TEXT" }).badge).toBe("JAVASCRIPT RENDER");
    expect(describeRetrieval({ source_kind: "STATIC_WEB", retrieval_method: "GET" }).badge).toBe("HTTP GET · STATIC PAGE");
    expect(describeRetrieval({ source_kind: "API", retrieval_method: "GET" }).badge).toBe("HTTP GET · JSON API");
  });
  it("does not use constitutional verdict words for evidence statuses", () => {
    const words = Object.values(STATUS_INFO).map((s) => s.label + s.explain).join(" ");
    expect(words).not.toMatch(/ELIGIBLE|INELIGIBLE|REPAIRABLE|APPROVED|REJECTED/);
  });
  it("explains reasons, including HTTP codes", () => {
    expect(reasonText("HTTP_404")).toBe("The server answered HTTP 404.");
    expect(reasonText("HTTP_0")).toMatch(/unusable/);
    expect(reasonText("VALUE_NOT_IN_CLAIM")).toMatch(/different value/);
    expect(reasonText("SOMETHING_NEW")).toBe("SOMETHING_NEW");
  });
  it("formats ids, hashes and hosts", () => {
    expect(evidenceLabel(4)).toBe("EVIDENCE #004");
    expect(evidenceLabel(1234)).toBe("EVIDENCE #1234");
    expect(shortHash("0x" + "ab".repeat(32))).toBe("0xabababab…ababab");
    expect(displayHost("https://atlas.example.org/tokenomics/")).toBe("atlas.example.org/tokenomics");
  });
});

/** The same cases as tests/direct/test_evidence_binding.py, so the preview cannot drift from the contract. */
describe("fact keys mirror the contract (one normalisation rule, no aliases)", () => {
  it.each([
    "team_token_allocation",
    "Team_Token_Allocation",
    "  TEAM_TOKEN_ALLOCATION  ",
    "team token allocation",
    "Team Token-Allocation",
    "team-token-allocation",
    "team   token 	 allocation",
  ])("canonicalises %j to team_token_allocation", (given) => {
    expect(canonFactKey(given)).toBe("team_token_allocation");
    expect(checkFactKey(given)).toBeNull();
  });

  it.each(["team_allocation", "team_tokens", "token_allocation_team", "team_token_allocations"])(
    "does not alias %j to team_token_allocation",
    (given) => {
      expect(canonFactKey(given)).toBe(given);
      expect(canonFactKey(given)).not.toBe("team_token_allocation");
    },
  );

  it.each([
    ["", "FACT_KEY_EMPTY"],
    ["   \n ", "FACT_KEY_EMPTY"],
    ["team/allocation", "FACT_KEY_INVALID"],
    ["team:allocation", "FACT_KEY_INVALID"],
    ["team.token.allocation", "FACT_KEY_INVALID"],
    ["équipe", "FACT_KEY_INVALID"],
    ["team%allocation", "FACT_KEY_INVALID"],
    ["___", "FACT_KEY_INVALID"],
    ["---", "FACT_KEY_INVALID"],
    ["a".repeat(65), "FACT_KEY_TOO_LONG"],
  ])("rejects %j with %s", (given, code) => {
    expect(checkFactKey(given)?.code).toBe(code);
  });

  it("accepts a 64-character key", () => {
    expect(checkFactKey("k".repeat(64))).toBeNull();
  });
});
