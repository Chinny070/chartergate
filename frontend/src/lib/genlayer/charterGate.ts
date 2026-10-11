import type { CalldataEncodable } from "genlayer-js/types";
import type { ChainClient } from "./client";
import { readView, submitWrite } from "./contract";
import type { TxState } from "./tx";

/**
 * Typed wrappers for the CharterGate contract (Stages 1 and 2). Every method name and argument below
 * comes from `docs/charter_gate.schema.json` (generated with `genvm-lint schema`); nothing is
 * assumed. Field names stay snake_case to match the contract's `to_dict()` output exactly.
 */

export interface DaoMetadata {
  dao_name: string;
  dao_description: string;
  owner: string;
  charter_version: number;
  created_at: string;
  updated_at: string;
  section_count: number;
  proposal_count: number;
  /** 0 when talking to a pre-Stage-2 contract, which has no such field. */
  evidence_count: number;
}

export interface CharterSection {
  section_id: string;
  title: string;
  body: string;
  active: boolean;
  created_at: string;
  updated_at: string;
}

/** One immutable entry in the charter history. `charter_version` is the version this change produced. */
export interface CharterRevision {
  section_id: string;
  charter_version: number;
  title: string;
  body: string;
  active: boolean;
  changed_at: string;
}

/** Stage 1 only ever produces SUBMITTED. Later statuses belong to later stages. */
export interface Proposal {
  proposal_id: number;
  proposer: string;
  title: string;
  description: string;
  requested_action: string;
  created_at: string;
  charter_version_at_submission: number;
  status: string;
}

/** Evidence verification outcomes. These are NOT constitutional verdicts (that is a later stage). */
export type EvidenceStatus = "VERIFIED" | "UNVERIFIABLE" | "SOURCE_UNAVAILABLE" | "INVALID_SOURCE";
export type SourceKind = "STATIC_WEB" | "DYNAMIC_WEB" | "API";
export type RetrievalMethod = "GET" | "RENDER_TEXT";

/**
 * One Evidence Vault record, exactly as the contract stored it. The submitter chose `source_url`,
 * `source_kind`, `claim`, `related_section_id` and which fact is being asked about (`normalized_fact`,
 * the canonicalised fact key). The status, value, quote, hash and times were produced by the contract
 * and agreed by validators; the submitter cannot supply them.
 */
export interface EvidenceRecord {
  evidence_id: number;
  proposal_id: number;
  submitter: string;
  source_url: string;
  source_kind: SourceKind;
  retrieval_method: RetrievalMethod;
  claim: string;
  status: EvidenceStatus;
  status_reason: string;
  normalized_fact: string;
  normalized_value: string;
  excerpt: string;
  content_hash: string;
  retrieved_at: string;
  created_at: string;
  related_section_id: string;
  related_revision_version: number;
}

/** The four constitutional verdicts. Derived by the contract from the findings; never supplied by the model. */
export type ReviewVerdict = "ELIGIBLE" | "INELIGIBLE" | "REPAIRABLE" | "INSUFFICIENT_EVIDENCE";
export type FindingKind = "SATISFIED" | "VIOLATED" | "UNCLEAR" | "NOT_APPLICABLE";

/** One immutable constitutional review, exactly as stored. `verdict` is NOT the transaction outcome. */
export interface ConstitutionalReview {
  review_id: number;
  proposal_id: number;
  requested_by: string;
  charter_version: number;
  evidence_count_at_review: number;
  evidence_set_hash: string;
  review_context_hash: string;
  verdict: ReviewVerdict;
  finding_count: number;
  primary_section_id: string;
  created_at: string;
  review_hash: string;
}

/** The finding for one charter section (one per active section at the proposal's charter version). */
export interface ReviewFinding {
  section_id: string;
  finding: FindingKind;
  repairable: boolean;
  evidence_ids: number[];
  missing_fact: string;
  rationale: string;
}

/** One immutable repair revision (revision 2 and later). Revision 1 is the original Stage 1 proposal. */
export interface ProposalRevision {
  revision_id: number;
  proposal_id: number;
  revision_number: number;
  /** 0 when the parent is the original proposal (revision 1). */
  parent_revision_id: number;
  source_review_id: number;
  proposer: string;
  title: string;
  description: string;
  requested_action: string;
  charter_version: number;
  addressed_section_ids: string[];
  created_at: string;
  revision_hash: string;
}

/** The current text of a proposal: the original (revision 1, `revision_id` 0) or its latest accepted repair. */
export interface EffectiveProposal {
  proposal_id: number;
  revision_id: number;
  revision_number: number;
  title: string;
  description: string;
  requested_action: string;
  charter_version: number;
  /** "" for revision 1. */
  revision_hash: string;
  status: string;
}

/** A repairable violation from the latest review, with the section text as it read at the proposal's charter version. */
export interface RepairTarget {
  section_id: string;
  title: string;
  body: string;
  rationale: string;
  evidence_ids: number[];
}

export type PrecedentTreatment = "FOLLOWED" | "DISTINGUISHED";

/** One prior section-level ruling that was available to a review (its precedent snapshot, in the contract's order). */
export interface PrecedentCandidate {
  section_id: string;
  /** The exact rule identity: section id + "@" + section revision. */
  rule: string;
  precedent_review_id: number;
  precedent_review_hash: string;
}

/** A precedent a finding cited, and whether it followed or distinguished it. The reason is explanatory prose only. */
export interface PrecedentCitation {
  section_id: string;
  precedent_review_id: number;
  treatment: PrecedentTreatment;
  reason: string;
}

/** What precedent a review saw and used. `precedent_set_hash` is "" when no prior ruling existed under any of its rules. */
export interface ReviewPrecedents {
  review_id: number;
  precedent_set_hash: string;
  candidates: PrecedentCandidate[];
  citations: PrecedentCitation[];
}

/** One prior ruling in full, for inspection: the review, its finding for one section, the text it judged and its cited evidence. */
export interface PrecedentCase {
  review: ConstitutionalReview;
  finding: ReviewFinding;
  rule: string;
  title: string;
  description: string;
  requested_action: string;
  revision_id: number;
  revision_number: number;
  evidence: EvidenceRecord[];
}

/**
 * Every contract method this wrapper can call, with its argument count. `charterGate.schema.test.ts`
 * compares this table to `docs/charter_gate.schema.json`, so a rename or signature change in the
 * contract fails the frontend tests instead of failing at runtime.
 */
