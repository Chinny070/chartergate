import { TransactionStatus, transactionResultNumberToName, transactionsStatusNumberToName } from "genlayer-js/types";

/**
 * TWO DIFFERENT QUESTIONS, NEVER COLLAPSED
 *
 *  1. Consensus: did GenLayer's validators reach a final decision on this transaction?
 *     (`status` / `statusName`: PENDING ... ACCEPTED ... FINALIZED, plus the consensus `result`.)
 *  2. Execution: did the Intelligent Contract's code actually succeed, or did it roll back / crash?
 *
 * A transaction can be consensus FINALIZED and still have been rolled back by the contract
 * (live example: a non-owner calling an owner-only method is FINALIZED with a rollback payload
 * `EXPECTED:NOT_OWNER`, and no state changes). The UI therefore reports success only for
 * `FINALIZED + execution success`; see `classifyTransaction`.
 *
 * VERIFIED SDK FACTS (genlayer-js 1.1.8, checked against its types and against live StudioNet):
 *  - `client.getTransaction({hash})` returns a `GenLayerTransaction` with `statusName`, `status`
 *    and `result` (a number, mapped by `transactionResultNumberToName`).
 *  - The typed `txExecutionResultName` field is populated ONLY on non-Studio chains. On StudioNet
 *    it is `undefined`.
 *  - On StudioNet the execution outcome is in `consensus_data.leader_receipt[]`, the entry with
 *    `mode === "leader"`: `execution_result` ("SUCCESS" | "ERROR") and `result.status`
 *    ("return" | "rollback" | "contract_error") with `result.payload`.
 *  - The SDK types `LeaderReceipt.result` as `string` and `execution_result` as `string`, but the
 *    live `result` is an object. The SDK types are therefore NOT trusted here: every field is read
 *    as `unknown` and validated, and anything unrecognised fails closed.
 *  - `waitForTransactionReceipt` returns a simplified receipt that renames/drops fields, so the
 *    outcome is read from `getTransaction` instead.
 */

/** Wallet/network readiness, independent of any one transaction. */
export type ConnectionState = "disconnected" | "wrong_network" | "ready";

/** Lifecycle of a single write. `ready` is the idle state before a write starts. */
export type TxPhase =
  | "ready"
  | "awaiting_wallet"
  | "submitted"
  | "pending"
  | "finalized"
  | "failed";

export type FailureCategory =
  | "wallet_rejected"
  | "wallet_network"
  | "consensus"
  | "execution"
  | "rolled_back"
  | "contract_error"
  | "timeout"
  | "unrecognized"
  | "unknown";

/** What the contract's code did. Independent of consensus finality. */
export type ExecutionOutcome =
  | { kind: "success" }
  /** The contract deliberately rejected the call (a UserError). `code` is e.g. `EXPECTED:NOT_OWNER`. */
  | { kind: "rolled_back"; code: string }
  /** The contract crashed (uncaught exception / VM error). `detail` is e.g. `exit_code 1`. */
  | { kind: "contract_error"; detail: string; stderr?: string }
  /** The response was not in a shape we recognise. Treated as failure. */
  | { kind: "unrecognized"; reason: string };

export interface TxFailure {
  category: FailureCategory;
  /** Short, safe, user-facing text. Never a stack trace. */
  message: string;
  /** Stable machine code when the contract supplied one, e.g. `EXPECTED:NOT_OWNER`. */
  code?: string;
  /** Truncated technical detail kept for debugging; not shown in the normal UI. */
  debug?: string;
}

export interface TxState {
  phase: TxPhase;
  hash?: `0x${string}`;
  /** Raw GenLayer lifecycle status last observed. Never invented. */
  networkStatus?: TransactionStatus;
  /** Consensus result name (e.g. MAJORITY_AGREE), when the network reported one. */
  consensusResult?: string;
  /** Execution outcome, only once the transaction is final. */
  execution?: ExecutionOutcome;
  failure?: TxFailure;
}

export const IDLE_TX: TxState = { phase: "ready" };

/**
 * CONSENSUS-LEVEL phase only. `FINALIZED` here means validators finalized the transaction; it does
 * NOT mean the contract succeeded. Do not use this to decide success; use `classifyTransaction`.
 * ACCEPTED is `pending`: accepted but still inside the appeal window, so it is not final.
 */
export function phaseFromNetworkStatus(status: TransactionStatus): TxPhase {
  switch (status) {
    case TransactionStatus.FINALIZED:
      return "finalized";
    case TransactionStatus.UNDETERMINED:
    case TransactionStatus.CANCELED:
    case TransactionStatus.LEADER_TIMEOUT:
    case TransactionStatus.VALIDATORS_TIMEOUT:
      return "failed";
    default:
      return "pending";
  }
}

export function failureFromNetworkStatus(status: TransactionStatus): TxState["failure"] {
  return {
    category: "consensus",
    message: `Network reported ${status}; the transaction did not reach a final result.`,
  };
}

