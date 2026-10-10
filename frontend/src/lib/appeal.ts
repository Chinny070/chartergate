import type { Tone } from "../components/primitives";
import type { AppealGround, DecisionKind, ReviewFinding } from "./genlayer/charterGate";

/**
 * Presentation and pre-flight rules for appeals and reasoned dissent. Nothing here decides anything: the closed record, the appellate
 * findings, the verdict, the disposition and every hash are read from (or decided by) the contract.
 */

export const MAX_APPEAL_STATEMENT = 1000;

export const REPAIR_VS_APPEAL = {
  repair: "Repair changes the proposal. It becomes a new immutable revision that is reviewed again.",
  appeal: "Appeal challenges the ruling on the existing record. The proposal, the evidence and the charter stay exactly as they were.",
};

export const FROZEN_RECORD_NOTE = "New evidence submitted after this review will not be considered in this appeal.";

export const FROZEN_RECORD_DETAIL =
  "An appeal judges the closed record the original review judged: the charter version in force at submission, the proposal text under review, the evidence snapshot and the precedent snapshot it saw. Later evidence, later charter amendments and later precedents never enter it, and the original review is never changed.";

export const APPEAL_NOT_EVIDENCE = "Your statement is an argument, not evidence. It does not make any finding true.";

export const APPEAL_GROUNDS: readonly { id: AppealGround; label: string; help: string }[] = [
  { id: "CHARTER_MISINTERPRETATION", label: "Charter misinterpretation", help: "The review read a charter requirement wrongly." },
  { id: "EVIDENCE_MISAPPLICATION", label: "Evidence misapplication", help: "The review misjudged what the evidence snapshot shows." },
  { id: "PRECEDENT_MISAPPLICATION", label: "Precedent misapplication", help: "The review was wrongly influenced by, or wrongly treated, an earlier ruling. Available only if the review saw precedent." },
  { id: "PROCEDURAL_ERROR", label: "Procedural error", help: "The review was not carried out on the record it should have used." },
];

export const DECISION_INFO: Record<DecisionKind, { label: string; tone: Tone; explain: string }> = {
  AFFIRMED: {
    label: "AFFIRMED",
    tone: "active",
    explain: "The appellate review reached the same material findings and the same constitutional verdict.",
  },
  MODIFIED: {
    label: "MODIFIED",
    tone: "warning",
    explain: "The constitutional verdict is unchanged, but at least one section's finding or its repairability changed.",
  },
  REVERSED: {
    label: "REVERSED",
    tone: "precedent",
    explain: "The constitutional verdict changed. An appeal is a genuine re-judgment: it can help or hurt the appellant.",
  },
};

export const WIN_IS_NOT_SUCCESS =
  "A finalized transaction means the appeal was processed, not that it succeeded. The appellate decision below is the result.";

export const BLOCKED_REASON_TEXT: Record<string, string> = {
  APPEAL_ALREADY_EXISTS: "This ruling has already been appealed. There is one appeal per review.",
  REVIEW_NOT_ADVERSE: "An ELIGIBLE ruling cannot be appealed by the proposer.",
  REVIEW_NOT_CONTROLLING: "Only the latest controlling review of the proposal's current revision can be appealed.",
  REPAIR_ALREADY_STARTED: "A repair has already been started from this ruling. Repair and appeal are alternatives.",
};

/** Whether to offer the appeal, and if not, why. The contract enforces all of it; the UI only avoids offering a doomed transaction. */
export function appealGate(input: { connection: string; isProposer: boolean; appealable: boolean; blockedReason: string }): { allowed: boolean; reason: string | null } {
  if (!input.appealable) return { allowed: false, reason: BLOCKED_REASON_TEXT[input.blockedReason] ?? "This ruling cannot be appealed." };
  if (input.connection === "disconnected") return { allowed: false, reason: "Connect your wallet to appeal this ruling." };
  if (input.connection === "wrong_network") return { allowed: false, reason: "Switch your wallet to StudioNet (chain 61999)." };
  if (!input.isProposer) return { allowed: false, reason: "Only the proposer can appeal this ruling." };
  return { allowed: true, reason: null };
}

export const PRECEDENT_AFTER_APPEAL: Record<DecisionKind, string> = {
  AFFIRMED: "The original ruling stays eligible as automatic precedent for future reviews.",
  MODIFIED:
    "The original ruling no longer appears as automatic precedent for future reviews, because an appeal changed it. It stays in the history. The appellate decision is not yet automatic precedent.",
  REVERSED:
    "The original ruling no longer appears as automatic precedent for future reviews, because an appeal reversed it. It stays in the history. The appellate decision is not yet automatic precedent.",
};

export const DISSENT_LABEL = "REASONED DISSENT";
export const DISSENT_HEADLINE = "Non-controlling alternative interpretation";
export const DISSENT_NOTE =
  "This is an AI-generated alternative reading of the same closed record. It is not a validator vote or minority, it is not evidence and not precedent, and it does not change the effective judgment, the proposal status or the repair targets.";
export const DISSENT_REQUEST_NOTE =
  "A reasoned dissent is optional and separate from the appeal. If no materially different reading exists, nothing is stored.";

/** What a failed dissent request means. */
export function dissentOutcome(code: string | undefined): { stored: false; reason: string } | null {
  if (code === "EXPECTED:NO_MATERIAL_DISSENT") {
    return { stored: false, reason: "No materially different reading of this record was found, so no dissent was stored." };
  }
  return null;
}

/** The sections whose class or repairability differ between two sets of findings (the contract's notion of a material difference). */
export function materialDifferences(a: readonly ReviewFinding[], b: readonly ReviewFinding[]): string[] {
  const sig = (f: ReviewFinding) => `${f.finding}|${f.finding === "VIOLATED" ? f.repairable : false}`;
  const by = new Map(b.map((f) => [f.section_id, f]));
  return a.filter((f) => {
    const other = by.get(f.section_id);
    return other !== undefined && sig(f) !== sig(other);
  }).map((f) => f.section_id);
}
