import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { AmendmentAccountabilityView } from "./Amendment";
import { ProposalAccountabilityView } from "./Accountability";
import { decodeAmendmentAccountability, decodeProposalAccountability } from "../lib/genlayer/charterGate";

const amendment = (over: Record<string, unknown> = {}) => ({
  amendment_id: 2,
  proposer: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b",
  action: "UPDATE",
  section_id: "3",
  title: "Budget",
  body: "Budgets must name a currency.",
  rationale: "Amounts without a currency are ambiguous.",
  base_version: 4,
  source_proposal_id: 0,
  status: "APPLIED",
  amendment_hash: "0x" + "ab".repeat(32),
  created_at: "2026-10-10T10:00:00Z",
  eval_verdict: "COMPATIBLE",
  eval_conflicting_section_ids: [],
  eval_hash: "0x" + "cd".repeat(32),
  evaluated_at: "2026-10-10T10:05:00Z",
  decided_by: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b",
  decided_at: "2026-10-10T10:10:00Z",
  applied_version: 5,
  applied_by: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b",
  applied_at: "2026-10-10T10:15:00Z",
  ...over,
});

const accountability = (state: string, over: Record<string, unknown> = {}, stale = false) =>
  decodeAmendmentAccountability({
    amendment: amendment(over),
    events: [
      { kind: "PROPOSED", actor: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b", at: "2026-10-10T10:00:00Z", charter_version: 4 },
      { kind: "APPLIED", actor: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b", at: "2026-10-10T10:15:00Z", charter_version: 5 },
    ],
    stale,
    current_charter_version: 5,
    execution_state: state,
    contract_verified: true,
  });

const render = (node: React.ReactElement) => renderToStaticMarkup(<MemoryRouter>{node}</MemoryRouter>);

describe("AmendmentAccountabilityView", () => {
  it("shows an applied amendment as applied by the contract, with the versions it touched", () => {
    const html = render(<AmendmentAccountabilityView acc={accountability("APPLIED")} />);
    expect(html).toContain("APPLIED");
    expect(html).toContain("VERIFIED BY THE CONTRACT");
    expect(html).toContain("Changed charter v4 into");
    expect(html).toContain("v5");
    expect(html).toContain("PROPOSED");
    expect(html).toContain("Amendment hash");
    expect(html).toContain("Why (the proposer&#x27;s argument, not evidence)");
  });

  it("states that the compatibility evaluation only advises", () => {
    const html = render(<AmendmentAccountabilityView acc={accountability("APPLIED")} />);
    expect(html).toContain("The compatibility evaluation is advice from validators, not a decision.");
  });

  it("does not claim an unapproved or closed amendment changed the charter", () => {
    const notApproved = render(<AmendmentAccountabilityView acc={accountability("NOT_APPROVED", { status: "PROPOSED", eval_verdict: "", applied_version: 0, applied_by: "", decided_by: "" })} />);
    expect(notApproved).toContain("NOT APPROVED");
    expect(notApproved).toContain("Not evaluated yet.");
    expect(notApproved).not.toContain("Changed charter");
    const superseded = render(<AmendmentAccountabilityView acc={accountability("SUPERSEDED", { status: "SUPERSEDED", applied_version: 0, applied_by: "" })} />);
    expect(superseded).toContain("SUPERSEDED");
    expect(superseded).toContain("was never applied");
    expect(superseded).not.toContain("Changed charter");
  });

  it("shows a conflicting verdict and what it conflicts with", () => {
    const html = render(<AmendmentAccountabilityView acc={accountability("NOT_APPROVED", { status: "EVALUATED", eval_verdict: "CONFLICTING", eval_conflicting_section_ids: ["1", "2"], applied_version: 0 })} />);
    expect(html).toContain("CONFLICTING");
    expect(html).toContain("§1, §2");
  });

  it("reports a stale approved amendment as stale, not as applied", () => {
    const html = render(<AmendmentAccountabilityView acc={accountability("APPROVED_BUT_STALE", { status: "APPROVED", applied_version: 0, applied_by: "" }, true)} />);
    expect(html).toContain("APPROVED BUT STALE");
    expect(html).toContain("can no longer apply");
  });
});

const proposal = (state: string, reports: unknown[] = [], approved = true) =>
  decodeProposalAccountability({
    proposal_id: 4,
    review_id: 6,
    appeal_id: 0,
    effective_verdict: approved ? "ELIGIBLE" : "REPAIRABLE",
    ruling_hash: "0x" + "ef".repeat(32),
    charter_version: 5,
    approved,
    execution_state: state,
    reports,
    verified: false,
  });

const report = (n: number, outcome: string, note: string) => ({
  report_number: n,
  proposal_id: 4,
  outcome,
  note,
  reporter: "0xaffE15eEc45b68835cc9E5B4Ab85dD5deaE8e70b",
  reported_at: "2026-10-11T08:00:00Z",
  charter_version: 5,
  review_id: 6,
  appeal_id: 0,
  ruling_hash: "0x" + "ef".repeat(32),
  verified: false,
});

describe("ProposalAccountabilityView", () => {
  it("separates an approved decision from an attempt and from a reported completion, and never says verified", () => {
    const approved = render(<ProposalAccountabilityView acc={proposal("APPROVED_NOT_REPORTED")} />);
    expect(approved).toContain("APPROVED · NOTHING REPORTED");
    expect(approved).toContain("NOT VERIFIED BY THE CONTRACT");
    expect(approved).toContain("No execution has been reported.");

    const attempted = render(<ProposalAccountabilityView acc={proposal("ATTEMPTED", [report(1, "ATTEMPTED", "Started.")])} />);
    expect(attempted).toContain("ATTEMPT REPORTED");
    expect(attempted).toContain("not a completed execution");

    const complete = render(<ProposalAccountabilityView acc={proposal("REPORTED_COMPLETE", [report(1, "ATTEMPTED", "Started."), report(2, "REPORTED_COMPLETE", "Paid out.")])} />);
    expect(complete).toContain("REPORTED COMPLETE (UNVERIFIED)");
    expect(complete).toContain("the contract did not verify it".replace("the", "The"));
    expect(complete).toContain("not verified");
    expect(complete.toLowerCase()).not.toContain("payment confirmed");
    expect(complete).toContain("cannot see outside events");
  });

  it("represents a failed execution honestly and a never-approved proposal as not approved", () => {
    expect(render(<ProposalAccountabilityView acc={proposal("REPORTED_FAILED", [report(1, "REPORTED_FAILED", "Rejected.")])} />)).toContain("REPORTED FAILED");
    const notApproved = render(<ProposalAccountabilityView acc={proposal("NOT_APPROVED", [], false)} />);
    expect(notApproved).toContain("NOT APPROVED");
    expect(notApproved).toContain("controlling ruling is not ELIGIBLE");
  });

  it("shows the decision the reports answer to", () => {
    const html = render(<ProposalAccountabilityView acc={proposal("APPROVED_NOT_REPORTED")} />);
    expect(html).toContain("ELIGIBLE");
    expect(html).toContain("review #006");
    expect(html).toContain("charter v5");
    expect(html).toContain("Ruling hash");
  });
});