/** EIP-1193 user rejection is code 4001. */
export function classifyError(err: unknown): NonNullable<TxState["failure"]> {
  const e = err as { code?: number; message?: string } | undefined;
  const message = e?.message ?? String(err);
  if (e?.code === 4001 || /user rejected|user denied/i.test(message)) {
    return { category: "wallet_rejected", message: "Signature request was rejected in the wallet." };
  }
  if (/Wallet is on chain/i.test(message)) return { category: "wallet_network", message };
  return { category: "unknown", message };
}

export const PHASE_LABEL: Record<TxPhase, string> = {
  ready: "READY",
  awaiting_wallet: "SIGNATURE REQUESTED",
  submitted: "SUBMITTED",
  pending: "PENDING CONSENSUS",
  finalized: "FINALIZED · SUCCESS",
  failed: "FAILED",
};

// ---- reading an untrusted GenLayerTransaction ---------------------------------------------

const isRecord = (v: unknown): v is Record<string, unknown> =>
  typeof v === "object" && v !== null && !Array.isArray(v);

const TERMINAL_FAILURE_STATUSES: ReadonlySet<string> = new Set([
  TransactionStatus.UNDETERMINED,
  TransactionStatus.CANCELED,
  TransactionStatus.LEADER_TIMEOUT,
  TransactionStatus.VALIDATORS_TIMEOUT,
]);

const KNOWN_STATUSES: ReadonlySet<string> = new Set(Object.values(TransactionStatus));

/** Consensus results that mean validators agreed. Anything else on a finalized tx is a failure. */
const AGREEING_RESULTS: ReadonlySet<string> = new Set(["AGREE", "MAJORITY_AGREE"]);

function readStatusName(tx: Record<string, unknown>): string | undefined {
  if (typeof tx.statusName === "string") return tx.statusName;
  if (typeof tx.status === "string") return tx.status;
  if (typeof tx.status === "number") {
    const name = (transactionsStatusNumberToName as Record<string, string | undefined>)[String(tx.status)];
    if (name) return name;
  }
  return undefined;
}

function readConsensusResult(tx: Record<string, unknown>): string | undefined {
  if (typeof tx.resultName === "string") return tx.resultName;
  if (typeof tx.result === "number") {
    return (transactionResultNumberToName as Record<string, string | undefined>)[String(tx.result)];
  }
  return undefined;
}