export const CONTRACT_METHODS = {
  get_dao_metadata: { args: 0, write: false },
  get_charter_sections_page: { args: 2, write: false },
  get_charter_section_at_version: { args: 2, write: false },
  get_charter_sections_at_version_page: { args: 3, write: false },
  get_charter_revision: { args: 1, write: false },
  get_proposal: { args: 1, write: false },
  get_proposals_page: { args: 2, write: false },
  add_charter_section: { args: 3, write: true },
  update_charter_section: { args: 3, write: true },
  deactivate_charter_section: { args: 1, write: true },
  submit_proposal: { args: 3, write: true },
  get_evidence: { args: 1, write: false },
  get_evidence_count: { args: 0, write: false },
  get_evidence_page: { args: 2, write: false },
  get_proposal_evidence_count: { args: 1, write: false },
  get_proposal_evidence_ids_page: { args: 3, write: false },
  get_proposal_evidence_page: { args: 3, write: false },
  submit_evidence: { args: 6, write: true },
  request_constitutional_review: { args: 1, write: true },
  get_constitutional_review: { args: 1, write: false },
  get_review_for_proposal: { args: 1, write: false },
  get_review_id_for_proposal: { args: 1, write: false },
  get_review_count: { args: 0, write: false },
  get_review_findings_page: { args: 3, write: false },
  get_review_evidence_ids_page: { args: 3, write: false },
  submit_repair_revision: { args: 4, write: true },
  request_revision_review: { args: 1, write: true },
  get_proposal_revision: { args: 1, write: false },
  get_proposal_revision_count: { args: 1, write: false },
  get_proposal_revisions_page: { args: 3, write: false },
  get_effective_proposal: { args: 1, write: false },
  get_review_for_revision: { args: 1, write: false },
  get_review_revision_id: { args: 1, write: false },
  get_proposal_review_count: { args: 1, write: false },
  get_proposal_reviews_page: { args: 3, write: false },
  get_repair_targets: { args: 1, write: false },
  get_review_precedents: { args: 1, write: false },
  get_rule_precedent_count: { args: 1, write: false },
  get_rule_precedents_page: { args: 3, write: false },
  get_precedent_case: { args: 2, write: false },
  request_appeal: { args: 3, write: true },
  request_reasoned_dissent: { args: 1, write: true },
  get_appeal: { args: 1, write: false },
  get_appeal_count: { args: 0, write: false },
  get_appeal_id_for_review: { args: 1, write: false },
  get_appellate_decision: { args: 1, write: false },
  get_appeal_findings_page: { args: 3, write: false },
  get_review_appeal_status: { args: 1, write: false },
  get_appeal_record: { args: 1, write: false },
  get_reasoned_dissent: { args: 1, write: false },
  get_effective_ruling: { args: 1, write: false },
  enable_amendment_governance: { args: 0, write: true },
  propose_amendment: { args: 7, write: true },
  request_amendment_evaluation: { args: 1, write: true },
  approve_amendment: { args: 1, write: true },
  reject_amendment: { args: 1, write: true },
  apply_amendment: { args: 1, write: true },
  close_stale_amendment: { args: 1, write: true },
  report_execution: { args: 3, write: true },
  get_governance_status: { args: 0, write: false },
  get_amendment: { args: 1, write: false },
  get_amendment_count: { args: 0, write: false },
  get_amendments_page: { args: 2, write: false },
  get_amendment_accountability: { args: 1, write: false },
  get_proposal_accountability: { args: 1, write: false },
  get_precedent_overview: { args: 0, write: false },
} as const;

type ViewName = { [K in keyof typeof CONTRACT_METHODS]: (typeof CONTRACT_METHODS)[K]["write"] extends false ? K : never }[keyof typeof CONTRACT_METHODS];
type WriteName = Exclude<keyof typeof CONTRACT_METHODS, ViewName>;

/** Mirrors the contract's validation limits so forms can warn before a wasted transaction. */
export const LIMITS = {
  sectionId: 64,
  sectionTitle: 200,
  sectionBody: 10000,
  proposalTitle: 200,
  proposalDescription: 10000,
  proposalAction: 2000,
  sourceUrl: 500,
  claim: 500,
  factKey: 64,
  evidencePerProposal: 25,
  reviewSections: 12,
  repairRevisions: 5,
  pageSize: 50,
} as const;

export const SECTION_ID_PATTERN = /^[A-Za-z0-9._-]+$/;

export const SOURCE_KINDS: readonly SourceKind[] = ["STATIC_WEB", "DYNAMIC_WEB", "API"];
export const EVIDENCE_STATUSES: readonly EvidenceStatus[] = ["VERIFIED", "UNVERIFIABLE", "SOURCE_UNAVAILABLE", "INVALID_SOURCE"];
export type AppealGround = "CHARTER_MISINTERPRETATION" | "EVIDENCE_MISAPPLICATION" | "PRECEDENT_MISAPPLICATION" | "PROCEDURAL_ERROR";
export type DecisionKind = "AFFIRMED" | "MODIFIED" | "REVERSED";

/** An appeal as filed: the ruling it challenges and the closed record that ruling judged. */
export interface Appeal {
  appeal_id: number;
  review_id: number;
  proposal_id: number;
  /** 0 when the appealed review judged the original proposal. */
  revision_id: number;
  appellant: string;
  ground: AppealGround;
  statement: string;
  original_verdict: ReviewVerdict;
  original_review_hash: string;
  charter_version: number;
  evidence_count: number;
  evidence_set_hash: string;
  precedent_set_hash: string;
  created_at: string;
  appeal_hash: string;
}

/** The appellate decision. It sits ABOVE the original review and never replaces it. */
export interface AppellateDecision {
  appeal_id: number;
  review_id: number;
  verdict: ReviewVerdict;
  decision_kind: DecisionKind;
  finding_count: number;
  appeal_context_hash: string;
  decision_hash: string;
  created_at: string;
}

/** A non-controlling, AI-generated alternative reading of the same closed record. Not a validator vote. */
export interface ReasonedDissent {
  dissent_id: number;
  appeal_id: number;
  decision_hash: string;
  verdict: ReviewVerdict;
  disagreeing_section_ids: string[];
  finding_count: number;
  created_at: string;
  dissent_hash: string;
  findings: ReviewFinding[];
}

/** The whole appellate record in one read. */
export interface AppealRecord {
  appeal: Appeal;
  review: ConstitutionalReview;
  original_findings: ReviewFinding[];
  decision: AppellateDecision;
  findings: ReviewFinding[];
  citations: PrecedentCitation[];
  precedent_candidates: PrecedentCandidate[];
  evidence_ids: number[];
  dissent: ReasonedDissent | null;
}

