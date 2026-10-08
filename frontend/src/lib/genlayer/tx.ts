import { TransactionStatus } from "genlayer-js/types";

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
  | "unknown";

export interface TxState {
  phase: TxPhase;
  hash?: `0x${string}`;
  /** Raw GenLayer status last observed, for display/debugging. Never invented. */
  networkStatus?: TransactionStatus;
  failure?: { category: FailureCategory; message: string };
}

export const IDLE_TX: TxState = { phase: "ready" };

/**
 * Map a verified genlayer-js 1.1.8 TransactionStatus to a UI phase.
 * ACCEPTED is deliberately `pending`: the result is accepted but still inside the
 * appeal window, so it is NOT final. Only FINALIZED is `finalized`.
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
  finalized: "FINALIZED",
  failed: "FAILED",
};
