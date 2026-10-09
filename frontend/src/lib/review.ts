import type { Tone } from "../components/primitives";
import type { ConstitutionalReview, EvidenceRecord, FindingKind, ReviewFinding, ReviewVerdict } from "./genlayer/charterGate";

/**
 * Presentation rules for constitutional reviews. Nothing here decides anything: the verdict, the findings and
 * every hash are read from the contract. This module chooses words and colours, and states plainly what is
 * and is not implemented.
 */

export const VERDICT_INFO: Record<ReviewVerdict, { label: string; tone: Tone; headline: string; explain: string }> = {
  ELIGIBLE: {
    label: "ELIGIBLE",
    tone: "eligible",
    headline: "Constitutional review passed.",
    explain:
      "Every materially applicable charter requirement was judged satisfied on the proposal text and VERIFIED evidence. Governance voting is not implemented in this stage.",
  },
  INELIGIBLE: {
    label: "INELIGIBLE",
    tone: "ineligible",
    headline: "The proposal conflicts with the charter.",
    explain:
      "At least one material violation that is not a curable gap was established from the proposal text and/or VERIFIED evidence.",
  },
  REPAIRABLE: {
    label: "REPAIRABLE",
    tone: "warning",
    headline: "The proposal currently fails the charter, but the failure looks curable.",
    explain:
      "Each failing requirement could be cured by changing or supplying specific terms or disclosures without changing the proposal's purpose. The repair workflow is not implemented yet (a later stage).",
  },
  INSUFFICIENT_EVIDENCE: {
    label: "INSUFFICIENT EVIDENCE",
    tone: "warning",
    headline: "No violation was shown, but a required fact is not verified.",
    explain: "Missing proof is not a violation. Verified evidence for the facts below would let the question be decided.",
  },
};

export const FINDING_INFO: Record<FindingKind, { label: string; tone: Tone }> = {
  SATISFIED: { label: "SATISFIED", tone: "eligible" },
  VIOLATED: { label: "VIOLATED", tone: "ineligible" },
  UNCLEAR: { label: "UNCLEAR", tone: "warning" },
  NOT_APPLICABLE: { label: "NOT APPLICABLE", tone: "active" },
};

/** Proposal statuses: SUBMITTED until a finalized review sets one of the four verdicts. */
export function statusTone(status: string): Tone {
  return (VERDICT_INFO as Record<string, { tone: Tone }>)[status]?.tone ?? "active";
}

export function statusLabel(status: string): string {
  return (VERDICT_INFO as Record<string, { label: string }>)[status]?.label ?? status;
}

export interface EvidenceSummary {
  total: number;
  verified: number;
  unverifiable: number;
  sourceUnavailable: number;
  invalidSource: number;
}

export function summarizeEvidence(records: readonly Pick<EvidenceRecord, "status">[]): EvidenceSummary {
  const count = (s: EvidenceRecord["status"]) => records.filter((r) => r.status === s).length;
  return {
    total: records.length,
    verified: count("VERIFIED"),
    unverifiable: count("UNVERIFIABLE"),
    sourceUnavailable: count("SOURCE_UNAVAILABLE"),
    invalidSource: count("INVALID_SOURCE"),
  };
}

/** e.g. "5 records: 3 VERIFIED, 1 UNVERIFIABLE, 1 SOURCE UNAVAILABLE". Zero-count statuses are omitted. */
export function describeEvidence(s: EvidenceSummary): string {
  if (s.total === 0) return "No evidence records.";
  const parts = [
    s.verified && `${s.verified} VERIFIED`,
    s.unverifiable && `${s.unverifiable} UNVERIFIABLE`,
    s.sourceUnavailable && `${s.sourceUnavailable} SOURCE UNAVAILABLE`,
    s.invalidSource && `${s.invalidSource} INVALID SOURCE`,
  ].filter(Boolean);
  return `${s.total} record${s.total === 1 ? "" : "s"}: ${parts.join(", ")}`;
}

export interface RequestGate {
  allowed: boolean;
  /** Why not (when not allowed). */
  reason: string | null;
}

/** Who may request a review. The contract enforces this; the UI only avoids offering a doomed transaction. */
export function reviewRequestGate(input: {
  connection: "disconnected" | "wrong_network" | "ready" | string;
  isProposer: boolean;
  hasReview: boolean;
  status: string;
  activeSections: number;
}): RequestGate {
  if (input.hasReview) return { allowed: false, reason: "This proposal already has a constitutional review. It cannot be reviewed again in this stage." };
  if (input.status !== "SUBMITTED") return { allowed: false, reason: `This proposal is ${input.status} and cannot be reviewed.` };
  if (input.activeSections < 1) return { allowed: false, reason: "The charter in force at submission had no active sections, so there is nothing to review against." };
  if (input.activeSections > 12) return { allowed: false, reason: "The charter in force at submission has too many active sections for one review (maximum 12)." };
  if (input.connection === "disconnected") return { allowed: false, reason: "Connect your wallet to request a review." };
  if (input.connection === "wrong_network") return { allowed: false, reason: "Switch your wallet to StudioNet (chain 61999)." };
  if (!input.isProposer) return { allowed: false, reason: "Only the proposer can request a constitutional review of this proposal." };
  return { allowed: true, reason: null };
}

/** The adverse findings, in charter order, for the verdict-specific explanation. */
export function adverseFindings(findings: readonly ReviewFinding[]): { violated: ReviewFinding[]; unclear: ReviewFinding[] } {
  return {
    violated: findings.filter((f) => f.finding === "VIOLATED"),
    unclear: findings.filter((f) => f.finding === "UNCLEAR"),
  };
}

export const reviewLabel = (r: Pick<ConstitutionalReview, "review_id">) => `CONSTITUTIONAL REVIEW #${String(r.review_id).padStart(3, "0")}`;
