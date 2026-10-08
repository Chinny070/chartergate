import { describe, expect, it } from "vitest";
import { decodeDaoMetadata, decodeProposal, decodeRevision, decodeSection, SECTION_ID_PATTERN } from "./charterGate";

const section = {
  section_id: "1",
  title: "Mission",
  body: "Fund open-source infrastructure.",
  active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("decoders", () => {
  it("decode plain objects", () => {
    expect(decodeSection(section)).toEqual(section);
  });
  it("decode Maps (genlayer-js may return either)", () => {
    expect(decodeSection(new Map(Object.entries(section)))).toEqual(section);
  });
  it("convert bigint integers to numbers", () => {
    const p = decodeProposal({
      proposal_id: 1n,
      proposer: "0xabc",
      title: "t",
      description: "d",
      requested_action: "a",
      created_at: "x",
      charter_version_at_submission: 3n,
      status: "SUBMITTED",
    });
    expect(p.proposal_id).toBe(1);
    expect(p.charter_version_at_submission).toBe(3);
  });
  it("fail loudly instead of defaulting when the shape is wrong", () => {
    expect(() => decodeSection({ ...section, active: "yes" })).toThrow(/boolean/);
    expect(() => decodeDaoMetadata(null)).toThrow(/object/);
    expect(() => decodeDaoMetadata({ dao_name: "x" })).toThrow();
  });
});

describe("SECTION_ID_PATTERN", () => {
  it("matches the contract's allowed id characters", () => {
    for (const ok of ["1", "mission", "a-b_c.d", "A1"]) expect(SECTION_ID_PATTERN.test(ok)).toBe(true);
    for (const bad of ["", "a b", "a/b", "é", " 1"]) expect(SECTION_ID_PATTERN.test(bad)).toBe(false);
  });
});

describe("decodeRevision", () => {
  it("decodes an immutable charter revision", () => {
    const rev = {
      section_id: "1",
      charter_version: 3n,
      title: "Mission",
      body: "text",
      active: false,
      changed_at: "2026-01-01T00:00:00Z",
    };
    expect(decodeRevision(rev)).toEqual({ ...rev, charter_version: 3 });
    expect(() => decodeRevision({ ...rev, changed_at: 5 })).toThrow(/string/);
  });
});