/** What currently controls a proposal: its latest review, or that review's appellate decision. Both stay readable. */
export interface EffectiveRuling {
  proposal_id: number;
  /** 0 when the proposal has no review yet. */
  review_id: number;
  original_verdict: ReviewVerdict | "";
  appeal_id: number;
  decision_kind: DecisionKind | "";
  effective_verdict: ReviewVerdict | "";
  controlled_by: "NONE" | "REVIEW" | "APPELLATE_DECISION";
  appealable: boolean;
  findings: ReviewFinding[];
  status: string;
}

export interface ReviewAppealStatus {
  review_id: number;
  appealable: boolean;
  blocked_reason: string;
  appeal_id: number;
  dissent_id: number;
}

export type AmendmentAction = "ADD" | "UPDATE" | "DEACTIVATE";
export type AmendmentStatus = "PROPOSED" | "EVALUATED" | "APPROVED" | "REJECTED" | "APPLIED" | "SUPERSEDED";
export type AmendmentExecutionState = "NOT_APPROVED" | "APPROVED_NOT_APPLIED" | "APPROVED_BUT_STALE" | "APPLIED" | "REJECTED" | "SUPERSEDED";

/** A proposed charter change, written against one exact charter version. */
export interface Amendment {
  amendment_id: number;
  proposer: string;
  action: AmendmentAction;
  section_id: string;
  title: string;
  body: string;
  rationale: string;
  base_version: number;
  /** 0 when the amendment does not reference a proposal. */
  source_proposal_id: number;
  status: AmendmentStatus;
  amendment_hash: string;
  created_at: string;
  /** "" until evaluated; the evaluation only advises. */
  eval_verdict: "" | "COMPATIBLE" | "CONFLICTING";
  eval_conflicting_section_ids: string[];
  eval_hash: string;
  evaluated_at: string;
  decided_by: string;
  decided_at: string;
  /** 0 until applied. */
  applied_version: number;
  applied_by: string;
  applied_at: string;
}

export interface AmendmentEvent {
  kind: string;
  actor: string;
  at: string;
  charter_version: number;
}

/** What the contract itself can establish about an amendment's execution. */
export interface AmendmentAccountability {
  amendment: Amendment;
  events: AmendmentEvent[];
  stale: boolean;
  current_charter_version: number;
  execution_state: AmendmentExecutionState;
  contract_verified: boolean;
}

export interface GovernanceStatus {
  governance_enabled: boolean;
  governance_enabled_at: string;
  charter_version: number;
  owner: string;
  amendment_count: number;
}

export type ExecutionOutcome = "ATTEMPTED" | "REPORTED_COMPLETE" | "REPORTED_FAILED";

/** A proposer's report about executing an approved proposal. Self-reported: `verified` is always false. */
export interface ExecutionReport {
  report_number: number;
  proposal_id: number;
  outcome: ExecutionOutcome;
  note: string;
  reporter: string;
  reported_at: string;
  charter_version: number;
  review_id: number;
  appeal_id: number;
  ruling_hash: string;
  verified: boolean;
}

export interface ProposalAccountability {
  proposal_id: number;
  review_id: number;
  appeal_id: number;
  effective_verdict: ReviewVerdict | "";
  ruling_hash: string;
  charter_version: number;
  approved: boolean;
  execution_state: "NOT_APPROVED" | "APPROVED_NOT_REPORTED" | ExecutionOutcome;
  reports: ExecutionReport[];
  verified: boolean;
}

export interface PrecedentRule {
  section_id: string;
  title: string;
  rule: string;
  review_count: number;
  newest_review_ids: number[];
}

export const RETRIEVAL_METHODS: readonly RetrievalMethod[] = ["GET", "RENDER_TEXT"];
export const REVIEW_VERDICTS: readonly ReviewVerdict[] = ["ELIGIBLE", "INELIGIBLE", "REPAIRABLE", "INSUFFICIENT_EVIDENCE"];
export const FINDING_KINDS: readonly FindingKind[] = ["SATISFIED", "VIOLATED", "UNCLEAR", "NOT_APPLICABLE"];

// ---- decoding ---------------------------------------------------------------------------

/** genlayer-js may decode a Python dict as a Map or a plain object; accept both, fail loudly otherwise. */
function asRecord(value: unknown): Record<string, unknown> {
  if (value instanceof Map) return Object.fromEntries(value) as Record<string, unknown>;
  if (value && typeof value === "object" && !Array.isArray(value)) return value as Record<string, unknown>;
  throw new Error(`Expected an object from the contract, got ${typeof value}`);
}

const str = (r: Record<string, unknown>, k: string): string => {
  const v = r[k];
  if (typeof v !== "string") throw new Error(`Contract field "${k}" is not a string`);
  return v;
};

/** Contract ints arrive as number or bigint; every Stage 1 counter is far below 2^53. */
const int = (r: Record<string, unknown>, k: string): number => {
  const v = r[k];
  if (typeof v !== "number" && typeof v !== "bigint") throw new Error(`Contract field "${k}" is not an integer`);
  return Number(v);
};

/** An integer field that an older contract may not have. A present-but-wrong value still fails loudly. */
const optionalInt = (r: Record<string, unknown>, k: string, fallback: number): number =>
  r[k] === undefined ? fallback : int(r, k);

/** A string that must be one of the contract's known values; anything else is a decoding error. */
function oneOf<T extends string>(r: Record<string, unknown>, k: string, allowed: readonly T[]): T {
  const v = str(r, k);
  if (!(allowed as readonly string[]).includes(v)) throw new Error(`Contract field "${k}" has unknown value "${v}"`);
  return v as T;
}

const bool = (r: Record<string, unknown>, k: string): boolean => {
  const v = r[k];
  if (typeof v !== "boolean") throw new Error(`Contract field "${k}" is not a boolean`);
  return v;
};

export function decodeDaoMetadata(raw: unknown): DaoMetadata {
  const r = asRecord(raw);
  return {
    dao_name: str(r, "dao_name"),
    dao_description: str(r, "dao_description"),
    owner: str(r, "owner"),
    charter_version: int(r, "charter_version"),
    created_at: str(r, "created_at"),
    updated_at: str(r, "updated_at"),
    section_count: int(r, "section_count"),
    proposal_count: int(r, "proposal_count"),
    evidence_count: optionalInt(r, "evidence_count", 0),
  };
}

