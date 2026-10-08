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
 * One Evidence Vault record, exactly as the contract stored it. Everything except `submitter`,
 * `source_url`, `source_kind`, `claim` and `related_section_id` was produced by the contract and
 * agreed by validators; the submitter cannot supply the status, fact, value or hash.
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
  submit_evidence: { args: 5, write: true },
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
  evidencePerProposal: 25,
  pageSize: 50,
} as const;

export const SECTION_ID_PATTERN = /^[A-Za-z0-9._-]+$/;

export const SOURCE_KINDS: readonly SourceKind[] = ["STATIC_WEB", "DYNAMIC_WEB", "API"];
export const EVIDENCE_STATUSES: readonly EvidenceStatus[] = ["VERIFIED", "UNVERIFIABLE", "SOURCE_UNAVAILABLE", "INVALID_SOURCE"];
export const RETRIEVAL_METHODS: readonly RetrievalMethod[] = ["GET", "RENDER_TEXT"];

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

function asList(raw: unknown): unknown[] {
  if (!Array.isArray(raw)) throw new Error("Expected a list from the contract");
  return raw;
}

// ---- reads (finalized state only; see readView) -----------------------------------------

const view = (name: ViewName, args: CalldataEncodable[] = []) => readView(name, args);

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
 * URL, the kind of source, the claim to check and (optionally) the charter section it relates to.
 * The retrieval method, the extracted fact and value, the status and the hash are produced by the
 * contract and agreed by validators; this app never sends them and cannot override them.
 */
export const submitEvidence = (
  c: ChainClient,
  proposalId: number,
  sourceUrl: string,
  sourceKind: SourceKind,
  claim: string,
  relatedSectionId: string,
  on: OnState,
) => write(c, "submit_evidence", [proposalId, sourceUrl, sourceKind, claim, relatedSectionId], on);
