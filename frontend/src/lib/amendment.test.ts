import { describe, expect, it } from "vitest";
import {
  ACTION_INFO,
  amendmentFailure,
  amendmentGates,
  EXECUTION_INFO,
  nextOutcomes,
  PROPOSAL_EXECUTION_INFO,
  reportFailure,
  reportGate,
  REPORT_INFO,
  STATUS_INFO,
  UNVERIFIED_NOTE,
} from "./amendment";
import {
  AMENDMENT_ACTIONS,
  AMENDMENT_EXECUTION_STATES,
  AMENDMENT_STATUSES,
  decodeAmendment,
  decodeAmendmentAccountability,
  decodeGovernanceStatus,
  decodePrecedentRule,
  decodeProposalAccountability,
  EXECUTION_OUTCOMES,
} from "./genlayer/charterGate";

const base = { connection: "ready", isOwner: false, isProposer: true, status: "PROPOSED" as const, evalVerdict: "" as const, stale: false };

describe("amendmentGates", () => {
  it("offers a proposer the evaluation of a proposed, current amendment and nothing that is the owner's", () => {
    const g = amendmentGates(base);
    expect(g.evaluate.allowed).toBe(true);
    expect(g.approve.allowed).toBe(false);
    expect(g.approve.reason).toMatch(/Only the owner/);
    expect(g.apply.allowed).toBe(false);
    expect(g.reject.allowed).toBe(true); // a proposer can withdraw
  });

  it("lets only the owner approve, and only a compatible, evaluated, current amendment", () => {
    const owner = { ...base, isOwner: true, isProposer: false, status: "EVALUATED" as const, evalVerdict: "COMPATIBLE" as const };
    expect(amendmentGates(owner).approve.allowed).toBe(true);
    expect(amendmentGates({ ...owner, evalVerdict: "CONFLICTING" }).approve.reason).toMatch(/conflicting/);
    expect(amendmentGates({ ...owner, stale: true }).approve.reason).toMatch(/charter has changed/);
    expect(amendmentGates({ ...owner, status: "PROPOSED" }).approve.reason).toMatch(/evaluated/);
  });

  it("offers apply only for an approved, current amendment and closing only for a stale one", () => {
    const approved = { ...base, status: "APPROVED" as const, evalVerdict: "COMPATIBLE" as const };
    expect(amendmentGates(approved).apply.allowed).toBe(true);
    expect(amendmentGates({ ...approved, stale: true }).apply.reason).toMatch(/can no longer apply/);
    expect(amendmentGates({ ...approved, stale: true }).closeStale.allowed).toBe(true);
    expect(amendmentGates(approved).closeStale.reason).toMatch(/has not changed/);
  });

  it("offers nothing on a closed amendment", () => {
    for (const status of ["APPLIED", "REJECTED", "SUPERSEDED"] as const) {
      const g = amendmentGates({ ...base, isOwner: true, status });
      expect(g.evaluate.allowed || g.approve.allowed || g.apply.allowed || g.reject.allowed).toBe(false);
    }
  });

  it("refuses a stranger everything and asks for a wallet and the right network first", () => {
    const stranger = amendmentGates({ ...base, isProposer: false });
    expect(Object.values(stranger).every((g) => !g.allowed)).toBe(true);
    expect(amendmentGates({ ...base, connection: "disconnected" }).evaluate.reason).toMatch(/Connect your wallet/);
    expect(amendmentGates({ ...base, connection: "wrong_network" }).evaluate.reason).toMatch(/StudioNet/);
  });
});

describe("copy and maps", () => {
  it("covers every status, execution state and action the contract can return", () => {
    for (const s of AMENDMENT_STATUSES) expect(STATUS_INFO[s].label).not.toBe("");
    for (const s of AMENDMENT_EXECUTION_STATES) expect(EXECUTION_INFO[s].explain).not.toBe("");
    for (const a of AMENDMENT_ACTIONS) expect(ACTION_INFO[a].help).not.toBe("");
    for (const o of EXECUTION_OUTCOMES) expect(REPORT_INFO[o].explain).not.toBe("");
    expect(Object.keys(PROPOSAL_EXECUTION_INFO)).toEqual(["NOT_APPROVED", "APPROVED_NOT_REPORTED", "ATTEMPTED", "REPORTED_COMPLETE", "REPORTED_FAILED"]);
  });

  it("never presents a self-reported outcome as a verified one", () => {
    expect(UNVERIFIED_NOTE).toMatch(/cannot see outside events/);
    expect(UNVERIFIED_NOTE).toMatch(/not verified/);
    expect(REPORT_INFO.REPORTED_COMPLETE.label).toMatch(/UNVERIFIED/);
    expect(REPORT_INFO.ATTEMPTED.explain).toMatch(/not a completed execution/);
  });

  it("explains a rolled-back transaction by the contract's own code, and says nothing changed", () => {
    expect(amendmentFailure("EXPECTED:AMENDMENT_STALE")).toMatch(/Nothing changed/);
    expect(amendmentFailure("EXPECTED:AMENDMENT_CONFLICTING")).toMatch(/cannot be approved/);
    expect(amendmentFailure("EXPECTED:UNKNOWN")).toBeNull();
    expect(amendmentFailure(undefined)).toBeNull();
    expect(reportFailure("EXPECTED:EXECUTION_ALREADY_CLOSED")).toMatch(/closed/);
  });
});

