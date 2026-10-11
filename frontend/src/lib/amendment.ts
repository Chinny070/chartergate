import type { Tone } from "../components/primitives";
import type { Amendment, AmendmentAction, AmendmentExecutionState, AmendmentStatus, ExecutionOutcome, ProposalAccountability } from "./genlayer/charterGate";

/**
 * Presentation and pre-flight rules for constitutional amendments and execution accountability. Nothing here decides anything: the lifecycle,
 * the evaluation, the approval, the application and every hash are read from (or decided by) the contract.
 */

export const MAX_RATIONALE = 1000;

export const STATUS_INFO: Record<AmendmentStatus, { label: string; tone: Tone; explain: string }> = {
  PROPOSED: { label: "PROPOSED", tone: "precedent", explain: "Written against one exact charter version. Nothing has changed yet." },
  EVALUATED: { label: "EVALUATED", tone: "warning", explain: "A model advised on compatibility with the rest of the charter. It approved nothing." },
  APPROVED: { label: "APPROVED", tone: "eligible", explain: "The owner approved it. It still has to be applied, and it applies only to the version it was written against." },
  APPLIED: { label: "APPLIED", tone: "final", explain: "The charter changed. The contract recorded the new charter version." },
  REJECTED: { label: "REJECTED", tone: "ineligible", explain: "Closed by the owner (rejected) or the proposer (withdrawn). The charter did not change." },
  SUPERSEDED: { label: "SUPERSEDED", tone: "active", explain: "The charter moved on before this could apply. The charter did not change because of it." },
};

export const EXECUTION_INFO: Record<AmendmentExecutionState, { label: string; tone: Tone; explain: string }> = {
  NOT_APPROVED: { label: "NOT APPROVED", tone: "active", explain: "No approval yet, so nothing can be applied." },
  APPROVED_NOT_APPLIED: { label: "APPROVED, NOT YET APPLIED", tone: "eligible", explain: "Approved and still current. It can be applied." },
  APPROVED_BUT_STALE: { label: "APPROVED BUT STALE", tone: "warning", explain: "The charter changed after approval, so it can no longer apply. It can be closed as superseded." },
  APPLIED: { label: "APPLIED", tone: "final", explain: "Applied by the contract itself: the charter version it created is recorded below." },
  REJECTED: { label: "REJECTED", tone: "ineligible", explain: "Closed without changing the charter." },
  SUPERSEDED: { label: "SUPERSEDED", tone: "active", explain: "Closed because the charter moved on. It was never applied." },
};

export const ACTION_INFO: Record<AmendmentAction, { label: string; help: string }> = {
  ADD: { label: "Add a section", help: "A new charter section. The id must not exist yet." },
  UPDATE: { label: "Change a section", help: "New wording for an active section. The old wording stays in the history." },
  DEACTIVATE: { label: "Deactivate a section", help: "The section stops applying to new proposals. Existing history is kept." },
};

export const EVAL_NOTE =
  "The compatibility evaluation is advice from validators, not a decision. A COMPATIBLE verdict does not approve anything, and a CONFLICTING verdict blocks approval.";

export const GOVERNANCE_ON_NOTE = "Amendment governance is on: the charter changes only through an approved, applied amendment. Direct owner edits are closed.";
export const GOVERNANCE_OFF_NOTE = "Amendment governance is off: the owner can still edit the charter directly. Turning it on is one-way.";

export interface ActionGate {
  allowed: boolean;
  reason: string | null;
}

const gate = (allowed: boolean, reason: string): ActionGate => ({ allowed, reason: allowed ? null : reason });

/** Who may do what to an amendment, and when. The contract enforces all of it; the UI only avoids offering a doomed transaction. */
export function amendmentGates(input: {
  connection: string;
  isOwner: boolean;
  isProposer: boolean;
  status: AmendmentStatus;
  evalVerdict: Amendment["eval_verdict"];
  stale: boolean;
}) {
  const base = input.connection === "ready" ? null : input.connection === "wrong_network" ? "Switch your wallet to StudioNet (chain 61999)." : "Connect your wallet first.";
  const wallet = (g: ActionGate) => (base !== null && g.allowed ? { allowed: false, reason: base } : g);
  const either = input.isOwner || input.isProposer;
  return {
    evaluate: wallet(
      !either
        ? gate(false, "Only the proposer or the owner can request the evaluation.")
        : input.status !== "PROPOSED"
          ? gate(false, "Only a proposed amendment can be evaluated, once.")
          : input.stale
            ? gate(false, "The charter has changed since this was written, so it can no longer be evaluated.")
            : gate(true, ""),
    ),
    approve: wallet(
      !input.isOwner
        ? gate(false, "Only the owner can approve.")
        : input.status !== "EVALUATED"
          ? gate(false, "Only an evaluated amendment can be approved.")
          : input.evalVerdict !== "COMPATIBLE"
            ? gate(false, "A conflicting amendment cannot be approved.")
            : input.stale
              ? gate(false, "The charter has changed since this was written, so it can no longer be approved.")
              : gate(true, ""),
    ),
    apply: wallet(
      !either
        ? gate(false, "Only the proposer or the owner can apply it.")
        : input.status !== "APPROVED"
          ? gate(false, "Only an approved amendment can be applied.")
          : input.stale
            ? gate(false, "The charter has changed since approval, so it can no longer apply.")
            : gate(true, ""),
    ),
    reject: wallet(
      !either
        ? gate(false, "Only the proposer (withdraw) or the owner (reject) can close it.")
        : input.status === "PROPOSED" || input.status === "EVALUATED" || input.status === "APPROVED"
          ? gate(true, "")
          : gate(false, "This amendment is already closed."),
    ),
    closeStale: wallet(
      !either
        ? gate(false, "Only the proposer or the owner can close it.")
        : !input.stale
          ? gate(false, "The charter has not changed since this was written.")
          : gate(true, ""),
    ),
  };
}

