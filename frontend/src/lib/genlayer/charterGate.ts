import type { CalldataEncodable } from "genlayer-js/types";
import type { ChainClient } from "./client";
import { readView, submitWrite } from "./contract";
import type { TxState } from "./tx";

/**
 * Typed wrappers for the Stage 1 CharterGate contract. Every method name and argument below
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
  pageSize: 50,
} as const;

export const SECTION_ID_PATTERN = /^[A-Za-z0-9._-]+$/;

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