describe("execution reports", () => {
  it("allows one optional attempt and then exactly one closing report", () => {
    expect(nextOutcomes("APPROVED_NOT_REPORTED")).toEqual(["ATTEMPTED", "REPORTED_COMPLETE", "REPORTED_FAILED"]);
    expect(nextOutcomes("ATTEMPTED")).toEqual(["REPORTED_COMPLETE", "REPORTED_FAILED"]);
    expect(nextOutcomes("REPORTED_COMPLETE")).toEqual([]);
    expect(nextOutcomes("REPORTED_FAILED")).toEqual([]);
    expect(nextOutcomes("NOT_APPROVED")).toEqual([]);
  });

  it("gates reporting to the proposer of an approved proposal with an open record", () => {
    const ok = { connection: "ready", isProposer: true, state: "APPROVED_NOT_REPORTED" as const };
    expect(reportGate(ok).allowed).toBe(true);
    expect(reportGate({ ...ok, state: "NOT_APPROVED" }).reason).toMatch(/ELIGIBLE/);
    expect(reportGate({ ...ok, state: "REPORTED_COMPLETE" }).reason).toMatch(/closed/);
    expect(reportGate({ ...ok, isProposer: false }).reason).toMatch(/Only the proposer/);
    expect(reportGate({ ...ok, connection: "disconnected" }).reason).toMatch(/Connect/);
  });
});

const amendmentRaw = {
  amendment_id: 1,
  proposer: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b",
  action: "UPDATE",
  section_id: "3",
  title: "Budget",
  body: "New wording.",
  rationale: "Because.",
  base_version: 4n,
  source_proposal_id: 0,
  status: "EVALUATED",
  amendment_hash: "0x" + "ab".repeat(32),
  created_at: "t",
  eval_verdict: "CONFLICTING",
  eval_conflicting_section_ids: ["1"],
  eval_hash: "0x" + "cd".repeat(32),
  evaluated_at: "t",
  decided_by: "",
  decided_at: "",
  applied_version: 0,
  applied_by: "",
  applied_at: "",
};

describe("decoders", () => {
  it("decode an amendment and its accountability", () => {
    const a = decodeAmendment(amendmentRaw);
    expect(a.base_version).toBe(4);
    expect(a.eval_conflicting_section_ids).toEqual(["1"]);
    const acc = decodeAmendmentAccountability({
      amendment: amendmentRaw,
      events: [{ kind: "PROPOSED", actor: "0x1", at: "t", charter_version: 4 }],
      stale: false,
      current_charter_version: 4,
      execution_state: "NOT_APPROVED",
      contract_verified: true,
    });
    expect(acc.events[0].kind).toBe("PROPOSED");
    expect(acc.contract_verified).toBe(true);
  });

  it("fail loudly on an unknown status, verdict or execution state", () => {
    expect(() => decodeAmendment({ ...amendmentRaw, status: "DONE" })).toThrow(/unknown value/);
    expect(() => decodeAmendment({ ...amendmentRaw, eval_verdict: "MAYBE" })).toThrow(/unknown value/);
    expect(() => decodeAmendment({ ...amendmentRaw, eval_conflicting_section_ids: [1] })).toThrow(/list of strings/);
    expect(() => decodeProposalAccountability({ proposal_id: 1, review_id: 1, appeal_id: 0, effective_verdict: "ELIGIBLE", ruling_hash: "h", charter_version: 4, approved: true, execution_state: "PAID", reports: [], verified: false })).toThrow(/unknown value/);
  });

  it("decode governance status, proposal accountability and precedent rules", () => {
    expect(decodeGovernanceStatus({ governance_enabled: true, governance_enabled_at: "t", charter_version: 5, owner: "0x1", amendment_count: 2 }).governance_enabled).toBe(true);
    const p = decodeProposalAccountability({
      proposal_id: 2,
      review_id: 3,
      appeal_id: 1,
      effective_verdict: "ELIGIBLE",
      ruling_hash: "h",
      charter_version: 4,
      approved: true,
      execution_state: "ATTEMPTED",
      reports: [{ report_number: 1, proposal_id: 2, outcome: "ATTEMPTED", note: "n", reporter: "0x1", reported_at: "t", charter_version: 4, review_id: 3, appeal_id: 1, ruling_hash: "h", verified: false }],
      verified: false,
    });
    expect(p.reports[0].verified).toBe(false);
    expect(p.verified).toBe(false);
    expect(decodePrecedentRule({ section_id: "3", title: "Budget", rule: "3@4", review_count: 2n, newest_review_ids: [1, 2] }).review_count).toBe(2);
  });
});
