import { useCallback, useEffect, useEffectEvent, useState } from "react";
import type { ChainClient } from "./client";
import { ContractNotDeployedError } from "./contract";
import { IDLE_TX, type TxState } from "./tx";

export interface ReadState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  /** True when the failure is simply "no contract address configured yet". */
  notDeployed: boolean;
  reload: () => void;
}

type Settled<T> = { key: string; data: T | null; error: unknown };

/**
 * Reads on-chain state. Nothing is cached anywhere but React memory; a refresh re-reads the chain.
 * `loading` is derived (the last settled result belongs to an older key), so no setState runs
 * synchronously inside the effect.
 */
export function useRead<T>(load: () => Promise<T>, deps: unknown[] = []): ReadState<T> {
  const [tick, setTick] = useState(0);
  const [settled, setSettled] = useState<Settled<T> | null>(null);
  const key = `${tick}:${JSON.stringify(deps)}`;
  const doLoad = useEffectEvent(load);

  useEffect(() => {
    let cancelled = false;
    doLoad().then(
      (data) => {
        if (!cancelled) setSettled({ key, data, error: null });
      },
      (error: unknown) => {
        if (!cancelled) setSettled({ key, data: null, error });
      },
    );
    return () => {
      cancelled = true;
    };
  }, [key]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  const current = settled?.key === key ? settled : null;
  const notDeployed = current?.error instanceof ContractNotDeployedError;
  const error =
    current?.error && !notDeployed
      ? current.error instanceof Error
        ? current.error.message
        : String(current.error)
      : null;
  return { data: current?.data ?? null, loading: current === null, error, notDeployed, reload };
}

/** Tracks one write's lifecycle. `run` resolves with the final TxState; reads must be reloaded by the caller. */
export function useTx() {
  const [tx, setTx] = useState<TxState>(IDLE_TX);
  const busy = tx.phase === "awaiting_wallet" || tx.phase === "submitted" || tx.phase === "pending";

  const run = useCallback(
    (send: (client: ChainClient, onState: (s: TxState) => void) => Promise<TxState>, client: ChainClient) =>
      send(client, setTx),
    [],
  );
  const reset = useCallback(() => setTx(IDLE_TX), []);
  return { tx, busy, run, reset };
}
