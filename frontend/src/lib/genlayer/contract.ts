import { TransactionHashVariant, TransactionStatus } from "genlayer-js/types";
import type { CalldataEncodable, TransactionHash } from "genlayer-js/types";
import { CHARTERGATE_ADDRESS } from "../../config/chain";
import type { ChainClient } from "./client";
import { readClient } from "./client";
import {
  classifyError,
  failureFromNetworkStatus,
  phaseFromNetworkStatus,
  type TxState,
} from "./tx";

/**
 * TYPED BOUNDARY, NOT A SCHEMA.
 *
 * The CharterGate contract does not exist yet (Stage 1), so there is deliberately no list of
 * method names here. Stage 8 wires named, typed wrappers on top of these two generic calls
 * after reading the deployed schema with `genlayer schema <address>`.
 */
export class ContractNotDeployedError extends Error {
  constructor() {
    super("CharterGate contract address is not configured (VITE_CHARTERGATE_ADDRESS).");
    this.name = "ContractNotDeployedError";
  }
}

function requireAddress() {
  if (!CHARTERGATE_ADDRESS) throw new ContractNotDeployedError();
  return CHARTERGATE_ADDRESS;
}

/** Read call. LATEST_FINAL = only finalized state; use LATEST_NON_FINAL knowingly. */
export async function readView(
  functionName: string,
  args: CalldataEncodable[] = [],
  client: ChainClient = readClient,
): Promise<CalldataEncodable> {
  return client.readContract({
    address: requireAddress(),
    functionName,
    args,
    transactionHashVariant: TransactionHashVariant.LATEST_FINAL,
  });
}

/**
 * Write call with a real lifecycle. A hash is NOT success: we report `finalized` only once
 * the network reports FINALIZED, and map UNDETERMINED/CANCELED/timeouts to `failed`.
 */
export async function submitWrite(
  client: ChainClient,
  call: { functionName: string; args?: CalldataEncodable[]; value?: bigint },
  onState: (s: TxState) => void,
): Promise<TxState> {
  let state: TxState = { phase: "awaiting_wallet" };
  onState(state);
  try {
    const hash = (await client.writeContract({
      address: requireAddress(),
      functionName: call.functionName,
      args: call.args ?? [],
      value: call.value ?? 0n,
    })) as TransactionHash;
    state = { phase: "submitted", hash };
    onState(state);
    state = { phase: "pending", hash };
    onState(state);

    const receipt = await client.waitForTransactionReceipt({
      hash,
      status: TransactionStatus.FINALIZED,
      interval: 3000,
      retries: 200,
    });
    const status = receipt.status as unknown as TransactionStatus;
    const phase = phaseFromNetworkStatus(status);
    state = {
      phase,
      hash,
      networkStatus: status,
      failure: phase === "failed" ? failureFromNetworkStatus(status) : undefined,
    };
  } catch (err) {
    state = { ...state, phase: "failed", failure: classifyError(err) };
  }
  onState(state);
  return state;
}
