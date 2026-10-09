import type { ConstitutionalReview, ProposalRevision } from "./genlayer/charterGate";

/**
 * Presentation and pre-flight rules for proposal repair. Nothing here decides anything: admissibility, the lineage, the
 * revision hash and every verdict are read from (or decided by) the contract.
 */

export const MAX_REPAIR_REVISIONS = 5;

/** What a rejected repair means. These come from the contract's deterministic derivation of the agreed assessment. */
export const REPAIR_REJECTION_INFO: Record<string, string> = {
  PURPOSE_CHANGED: "The fundamental purpose changed, so this is not a repair of the same proposal.",
  SCOPE_CHANGED: "The scope changed materially beyond curing the deficiencies.",
  NO_TARGET_ADDRESSED: "None of the repair targets was materially addressed.",
};

/** Turns a failed repair transaction's contract code into an assessment result, or null if it is not a repair rejection. */
export function repairRejection(code: string | undefined): { reason: string; code: string } | null {
  const m = /^EXPECTED:REPAIR_REJECTED:([A-Z_]+)$/.exec(code ?? "");
  if (!m) return null;
  return { code: m[1], reason: REPAIR_REJECTION_INFO[m[1]] ?? "The repair was not admissible." };
}

export const PROPOSAL_FIELDS = [
  { key: "title", label: "Title" },
  { key: "description", label: "Description" },
  { key: "requested_action", label: "Requested action" },
] as const;
export type ProposalField = (typeof PROPOSAL_FIELDS)[number]["key"];

export interface ProposalText {
  title: string;
  description: string;
  requested_action: string;
}

export interface FieldDiff {
  field: ProposalField;
  label: string;
  changed: boolean;
  before: string;
  after: string;
}

const collapse = (s: string) => s.split(/\s+/).filter(Boolean).join(" ");

/** A deterministic field-level comparison (whitespace is not a change, matching the contract's own normalisation). */
export function diffRevision(parent: ProposalText, proposed: ProposalText): FieldDiff[] {
  return PROPOSAL_FIELDS.map(({ key, label }) => ({
    field: key,
    label,
    changed: collapse(parent[key]) !== collapse(proposed[key]),
    before: parent[key],
    after: proposed[key],
  }));
}

export const hasChanges = (diffs: readonly FieldDiff[]) => diffs.some((d) => d.changed);

export interface RepairGate {
  allowed: boolean;
  reason: string | null;
}

/** Who may repair, and when. The contract enforces all of it; the UI only avoids offering a doomed transaction. */
export function repairGate(input: {
  connection: string;
  isProposer: boolean;
  status: string;
  revisionCount: number;
  targets: number;
}): RepairGate {
  if (input.status !== "REPAIRABLE") return { allowed: false, reason: `This proposal is ${input.status}; only a REPAIRABLE proposal can be repaired.` };
  if (input.revisionCount >= MAX_REPAIR_REVISIONS) return { allowed: false, reason: `This proposal has reached the maximum of ${MAX_REPAIR_REVISIONS} repair revisions.` };
  if (input.targets < 1) return { allowed: false, reason: "The latest review lists no repair targets." };
  if (input.connection === "disconnected") return { allowed: false, reason: "Connect your wallet to repair this proposal." };
  if (input.connection === "wrong_network") return { allowed: false, reason: "Switch your wallet to StudioNet (chain 61999)." };
  if (!input.isProposer) return { allowed: false, reason: "Only the proposer can repair this proposal." };
  return { allowed: true, reason: null };
}

export interface LineageEntry {
  revisionNumber: number;
  /** 0 for the original proposal. */
  revisionId: number;
  text: ProposalText;
  addressed: string[];
  createdAt: string;
  revisionHash: string;
  /** The review that judged exactly this revision, if it has one. */
  review: ConstitutionalReview | null;
}

/**
 * The linear lineage: the original proposal (revision 1) then each repair revision, each with the review that judged it.
 * `reviews` is the lineage's review history, oldest first. The contract appends a review only when it finalizes and
 * accepts revision n+1 only after revision n's review was REPAIRABLE, so review k judged revision k+1 (review 0 the original).
 */
export function buildLineage(
  original: ProposalText & { created_at: string },
  revisions: readonly ProposalRevision[],
  reviews: readonly ConstitutionalReview[],
): LineageEntry[] {
  const entries: LineageEntry[] = [
    {
      revisionNumber: 1,
      revisionId: 0,
      text: original,
      addressed: [],
      createdAt: original.created_at,
      revisionHash: "",
      review: reviews[0] ?? null,
    },
  ];
  revisions.forEach((r, i) => {
    entries.push({
      revisionNumber: r.revision_number,
      revisionId: r.revision_id,
      text: r,
      addressed: r.addressed_section_ids,
      createdAt: r.created_at,
      revisionHash: r.revision_hash,
      review: reviews[i + 1] ?? null,
    });
  });
  return entries;
}

/** The latest revision awaiting its constitutional review, if any. */
export const awaitingReview = (entries: readonly LineageEntry[]): LineageEntry | null => {
  const last = entries[entries.length - 1];
  return last && last.revisionId > 0 && last.review === null ? last : null;
};