export function decodeSection(raw: unknown): CharterSection {
  const r = asRecord(raw);
  return {
    section_id: str(r, "section_id"),
    title: str(r, "title"),
    body: str(r, "body"),
    active: bool(r, "active"),
    created_at: str(r, "created_at"),
    updated_at: str(r, "updated_at"),
  };
}

export function decodeRevision(raw: unknown): CharterRevision {
  const r = asRecord(raw);
  return {
    section_id: str(r, "section_id"),
    charter_version: int(r, "charter_version"),
    title: str(r, "title"),
    body: str(r, "body"),
    active: bool(r, "active"),
    changed_at: str(r, "changed_at"),
  };
}

export function decodeProposal(raw: unknown): Proposal {
  const r = asRecord(raw);
  return {
    proposal_id: int(r, "proposal_id"),
    proposer: str(r, "proposer"),
    title: str(r, "title"),
    description: str(r, "description"),
    requested_action: str(r, "requested_action"),
    created_at: str(r, "created_at"),
    charter_version_at_submission: int(r, "charter_version_at_submission"),
    status: str(r, "status"),
  };
}

export function decodeEvidence(raw: unknown): EvidenceRecord {
  const r = asRecord(raw);
  return {
    evidence_id: int(r, "evidence_id"),
    proposal_id: int(r, "proposal_id"),
    submitter: str(r, "submitter"),
    source_url: str(r, "source_url"),
    source_kind: oneOf(r, "source_kind", SOURCE_KINDS),
    retrieval_method: oneOf(r, "retrieval_method", RETRIEVAL_METHODS),
    claim: str(r, "claim"),
    status: oneOf(r, "status", EVIDENCE_STATUSES),
    status_reason: str(r, "status_reason"),
    normalized_fact: str(r, "normalized_fact"),
    normalized_value: str(r, "normalized_value"),
    excerpt: str(r, "excerpt"),
    content_hash: str(r, "content_hash"),
    retrieved_at: str(r, "retrieved_at"),
    created_at: str(r, "created_at"),
    related_section_id: str(r, "related_section_id"),
    related_revision_version: int(r, "related_revision_version"),
  };
}

export function decodeReview(raw: unknown): ConstitutionalReview {
  const r = asRecord(raw);
  return {
    review_id: int(r, "review_id"),
    proposal_id: int(r, "proposal_id"),
    requested_by: str(r, "requested_by"),
    charter_version: int(r, "charter_version"),
    evidence_count_at_review: int(r, "evidence_count_at_review"),
    evidence_set_hash: str(r, "evidence_set_hash"),
    review_context_hash: str(r, "review_context_hash"),
    verdict: oneOf(r, "verdict", REVIEW_VERDICTS),
    finding_count: int(r, "finding_count"),
    primary_section_id: str(r, "primary_section_id"),
    created_at: str(r, "created_at"),
    review_hash: str(r, "review_hash"),
  };
}

export function decodeFinding(raw: unknown): ReviewFinding {
  const r = asRecord(raw);
  const ids = r.evidence_ids;
  if (!Array.isArray(ids) || ids.some((i) => typeof i !== "number" && typeof i !== "bigint")) {
    throw new Error('Contract field "evidence_ids" is not a list of integers');
  }
  return {
    section_id: str(r, "section_id"),
    finding: oneOf(r, "finding", FINDING_KINDS),
    repairable: bool(r, "repairable"),
    evidence_ids: ids.map((i) => Number(i)),
    missing_fact: str(r, "missing_fact"),
    rationale: str(r, "rationale"),
  };
}

export function decodeProposalRevision(raw: unknown): ProposalRevision {
  const r = asRecord(raw);
  const ids = r.addressed_section_ids;
  if (!Array.isArray(ids) || ids.some((i) => typeof i !== "string")) {
    throw new Error('Contract field "addressed_section_ids" is not a list of strings');
  }
  return {
    revision_id: int(r, "revision_id"),
    proposal_id: int(r, "proposal_id"),
    revision_number: int(r, "revision_number"),
    parent_revision_id: int(r, "parent_revision_id"),
    source_review_id: int(r, "source_review_id"),
    proposer: str(r, "proposer"),
    title: str(r, "title"),
    description: str(r, "description"),
    requested_action: str(r, "requested_action"),
    charter_version: int(r, "charter_version"),
    addressed_section_ids: ids as string[],
    created_at: str(r, "created_at"),
    revision_hash: str(r, "revision_hash"),
  };
}

export function decodeEffectiveProposal(raw: unknown): EffectiveProposal {
  const r = asRecord(raw);
  return {
    proposal_id: int(r, "proposal_id"),
    revision_id: int(r, "revision_id"),
    revision_number: int(r, "revision_number"),
    title: str(r, "title"),
    description: str(r, "description"),
    requested_action: str(r, "requested_action"),
    charter_version: int(r, "charter_version"),
    revision_hash: str(r, "revision_hash"),
    status: str(r, "status"),
  };
}

export function decodeRepairTarget(raw: unknown): RepairTarget {
  const r = asRecord(raw);
  const ids = r.evidence_ids;
  if (!Array.isArray(ids) || ids.some((i) => typeof i !== "number" && typeof i !== "bigint")) {
    throw new Error('Contract field "evidence_ids" is not a list of integers');
  }
  return {
    section_id: str(r, "section_id"),
    title: str(r, "title"),
    body: str(r, "body"),
    rationale: str(r, "rationale"),
    evidence_ids: ids.map((i) => Number(i)),
  };
}

export const PRECEDENT_TREATMENTS: readonly PrecedentTreatment[] = ["FOLLOWED", "DISTINGUISHED"];

export function decodeReviewPrecedents(raw: unknown): ReviewPrecedents {
  const r = asRecord(raw);
  const list = (k: string): unknown[] => {
    const v = r[k];
    if (!Array.isArray(v)) throw new Error(`Contract field "${k}" is not a list`);
    return v;
  };
  return {
    review_id: int(r, "review_id"),
    precedent_set_hash: str(r, "precedent_set_hash"),
    candidates: list("candidates").map((c) => {
      const x = asRecord(c);
      return {
        section_id: str(x, "section_id"),
        rule: str(x, "rule"),
        precedent_review_id: int(x, "precedent_review_id"),
        precedent_review_hash: str(x, "precedent_review_hash"),
      };
    }),
    citations: list("citations").map((c) => {
      const x = asRecord(c);
      return {
        section_id: str(x, "section_id"),
        precedent_review_id: int(x, "precedent_review_id"),
        treatment: oneOf(x, "treatment", PRECEDENT_TREATMENTS),
        reason: str(x, "reason"),
      };
    }),
  };
}

