import { TransactionHashVariant } from "genlayer-js/types";
import type { CalldataEncodable, TransactionHash } from "genlayer-js/types";
import { CHARTERGATE_ADDRESS } from "../../config/chain";
import type { ChainClient } from "./client";
import { readClient } from "./client";
import { classifyError, type TxState } from "./tx";
import { watchTransaction } from "./watch";

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
 * Write call with a real lifecycle:
 *   awaiting_wallet -> submitted (hash returned) -> pending (network knows it) -> finalized | failed
 *
 * A hash is NOT success, and neither is consensus FINALIZED: a finalized transaction can still have
 * been rolled back by the contract. `watchTransaction` -> `classifyTransaction` reports `finalized`
 * only for FINALIZED + successful execution; see tx.ts for the verified SDK fields it relies on.
 */
export async function submitWrite(
  client: ChainClient,
  call: { functionName: string; args?: CalldataEncodable[]; value?: bigint },
  onState: (s: TxState) => void,
): Promise<TxState> {
  onState({ phase: "awaiting_wallet" });

  let hash: `0x${string}`;
  try {
    const sent: unknown = await client.writeContract({
      address: requireAddress(),
      functionName: call.functionName,
      args: call.args ?? [],
      value: call.value ?? 0n,
    });
    if (typeof sent !== "string" || !/^0x[0-9a-fA-F]{64}$/.test(sent)) {
      const bad: TxState = {
        phase: "failed",
        failure: { category: "unrecognized", message: "The wallet did not return a valid transaction hash." },
      };
      onState(bad);
      return bad;
    }
    hash = sent as `0x${string}`;
  } catch (err) {
    const failed: TxState = { phase: "failed", failure: classifyError(err) };
    onState(failed);
    return failed;
  }

  onState({ phase: "submitted", hash });
  return watchTransaction(
    hash,
    {
      getTransaction: (h) => client.getTransaction({ hash: h as TransactionHash }),
      sleep: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
    },
    onState,
  );
}
