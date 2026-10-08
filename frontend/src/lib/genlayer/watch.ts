import { classifyTransaction, type TxState } from "./tx";

export interface WatchDeps {
  /** Wraps `client.getTransaction({ hash })`. Returns `unknown` on purpose: the SDK types are not trusted. */
  getTransaction: (hash: `0x${string}`) => Promise<unknown>;
  sleep: (ms: number) => Promise<void>;
}

export interface WatchOptions {
  intervalMs?: number;
  /** Upper bound on polls. At the 3 s default, 300 polls is about 15 minutes. */
  maxPolls?: number;
  /** Consecutive read failures tolerated before giving up. */
  maxConsecutiveErrors?: number;
}

/**
 * Polls a submitted transaction until it reaches a terminal outcome and returns the final state.
 *
 *  - `pending` is reported once the network actually knows the transaction (and again when its
 *    lifecycle status changes), so SUBMITTED stays visible until then.
 *  - Terminal outcomes come only from `classifyTransaction`, so success requires
 *    FINALIZED consensus AND a successful contract execution.
 *  - CANCELED / UNDETERMINED / timeouts fail immediately rather than polling until a retry limit.
 *  - Read errors are counted and surfaced; they are not swallowed forever.
 */
export async function watchTransaction(
  hash: `0x${string}`,
  deps: WatchDeps,
  onState: (s: TxState) => void,
  opts: WatchOptions = {},
): Promise<TxState> {
  const intervalMs = opts.intervalMs ?? 3000;
  const maxPolls = opts.maxPolls ?? 300;
  const maxConsecutiveErrors = opts.maxConsecutiveErrors ?? 5;

  let consecutiveErrors = 0;
  let lastReportedStatus: string | undefined;

  for (let poll = 0; poll < maxPolls; poll++) {
    await deps.sleep(intervalMs);

    let tx: unknown;
    try {
      tx = await deps.getTransaction(hash);
      consecutiveErrors = 0;
    } catch (err) {
      consecutiveErrors++;
      if (consecutiveErrors >= maxConsecutiveErrors) {
        const failed: TxState = {
          phase: "failed",
          hash,
          failure: {
            category: "unknown",
            message: `Could not read the transaction status ${consecutiveErrors} times in a row. It may still have been processed; check the transaction hash.`,
            debug: err instanceof Error ? err.message : String(err),
          },
        };
        onState(failed);
        return failed;
      }
      continue;
    }

    const state = classifyTransaction(tx, hash);
    if (state.phase === "pending") {
      if (state.networkStatus !== lastReportedStatus) {
        lastReportedStatus = state.networkStatus;
        onState(state);
      }
      continue;
    }
    onState(state);
    return state;
  }

  const timedOut: TxState = {
    phase: "failed",
    hash,
    failure: {
      category: "timeout",
      message: `Still not final after about ${Math.round((maxPolls * intervalMs) / 60000)} minutes. It may still complete; check the transaction hash.`,
    },
  };
  onState(timedOut);
  return timedOut;
}