export function decodePrecedentCase(raw: unknown): PrecedentCase {
  const r = asRecord(raw);
  const evidence = r.evidence;
  if (!Array.isArray(evidence)) throw new Error('Contract field "evidence" is not a list');
  return {
    review: decodeReview(r.review),
    finding: decodeFinding(r.finding),
    rule: str(r, "rule"),
    title: str(r, "title"),
    description: str(r, "description"),
    requested_action: str(r, "requested_action"),
    revision_id: int(r, "revision_id"),
    revision_number: int(r, "revision_number"),
    evidence: evidence.map(decodeEvidence),
  };
}

export const APPEAL_GROUND_IDS: readonly AppealGround[] = ["CHARTER_MISINTERPRETATION", "EVIDENCE_MISAPPLICATION", "PRECEDENT_MISAPPLICATION", "PROCEDURAL_ERROR"];
export const DECISION_KINDS: readonly DecisionKind[] = ["AFFIRMED", "MODIFIED", "REVERSED"];

function listOf(r: Record<string, unknown>, k: string): unknown[] {
  const v = r[k];
  if (!Array.isArray(v)) throw new Error(`Contract field "${k}" is not a list`);
  return v;
}

export function decodeAppeal(raw: unknown): Appeal {
  const r = asRecord(raw);
  return {
    appeal_id: int(r, "appeal_id"),
    review_id: int(r, "review_id"),
    proposal_id: int(r, "proposal_id"),
    revision_id: int(r, "revision_id"),
    appellant: str(r, "appellant"),
    ground: oneOf(r, "ground", APPEAL_GROUND_IDS),
    statement: str(r, "statement"),
    original_verdict: oneOf(r, "original_verdict", REVIEW_VERDICTS),
    original_review_hash: str(r, "original_review_hash"),
    charter_version: int(r, "charter_version"),
    evidence_count: int(r, "evidence_count"),
    evidence_set_hash: str(r, "evidence_set_hash"),
    precedent_set_hash: str(r, "precedent_set_hash"),
    created_at: str(r, "created_at"),
    appeal_hash: str(r, "appeal_hash"),
  };
}

export function decodeAppellateDecision(raw: unknown): AppellateDecision {
  const r = asRecord(raw);
  return {
    appeal_id: int(r, "appeal_id"),
    review_id: int(r, "review_id"),
    verdict: oneOf(r, "verdict", REVIEW_VERDICTS),
    decision_kind: oneOf(r, "decision_kind", DECISION_KINDS),
    finding_count: int(r, "finding_count"),
    appeal_context_hash: str(r, "appeal_context_hash"),
    decision_hash: str(r, "decision_hash"),
    created_at: str(r, "created_at"),
  };
}

export function decodeReasonedDissent(raw: unknown): ReasonedDissent {
  const r = asRecord(raw);
  const sections = listOf(r, "disagreeing_section_ids");
  if (sections.some((x) => typeof x !== "string")) throw new Error('Contract field "disagreeing_section_ids" is not a list of strings');
  return {
    dissent_id: int(r, "dissent_id"),
    appeal_id: int(r, "appeal_id"),
    decision_hash: str(r, "decision_hash"),
    verdict: oneOf(r, "verdict", REVIEW_VERDICTS),
    disagreeing_section_ids: sections as string[],
    finding_count: int(r, "finding_count"),
    created_at: str(r, "created_at"),
    dissent_hash: str(r, "dissent_hash"),
    findings: listOf(r, "findings").map(decodeFinding),
  };
}

export function decodeAppealRecord(raw: unknown): AppealRecord {
  const r = asRecord(raw);
  const evidenceIds = listOf(r, "evidence_ids");
  if (evidenceIds.some((i) => typeof i !== "number" && typeof i !== "bigint")) throw new Error('Contract field "evidence_ids" is not a list of integers');
  const ap = asRecord(r.appeal);
  const precedents = decodeReviewPrecedents({
    review_id: int(ap, "review_id"),
    precedent_set_hash: str(ap, "precedent_set_hash"),
    candidates: listOf(r, "precedent_candidates"),
    citations: listOf(r, "citations"),
  });
  return {
    appeal: decodeAppeal(r.appeal),
    review: decodeReview(r.review),
    original_findings: listOf(r, "original_findings").map(decodeFinding),
    decision: decodeAppellateDecision(r.decision),
    findings: listOf(r, "findings").map(decodeFinding),
    citations: precedents.citations,
    precedent_candidates: precedents.candidates,
    evidence_ids: evidenceIds.map((i) => Number(i)),
    dissent: r.dissent === null || r.dissent === undefined ? null : decodeReasonedDissent(r.dissent),
  };
}

const CONTROLLED_BY = ["NONE", "REVIEW", "APPELLATE_DECISION"] as const;

export function decodeEffectiveRuling(raw: unknown): EffectiveRuling {
  const r = asRecord(raw);
  const verdictOrEmpty = (k: string): ReviewVerdict | "" => (str(r, k) === "" ? "" : oneOf(r, k, REVIEW_VERDICTS));
  return {
    proposal_id: int(r, "proposal_id"),
    review_id: int(r, "review_id"),
    original_verdict: verdictOrEmpty("original_verdict"),
    appeal_id: int(r, "appeal_id"),
    decision_kind: str(r, "decision_kind") === "" ? "" : oneOf(r, "decision_kind", DECISION_KINDS),
    effective_verdict: verdictOrEmpty("effective_verdict"),
    controlled_by: oneOf(r, "controlled_by", CONTROLLED_BY),
    appealable: bool(r, "appealable"),
    findings: listOf(r, "findings").map(decodeFinding),
    status: str(r, "status"),
  };
}

export function decodeReviewAppealStatus(raw: unknown): ReviewAppealStatus {
  const r = asRecord(raw);
  return {
    review_id: int(r, "review_id"),
    appealable: bool(r, "appealable"),
    blocked_reason: str(r, "blocked_reason"),
    appeal_id: int(r, "appeal_id"),
    dissent_id: int(r, "dissent_id"),
  };
}