const clip = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}…[truncated]` : s);

/**
 * Reads the contract execution outcome from a transaction. Pure; never throws. Anything it does
 * not positively recognise as a success is NOT a success.
 */
export function readExecutionOutcome(tx: unknown): ExecutionOutcome {
  if (!isRecord(tx)) return { kind: "unrecognized", reason: "transaction response is not an object" };

  // Typed SDK field. Populated on non-Studio chains only (undefined on StudioNet).
  if (tx.txExecutionResultName !== undefined) {
    switch (tx.txExecutionResultName) {
      case "FINISHED_WITH_RETURN":
        return { kind: "success" };
      case "FINISHED_WITH_ERROR":
        return { kind: "rolled_back", code: "" };
      default:
        return {
          kind: "unrecognized",
          reason: `execution result ${JSON.stringify(tx.txExecutionResultName)} is not a finished outcome`,
        };
    }
  }

  // StudioNet: the leader's receipt.
  const consensus = tx.consensus_data;
  const receipts = isRecord(consensus) ? consensus.leader_receipt : undefined;
  if (!Array.isArray(receipts)) return { kind: "unrecognized", reason: "no leader receipt in transaction" };
  const leader = receipts.find((r): r is Record<string, unknown> => isRecord(r) && r.mode === "leader");
  if (!leader) return { kind: "unrecognized", reason: "no entry with mode 'leader' in leader receipt" };

  const exec = leader.execution_result;
  const result = leader.result;
  const status = isRecord(result) ? result.status : undefined;
  const payload = isRecord(result) ? result.payload : undefined;

  if (exec === "SUCCESS") {
    return status === "return"
      ? { kind: "success" }
      : { kind: "unrecognized", reason: `execution_result SUCCESS but result.status is ${JSON.stringify(status)}` };
  }
  if (exec === "ERROR") {
    if (status === "rollback") return { kind: "rolled_back", code: typeof payload === "string" ? payload : "" };
    if (status === "contract_error") {
      const stderr = isRecord(leader.genvm_result) ? leader.genvm_result.stderr : undefined;
      return {
        kind: "contract_error",
        detail: typeof payload === "string" ? payload : "",
        stderr: typeof stderr === "string" && stderr !== "" ? clip(stderr, 600) : undefined,
      };
    }
    return { kind: "unrecognized", reason: `execution_result ERROR with result.status ${JSON.stringify(status)}` };
  }
  return { kind: "unrecognized", reason: `execution_result is ${JSON.stringify(exec)}` };
}

/** User-facing text for this contract's stable `EXPECTED:` codes. Unknown codes are shown verbatim. */
export function describeContractError(code: string): string {
  if (code === "") return "The contract rejected the transaction.";
  if (code === "EXPECTED:NOT_OWNER") return "Only the contract owner can do this.";
  if (code === "EXPECTED:NOT_PROPOSER") return "Only the proposer can do this.";
  if (code === "EXPECTED:REPAIR_NOT_ALLOWED") return "This proposal cannot be repaired now: only a REPAIRABLE proposal with no pending revision can.";
  if (code === "EXPECTED:REVISION_LIMIT_REACHED") return "This proposal has reached its maximum number of repair revisions.";
  if (code === "EXPECTED:REVISION_UNCHANGED") return "The revision is identical to the current text, so there is nothing to repair.";
  const rejected = /^EXPECTED:REPAIR_REJECTED:(.+)$/.exec(code);
  if (rejected) return "Repair rejected: the proposed revision is not an admissible repair of this proposal.";
  const typeMatch = /^EXPECTED:INVALID_TYPE:(.+)$/.exec(code);
  if (typeMatch) return `The value for "${typeMatch[1]}" has the wrong type.`;
  const rangeMatch = /^EXPECTED:INTEGER_OUT_OF_RANGE:(.+)$/.exec(code);
  if (rangeMatch) return `The value for "${rangeMatch[1]}" is out of range.`;
  if (code.startsWith("EXPECTED:")) return `The contract rejected the transaction: ${code.slice("EXPECTED:".length)}.`;
  return `The contract rejected the transaction: ${clip(code, 120)}`;
}

/**
 * The single place that turns a `getTransaction` response into a user-facing state.
 *
 *   not final                              -> pending
 *   UNDETERMINED / CANCELED / *_TIMEOUT    -> failed (consensus)
 *   FINALIZED + validators did not agree   -> failed (consensus)
 *   FINALIZED + execution success          -> finalized   (the ONLY success)
 *   FINALIZED + rollback                   -> failed (rolled_back)
 *   FINALIZED + contract crash             -> failed (contract_error)
 *   anything unrecognised                  -> failed (unrecognized)   [fail closed]
 */
export function classifyTransaction(tx: unknown, hash: `0x${string}`): TxState {
  if (!isRecord(tx)) {
    return {
      phase: "failed",
      hash,
      failure: { category: "unrecognized", message: "The network returned an unreadable transaction." },
    };
  }
  const statusName = readStatusName(tx);
  if (statusName === undefined || !KNOWN_STATUSES.has(statusName)) {
    return {
      phase: "failed",
      hash,
      failure: {
        category: "unrecognized",
        message: "The network reported a transaction status this app does not recognise.",
        debug: `status=${JSON.stringify(statusName)}`,
      },
    };
  }
  const networkStatus = statusName as TransactionStatus;
  const consensusResult = readConsensusResult(tx);

  if (TERMINAL_FAILURE_STATUSES.has(networkStatus)) {
    return {
      phase: "failed",
      hash,
      networkStatus,
      consensusResult,
      failure: failureFromNetworkStatus(networkStatus) ?? { category: "consensus", message: networkStatus },
    };
  }
  if (networkStatus !== TransactionStatus.FINALIZED) {
    return { phase: "pending", hash, networkStatus, consensusResult };
  }

  // FINALIZED. Consensus finality is established; now decide what the contract did.
  if (consensusResult === undefined || !AGREEING_RESULTS.has(consensusResult)) {
    return {
      phase: "failed",
      hash,
      networkStatus,
      consensusResult,
      failure: {
        category: "consensus",
        message: "Validators did not agree on this transaction's result.",
        debug: `consensus result=${JSON.stringify(consensusResult)}`,
      },
    };
  }

  const execution = readExecutionOutcome(tx);
  const base = { hash, networkStatus, consensusResult, execution };
  switch (execution.kind) {
    case "success":
      return { phase: "finalized", ...base };
    case "rolled_back":
      return {
        phase: "failed",
        ...base,
        failure: {
          category: "rolled_back",
          message: describeContractError(execution.code),
          code: execution.code || undefined,
        },
      };
    case "contract_error":
      return {
        phase: "failed",
        ...base,
        failure: {
          category: "contract_error",
          message: `The contract failed while executing this transaction${execution.detail ? ` (${clip(execution.detail, 60)})` : ""}. No changes were made.`,
          debug: execution.stderr,
        },
      };
    case "unrecognized":
      return {
        phase: "failed",
        ...base,
        failure: {
          category: "unrecognized",
          message: "The transaction was finalized, but its outcome could not be confirmed as successful, so it is treated as failed.",
          debug: execution.reason,
        },
      };
  }
}

/** One line showing consensus and execution side by side, e.g. `network FINALIZED · execution ROLLED BACK`. */
export function describeOutcomeLine(tx: TxState): string | null {
  if (!tx.networkStatus) return null;
  const parts = [`network ${tx.networkStatus}`];
  if (tx.consensusResult) parts.push(`consensus ${tx.consensusResult}`);
  if (tx.execution) {
    const e = tx.execution;
    parts.push(
      e.kind === "success"
        ? "execution SUCCESS"
        : e.kind === "rolled_back"
          ? `execution ROLLED BACK${e.code ? ` (${e.code})` : ""}`
          : e.kind === "contract_error"
            ? "execution CONTRACT ERROR"
            : "execution UNRECOGNIZED",
    );
  }
  return parts.join(" · ");
}
