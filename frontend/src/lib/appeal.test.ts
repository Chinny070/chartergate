import { describe, expect, it } from "vitest";
import {
  appealGate,
  APPEAL_GROUNDS,
  BLOCKED_REASON_TEXT,
  DECISION_INFO,
  DISSENT_NOTE,
  dissentOutcome,
  FROZEN_RECORD_NOTE,
  materialDifferences,
  MAX_APPEAL_STATEMENT,
  REPAIR_VS_APPEAL,
} from "./appeal";
import type { ReviewFinding } from "./genlayer/charterGate";

const f = (section_id: string, finding: ReviewFinding["finding"], repairable = false): ReviewFinding => ({
  section_id,
  finding,
  repairable,
  evidence_ids: [],
  missing_fact: "",
  rationale: "",
});

describe("appealGate", () => {
  const ok = { connection: "ready", isProposer: true, appealable: true, blockedReason: "" };
  it("allows the proposer with a connected wallet", () => expect(appealGate(ok).allowed).toBe(true));
  it("explains why a ruling cannot be appealed", () => {
    for (const reason of Object.keys(BLOCKED_REASON_TEXT)) {
      const g = appealGate({ ...ok, appealable: false, blockedReason: reason });
      expect(g.allowed).toBe(false);
      expect(g.reason).toBe(BLOCKED_REASON_TEXT[reason]);
    }
  });
  it("asks for a wallet, the right network and the proposer", () => {
    expect(appealGate({ ...ok, connection: "disconnected" }).reason).toMatch(/Connect your wallet/);
    expect(appealGate({ ...ok, connection: "wrong_network" }).reason).toMatch(/StudioNet/);
    expect(appealGate({ ...ok, isProposer: false }).reason).toMatch(/Only the proposer/);
  });
});

describe("copy", () => {
  it("separates repair from appeal and freezes the record in plain words", () => {
    expect(REPAIR_VS_APPEAL.repair).toMatch(/changes the proposal/);
    expect(REPAIR_VS_APPEAL.appeal).toMatch(/existing record/);
    expect(FROZEN_RECORD_NOTE).toBe("New evidence submitted after this review will not be considered in this appeal.");
  });
  it("offers exactly the four documented grounds and a bounded statement", () => {
    expect(APPEAL_GROUNDS.map((g) => g.id)).toEqual(["CHARTER_MISINTERPRETATION", "EVIDENCE_MISAPPLICATION", "PRECEDENT_MISAPPLICATION", "PROCEDURAL_ERROR"]);
    expect(MAX_APPEAL_STATEMENT).toBe(1000);
  });
  it("describes the three dispositions", () => expect(Object.keys(DECISION_INFO)).toEqual(["AFFIRMED", "MODIFIED", "REVERSED"]));
  it("calls a dissent AI-generated and non-controlling, never a validator vote", () => {
    expect(DISSENT_NOTE).toMatch(/AI-generated/);
    expect(DISSENT_NOTE).toMatch(/not a validator vote or minority/);
    expect(DISSENT_NOTE).toMatch(/does not change the effective judgment/);
  });
});

describe("dissentOutcome", () => {
  it("recognises the no-dissent rollback", () => {
    expect(dissentOutcome("EXPECTED:NO_MATERIAL_DISSENT")?.reason).toMatch(/no dissent was stored/);
    expect(dissentOutcome("EXPECTED:NOT_PROPOSER")).toBeNull();
    expect(dissentOutcome(undefined)).toBeNull();
  });
});

describe("materialDifferences", () => {
  it("counts a class change or a repairability change, and nothing else", () => {
    expect(materialDifferences([f("1", "SATISFIED"), f("3", "VIOLATED", true)], [f("1", "SATISFIED"), f("3", "SATISFIED")])).toEqual(["3"]);
    expect(materialDifferences([f("3", "VIOLATED", true)], [f("3", "VIOLATED", false)])).toEqual(["3"]);
    expect(materialDifferences([f("3", "VIOLATED", true)], [f("3", "VIOLATED", true)])).toEqual([]);
    expect(materialDifferences([f("3", "SATISFIED", false)], [f("3", "SATISFIED", true)])).toEqual([]);
  });
});