export const AMENDMENT_ACTIONS: readonly AmendmentAction[] = ["ADD", "UPDATE", "DEACTIVATE"];
export const AMENDMENT_STATUSES: readonly AmendmentStatus[] = ["PROPOSED", "EVALUATED", "APPROVED", "REJECTED", "APPLIED", "SUPERSEDED"];
export const AMENDMENT_EXECUTION_STATES: readonly AmendmentExecutionState[] = ["NOT_APPROVED", "APPROVED_NOT_APPLIED", "APPROVED_BUT_STALE", "APPLIED", "REJECTED", "SUPERSEDED"];
export const EXECUTION_OUTCOMES: readonly ExecutionOutcome[] = ["ATTEMPTED", "REPORTED_COMPLETE", "REPORTED_FAILED"];

export function decodeAmendment(raw: unknown): Amendment {
  const r = asRecord(raw);
  const conflicts = listOf(r, "eval_conflicting_section_ids");
  if (conflicts.some((x) => typeof x !== "string")) throw new Error('Contract field "eval_conflicting_section_ids" is not a list of strings');
  const verdict = str(r, "eval_verdict");
  if (verdict !== "" && verdict !== "COMPATIBLE" && verdict !== "CONFLICTING") throw new Error(`Contract field "eval_verdict" has unknown value "${verdict}"`);
  return {
    amendment_id: int(r, "amendment_id"),
    proposer: str(r, "proposer"),
    action: oneOf(r, "action", AMENDMENT_ACTIONS),
    section_id: str(r, "section_id"),
    title: str(r, "title"),
    body: str(r, "body"),
    rationale: str(r, "rationale"),
    base_version: int(r, "base_version"),
    source_proposal_id: int(r, "source_proposal_id"),
    status: oneOf(r, "status", AMENDMENT_STATUSES),
    amendment_hash: str(r, "amendment_hash"),
    created_at: str(r, "created_at"),
    eval_verdict: verdict,
    eval_conflicting_section_ids: conflicts as string[],
    eval_hash: str(r, "eval_hash"),
    evaluated_at: str(r, "evaluated_at"),
    decided_by: str(r, "decided_by"),
    decided_at: str(r, "decided_at"),
    applied_version: int(r, "applied_version"),
    applied_by: str(r, "applied_by"),
    applied_at: str(r, "applied_at"),
  };
}

function decodeAmendmentEvent(raw: unknown): AmendmentEvent {
  const r = asRecord(raw);
  return { kind: str(r, "kind"), actor: str(r, "actor"), at: str(r, "at"), charter_version: int(r, "charter_version") };
}

export function decodeAmendmentAccountability(raw: unknown): AmendmentAccountability {
  const r = asRecord(raw);
  return {
    amendment: decodeAmendment(r.amendment),
    events: listOf(r, "events").map(decodeAmendmentEvent),
    stale: bool(r, "stale"),
    current_charter_version: int(r, "current_charter_version"),
    execution_state: oneOf(r, "execution_state", AMENDMENT_EXECUTION_STATES),
    contract_verified: bool(r, "contract_verified"),
  };
}

export function decodeGovernanceStatus(raw: unknown): GovernanceStatus {
  const r = asRecord(raw);
  return {
    governance_enabled: bool(r, "governance_enabled"),
    governance_enabled_at: str(r, "governance_enabled_at"),
    charter_version: int(r, "charter_version"),
    owner: str(r, "owner"),
    amendment_count: int(r, "amendment_count"),
  };
}

export function decodeExecutionReport(raw: unknown): ExecutionReport {
  const r = asRecord(raw);
  return {
    report_number: int(r, "report_number"),
    proposal_id: int(r, "proposal_id"),
    outcome: oneOf(r, "outcome", EXECUTION_OUTCOMES),
    note: str(r, "note"),
    reporter: str(r, "reporter"),
    reported_at: str(r, "reported_at"),
    charter_version: int(r, "charter_version"),
    review_id: int(r, "review_id"),
    appeal_id: int(r, "appeal_id"),
    ruling_hash: str(r, "ruling_hash"),
    verified: bool(r, "verified"),
  };
}

export function decodeProposalAccountability(raw: unknown): ProposalAccountability {
  const r = asRecord(raw);
  const verdict = str(r, "effective_verdict");
  const state = str(r, "execution_state");
  if (state !== "NOT_APPROVED" && state !== "APPROVED_NOT_REPORTED" && !(EXECUTION_OUTCOMES as readonly string[]).includes(state)) {
    throw new Error(`Contract field "execution_state" has unknown value "${state}"`);
  }
  return {
    proposal_id: int(r, "proposal_id"),
    review_id: int(r, "review_id"),
    appeal_id: int(r, "appeal_id"),
    effective_verdict: verdict === "" ? "" : oneOf(r, "effective_verdict", REVIEW_VERDICTS),
    ruling_hash: str(r, "ruling_hash"),
    charter_version: int(r, "charter_version"),
    approved: bool(r, "approved"),
    execution_state: state as ProposalAccountability["execution_state"],
    reports: listOf(r, "reports").map(decodeExecutionReport),
    verified: bool(r, "verified"),
  };
}

export function decodePrecedentRule(raw: unknown): PrecedentRule {
  const r = asRecord(raw);
  const ids = listOf(r, "newest_review_ids");
  if (ids.some((i) => typeof i !== "number" && typeof i !== "bigint")) throw new Error('Contract field "newest_review_ids" is not a list of integers');
  return {
    section_id: str(r, "section_id"),
    title: str(r, "title"),
    rule: str(r, "rule"),
    review_count: int(r, "review_count"),
    newest_review_ids: ids.map((i) => Number(i)),
  };
}

function asList(raw: unknown): unknown[] {
  if (!Array.isArray(raw)) throw new Error("Expected a list from the contract");
  return raw;
}

// ---- reads (finalized state only; see readView) -----------------------------------------

// StudioNet allows roughly 30 reads a minute and answers the excess with an error the browser reports as "Failed to fetch".
// A case page asks for the same view from more than one component, so identical in-flight reads share one request, and read
// starts are spaced out so a page does not exhaust the quota (and then its own retries) in its first second.
export const READ_SPACING_MS = import.meta.env.MODE === "test" ? 0 : 1500;
const inflight = new Map<string, Promise<CalldataEncodable>>();
let nextReadSlot = 0;

// The rate-limit error is transient: retry a network-level failure a couple of times with a growing pause before showing an error.
const READ_RETRY_DELAYS_MS = import.meta.env.MODE === "test" ? [] : [4000, 9000];
const isTransientReadError = (e: unknown) => /failed to fetch|networkerror|rate limit|too many requests/i.test(e instanceof Error ? e.message : String(e));

