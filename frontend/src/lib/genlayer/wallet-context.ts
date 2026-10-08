import { createContext, useContext } from "react";
import type { Address } from "viem";
import type { ChainClient } from "./client";
import type { ConnectionState } from "./tx";

export interface WalletContextValue {
  connection: ConnectionState;
  /** True when no injected wallet (window.ethereum) exists at all. */
  noWallet: boolean;
  address: Address | null;
  /** Wallet's current chain id, if known. */
  chainId: number | null;
  /** Wallet-bound client; null unless connection is "ready". */
  client: ChainClient | null;
  connect: () => Promise<void>;
  switchToStudionet: () => Promise<void>;
  error: string | null;
}

export const WalletContext = createContext<WalletContextValue | null>(null);

export function useWallet(): WalletContextValue {
  const ctx = useContext(WalletContext);
  if (!ctx) throw new Error("useWallet must be used inside <WalletProvider>");
  return ctx;
}