/** What a rolled-back amendment transaction means, from the contract's own refusal code. */
export const AMENDMENT_FAILURE_INFO: Record<string, string> = {
  "EXPECTED:AMENDMENT_STALE": "The charter changed after this amendment was written, so it was refused. Nothing changed.",
  "EXPECTED:AMENDMENT_CONFLICTING": "A conflicting amendment cannot be approved. Nothing changed.",
  "EXPECTED:AMENDMENT_NOT_APPROVED": "This amendment is not approved, so it cannot be applied. Nothing changed.",
  "EXPECTED:AMENDMENT_NOT_APPROVABLE": "Only an evaluated amendment can be approved. Nothing changed.",
  "EXPECTED:AMENDMENT_NOT_EVALUABLE": "Only a proposed amendment can be evaluated, once. Nothing changed.",
  "EXPECTED:AMENDMENT_NOT_OPEN": "This amendment is already closed. Nothing changed.",
  "EXPECTED:AMENDMENT_NOT_STALE": "The charter has not changed since this was written. Nothing changed.",
  "EXPECTED:AMENDMENT_NO_CHANGE": "That wording is the same as the current section, so there is nothing to amend.",
  "EXPECTED:SECTION_ID_EXISTS": "A section with that id already exists.",
  "EXPECTED:SECTION_NOT_FOUND": "That section does not exist.",
  "EXPECTED:NOT_OWNER": "Only the owner can do that.",
  "EXPECTED:NOT_AUTHORIZED": "Only the proposer or the owner can do that.",
  "EXPECTED:GOVERNANCE_ALREADY_ENABLED": "Amendment governance is already on.",
  "EXPECTED:AMENDMENT_GOVERNANCE_REQUIRED": "Amendment governance is on: change the charter through an amendment.",
};

export function amendmentFailure(code: string | undefined): string | null {
  return code ? (AMENDMENT_FAILURE_INFO[code] ?? null) : null;
}

// ---- execution reports (proposals) ---------------------------------------------------------------------------------------------------------------------

export const UNVERIFIED_NOTE =
  "Self-reported by the proposer. The contract cannot see outside events, so it has not verified any of this, and no payment, transfer or other external action is confirmed by it.";

export const REPORT_INFO: Record<ExecutionOutcome, { label: string; tone: Tone; explain: string }> = {
  ATTEMPTED: { label: "ATTEMPT REPORTED", tone: "warning", explain: "The proposer says execution was started. That is not a completed execution." },
  REPORTED_COMPLETE: { label: "REPORTED COMPLETE (UNVERIFIED)", tone: "precedent", explain: "The proposer says execution finished. The contract did not verify it." },
  REPORTED_FAILED: { label: "REPORTED FAILED", tone: "ineligible", explain: "The proposer says execution failed." },
};

export const PROPOSAL_EXECUTION_INFO: Record<ProposalAccountability["execution_state"], { label: string; tone: Tone; explain: string }> = {
  NOT_APPROVED: { label: "NOT APPROVED", tone: "active", explain: "The controlling ruling is not ELIGIBLE, so there is no approved decision to execute." },
  APPROVED_NOT_REPORTED: { label: "APPROVED · NOTHING REPORTED", tone: "eligible", explain: "The ruling is ELIGIBLE. The proposer has not reported any execution." },
  ATTEMPTED: REPORT_INFO.ATTEMPTED,
  REPORTED_COMPLETE: REPORT_INFO.REPORTED_COMPLETE,
  REPORTED_FAILED: REPORT_INFO.REPORTED_FAILED,
};

/** The reports that may follow the current state: one optional attempt, then exactly one closing report. */
export function nextOutcomes(state: ProposalAccountability["execution_state"]): ExecutionOutcome[] {
  if (state === "APPROVED_NOT_REPORTED") return ["ATTEMPTED", "REPORTED_COMPLETE", "REPORTED_FAILED"];
  if (state === "ATTEMPTED") return ["REPORTED_COMPLETE", "REPORTED_FAILED"];
  return [];
}

export const MAX_EXECUTION_NOTE = 500;

export function reportGate(input: { connection: string; isProposer: boolean; state: ProposalAccountability["execution_state"] }): ActionGate {
  if (input.state === "NOT_APPROVED") return gate(false, "Only a proposal whose controlling ruling is ELIGIBLE can be reported as executed.");
  if (nextOutcomes(input.state).length === 0) return gate(false, "The execution record is closed. It cannot be changed.");
  if (input.connection === "disconnected") return gate(false, "Connect your wallet to report.");
  if (input.connection === "wrong_network") return gate(false, "Switch your wallet to StudioNet (chain 61999).");
  if (!input.isProposer) return gate(false, "Only the proposer can report.");
  return gate(true, "");
}

export function reportFailure(code: string | undefined): string | null {
  const map: Record<string, string> = {
    "EXPECTED:EXECUTION_ALREADY_CLOSED": "The execution record is already closed. Nothing changed.",
    "EXPECTED:EXECUTION_ALREADY_ATTEMPTED": "An attempt was already reported. Report how it ended. Nothing changed.",
    "EXPECTED:PROPOSAL_NOT_APPROVED": "The controlling ruling is not ELIGIBLE. Nothing changed.",
    "EXPECTED:NOT_PROPOSER": "Only the proposer can report.",
  };
  return code ? (map[code] ?? null) : null;
}