async function readWithRetry(name: ViewName, args: CalldataEncodable[]): Promise<CalldataEncodable> {
  for (let attempt = 0; ; attempt++) {
    try {
      return await readView(name, args);
    } catch (e) {
      const delay = READ_RETRY_DELAYS_MS[attempt];
      if (delay === undefined || !isTransientReadError(e)) throw e;
      await new Promise<void>((resolve) => setTimeout(resolve, delay));
    }
  }
}

const view = (name: ViewName, args: CalldataEncodable[] = []): Promise<CalldataEncodable> => {
  const key = name + JSON.stringify(args, (_k, v) => (typeof v === "bigint" ? v.toString() + "n" : v));
  const shared = inflight.get(key);
  if (shared) return shared;
  const now = Date.now();
  const start = Math.max(now, nextReadSlot);
  nextReadSlot = start + READ_SPACING_MS;
  const wait = start - now;
  const begin = wait > 0 ? new Promise<void>((resolve) => setTimeout(resolve, wait)) : Promise.resolve();
  const request = begin.then(() => readWithRetry(name, args)).finally(() => inflight.delete(key));
  inflight.set(key, request);
  return request;
};

export const getDaoMetadata = async () => decodeDaoMetadata(await view("get_dao_metadata"));

export const getCharterSectionsPage = async (offset = 0, limit: number = LIMITS.pageSize) =>
  asList(await view("get_charter_sections_page", [offset, limit])).map(decodeSection);

/** The charter as it stood at `charterVersion` (e.g. a proposal's `charter_version_at_submission`). */
export const getCharterSectionsAtVersionPage = async (
  charterVersion: number,
  offset = 0,
  limit: number = LIMITS.pageSize,
) => asList(await view("get_charter_sections_at_version_page", [charterVersion, offset, limit])).map(decodeRevision);

export const getCharterSectionAtVersion = async (sectionId: string, charterVersion: number) =>
  decodeRevision(await view("get_charter_section_at_version", [sectionId, charterVersion]));

export const getCharterRevision = async (charterVersion: number) =>
  decodeRevision(await view("get_charter_revision", [charterVersion]));

export const getProposal = async (proposalId: number) =>
  decodeProposal(await view("get_proposal", [proposalId]));

export const getProposalsPage = async (offset = 0, limit: number = LIMITS.pageSize) =>
  asList(await view("get_proposals_page", [offset, limit])).map(decodeProposal);

export const getEvidence = async (evidenceId: number) => decodeEvidence(await view("get_evidence", [evidenceId]));

export const getEvidenceCount = async () => {
  const n = await view("get_evidence_count");
  if (typeof n !== "number" && typeof n !== "bigint") throw new Error("get_evidence_count did not return an integer");
  return Number(n);
};

export const getEvidencePage = async (offset = 0, limit: number = LIMITS.pageSize) =>
  asList(await view("get_evidence_page", [offset, limit])).map(decodeEvidence);

export const getProposalEvidencePage = async (proposalId: number, offset = 0, limit: number = LIMITS.pageSize) =>
  asList(await view("get_proposal_evidence_page", [proposalId, offset, limit])).map(decodeEvidence);

/** 0 when the proposal has not been reviewed. */
export const getReviewIdForProposal = async (proposalId: number) => {
  const n = await view("get_review_id_for_proposal", [proposalId]);
  if (typeof n !== "number" && typeof n !== "bigint") throw new Error("get_review_id_for_proposal did not return an integer");
  return Number(n);
};

export const getConstitutionalReview = async (reviewId: number) =>
  decodeReview(await view("get_constitutional_review", [reviewId]));

export const getReviewFindingsPage = async (reviewId: number, offset = 0, limit: number = LIMITS.pageSize) =>
  asList(await view("get_review_findings_page", [reviewId, offset, limit])).map(decodeFinding);

export const getReviewEvidenceIdsPage = async (reviewId: number, offset = 0, limit: number = LIMITS.pageSize) =>
  asList(await view("get_review_evidence_ids_page", [reviewId, offset, limit])).map((i) => {
    if (typeof i !== "number" && typeof i !== "bigint") throw new Error("Expected an evidence id");
    return Number(i);
  });

export const getEffectiveProposal = async (proposalId: number) =>
  decodeEffectiveProposal(await view("get_effective_proposal", [proposalId]));

export const getProposalRevisionsPage = async (proposalId: number, offset = 0, limit: number = LIMITS.pageSize) =>
  asList(await view("get_proposal_revisions_page", [proposalId, offset, limit])).map(decodeProposalRevision);

/** Every review of the proposal's lineage, oldest first: the review of the original, then of each revision in order. */
export const getProposalReviewsPage = async (proposalId: number, offset = 0, limit: number = LIMITS.pageSize) =>
  asList(await view("get_proposal_reviews_page", [proposalId, offset, limit])).map(decodeReview);

export const getRepairTargets = async (proposalId: number) =>
  asList(await view("get_repair_targets", [proposalId])).map(decodeRepairTarget);

export const getReviewRevisionId = async (reviewId: number) => {
  const n = await view("get_review_revision_id", [reviewId]);
  if (typeof n !== "number" && typeof n !== "bigint") throw new Error("get_review_revision_id did not return an integer");
  return Number(n);
};

/** What precedent a review saw and cited: one bounded read (at most 24 candidates and 24 citations). */
export const getReviewPrecedents = async (reviewId: number) => decodeReviewPrecedents(await view("get_review_precedents", [reviewId]));

/** The whole appellate record in ONE read (appeal, original judgment, decision, findings, precedent treatment, dissent). */
export const getAppealRecord = async (appealId: number) => decodeAppealRecord(await view("get_appeal_record", [appealId]));

/** What currently controls a proposal, in one read. */
export const getEffectiveRuling = async (proposalId: number) => decodeEffectiveRuling(await view("get_effective_ruling", [proposalId]));

/** Charter governance: whether direct owner edits are closed, the current charter version and the amendment count. One read. */
export const getGovernanceStatus = async () => decodeGovernanceStatus(await view("get_governance_status"));

export const getAmendmentsPage = async (offset = 0, limit: number = LIMITS.pageSize) =>
  asList(await view("get_amendments_page", [offset, limit])).map(decodeAmendment);

/** One amendment with its whole lifecycle and what the contract can establish about its execution. One read. */
export const getAmendmentAccountability = async (amendmentId: number) =>
  decodeAmendmentAccountability(await view("get_amendment_accountability", [amendmentId]));

/** What decided a proposal and what its proposer reported about executing it (self-reported, never verified). One read. */
export const getProposalAccountability = async (proposalId: number) => decodeProposalAccountability(await view("get_proposal_accountability", [proposalId]));

/** For every active rule of the current charter: how many reviews interpreted it. One read. */
export const getPrecedentOverview = async () => asList(await view("get_precedent_overview")).map(decodePrecedentRule);

export const getReviewAppealStatus = async (reviewId: number) => decodeReviewAppealStatus(await view("get_review_appeal_status", [reviewId]));

/** One prior section-level ruling in full, in a single read. */
export const getPrecedentCase = async (reviewId: number, sectionId: string) =>
  decodePrecedentCase(await view("get_precedent_case", [reviewId, sectionId]));

// ---- writes -----------------------------------------------------------------------------

type OnState = (s: TxState) => void;
const write = (client: ChainClient, functionName: WriteName, args: CalldataEncodable[], onState: OnState) =>
  submitWrite(client, { functionName, args }, onState);

/** Owner only (enforced by the contract; the UI merely hides the controls from non-owners). */
export const addCharterSection = (c: ChainClient, id: string, title: string, body: string, on: OnState) =>
  write(c, "add_charter_section", [id, title, body], on);

export const updateCharterSection = (c: ChainClient, id: string, title: string, body: string, on: OnState) =>
  write(c, "update_charter_section", [id, title, body], on);

export const deactivateCharterSection = (c: ChainClient, id: string, on: OnState) =>
  write(c, "deactivate_charter_section", [id], on);

/** Any connected wallet. Creates a SUBMITTED proposal; nothing reviews it in Stage 1. */
export const submitProposal = (c: ChainClient, title: string, description: string, action: string, on: OnState) =>
  write(c, "submit_proposal", [title, description, action], on);

/**
 * Proposer only. The caller supplies ONLY what they legitimately control: which proposal, the source
 * URL, the kind of source, the claim to check, WHICH FACT is being asked about (a constrained key such
 * as `team_token_allocation`) and, optionally, the charter section it relates to. The retrieval method,
 * the extracted value, the status and the hash are produced by the contract and agreed by validators;
 * this app never sends them and cannot override them.
 */
export const submitEvidence = (
  c: ChainClient,
  proposalId: number,
  sourceUrl: string,
  sourceKind: SourceKind,
  claim: string,
  factKey: string,
  relatedSectionId: string,
  on: OnState,
) => write(c, "submit_evidence", [proposalId, sourceUrl, sourceKind, claim, factKey, relatedSectionId], on);

/**
 * Proposer only (enforced by the contract). Asks GenLayer to judge the proposal against the charter in force
 * when it was submitted and the VERIFIED evidence that exists now. Takes only the proposal id: the charter
 * version, evidence snapshot and verdict are all determined on-chain, never supplied from here.
 */
export const requestConstitutionalReview = (c: ChainClient, proposalId: number, on: OnState) =>
  write(c, "request_constitutional_review", [proposalId], on);

/**
 * Proposer only. Submits a repair of a proposal whose latest review is REPAIRABLE. Takes only the revised text: the
 * lineage, parent, source review, charter version, repair targets and admissibility are all determined on-chain. GenLayer
 * consensus decides whether it is genuinely a repair; an inadmissible repair rolls back and enters no history.
 */
export const submitRepairRevision = (c: ChainClient, proposalId: number, title: string, description: string, action: string, on: OnState) =>
  write(c, "submit_repair_revision", [proposalId, title, description, action], on);

/** Proposer only. A full constitutional review of an accepted revision (the same Stage 3 adjudication). */
export const requestRevisionReview = (c: ChainClient, revisionId: number, on: OnState) =>
  write(c, "request_revision_review", [revisionId], on);

/**
 * Proposer only. Appeals the proposal's controlling adverse review on the CLOSED record that review judged. Takes only the ground and
 * the statement: the record, the verdict and the disposition are all determined on-chain. New evidence, a newer charter and later
 * precedent are never part of an appeal, and the original review is never changed.
 */
export const requestAppeal = (c: ChainClient, reviewId: number, ground: AppealGround, statement: string, on: OnState) =>
  write(c, "request_appeal", [reviewId, ground, statement], on);

/** Proposer only. Asks for a non-controlling, AI-generated alternative reading of an appeal's closed record. */
export const requestReasonedDissent = (c: ChainClient, appealId: number, on: OnState) => write(c, "request_reasoned_dissent", [appealId], on);

/** Owner only, one way. Afterwards the charter changes only through an approved, applied amendment. */
export const enableAmendmentGovernance = (c: ChainClient, on: OnState) => write(c, "enable_amendment_governance", [], on);

/**
 * Anyone may propose. The charter version is the one the proposer read: if the charter has moved on by the time the contract runs,
 * the amendment is refused as stale rather than being written against a charter nobody saw.
 */
export const proposeAmendment = (
  c: ChainClient,
  action: AmendmentAction,
  sectionId: string,
  title: string,
  body: string,
  baseVersion: number,
  rationale: string,
  sourceProposalId: number,
  on: OnState,
) => write(c, "propose_amendment", [action, sectionId, title, body, baseVersion, rationale, sourceProposalId], on);

/** Proposer or owner. A model advises whether the change is compatible with the rest of the charter. It approves nothing. */
export const requestAmendmentEvaluation = (c: ChainClient, amendmentId: number, on: OnState) => write(c, "request_amendment_evaluation", [amendmentId], on);

/** Owner only, and only for a COMPATIBLE evaluation of an amendment that is not stale. */
export const approveAmendment = (c: ChainClient, amendmentId: number, on: OnState) => write(c, "approve_amendment", [amendmentId], on);

/** The owner rejects, or the proposer withdraws, an open amendment. */
export const rejectAmendment = (c: ChainClient, amendmentId: number, on: OnState) => write(c, "reject_amendment", [amendmentId], on);

/** Proposer or owner. Applies an approved amendment through the charter versioning, only to the exact version it was written against. */
export const applyAmendment = (c: ChainClient, amendmentId: number, on: OnState) => write(c, "apply_amendment", [amendmentId], on);

/** Proposer or owner. Records that an open amendment can no longer apply because the charter moved on. */
export const closeStaleAmendment = (c: ChainClient, amendmentId: number, on: OnState) => write(c, "close_stale_amendment", [amendmentId], on);

/** Proposer only. A self-reported, append-only note about executing an approved proposal. The contract cannot verify it. */
export const reportExecution = (c: ChainClient, proposalId: number, outcome: ExecutionOutcome, note: string, on: OnState) =>
  write(c, "report_execution", [proposalId, outcome, note], on);
