import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import type { Address } from "viem";
import { CHAIN, CHAIN_ID_HEX, STUDIONET_CHAIN_ID } from "../../config/chain";
import { createWalletClient } from "./client";
import { getInjectedProvider } from "./ethereum";
import { WalletContext, type WalletContextValue } from "./wallet-context";

/**
 * Injected-wallet state. The active account is always re-read from the wallet
 * (accountsChanged / chainChanged); we never assume the first account stays active.
 * Nothing here is persisted: connection state is derived from the wallet on every load.
 */
export function WalletProvider({ children }: { children: ReactNode }) {
  const provider = getInjectedProvider();
  const [address, setAddress] = useState<Address | null>(null);
  const [chainId, setChainId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const syncChain = useCallback(async () => {
    if (!provider) return;
    const hex = (await provider.request({ method: "eth_chainId" })) as string;
    setChainId(parseInt(hex, 16));
  }, [provider]);

  // Silent restore: eth_accounts never prompts, it only returns already-authorised accounts.
  useEffect(() => {
    if (!provider) return;
    let cancelled = false;
    (async () => {
      try {
        const accounts = (await provider.request({ method: "eth_accounts" })) as Address[];
        const hex = (await provider.request({ method: "eth_chainId" })) as string;
        if (cancelled) return;
        setAddress(accounts[0] ?? null);
        setChainId(parseInt(hex, 16));
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      }
    })();
    const onAccounts = (accounts: Address[]) => setAddress(accounts[0] ?? null);
    const onChain = (hex: string) => setChainId(parseInt(hex, 16));
    provider.on?.("accountsChanged", onAccounts as never);
    provider.on?.("chainChanged", onChain as never);
    return () => {
      cancelled = true;
      provider.removeListener?.("accountsChanged", onAccounts as never);
      provider.removeListener?.("chainChanged", onChain as never);
    };
  }, [provider]);

  const connect = useCallback(async () => {
    if (!provider) return;
    setError(null);
    try {
      const accounts = (await provider.request({ method: "eth_requestAccounts" })) as Address[];
      setAddress(accounts[0] ?? null);
      await syncChain();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [provider, syncChain]);

  // Standard EIP-3085 / EIP-3326 requests. We avoid genlayer-js `client.connect()` because it
  // also installs a MetaMask Snap, which this app does not need.
  const switchToStudionet = useCallback(async () => {
    if (!provider) return;
    setError(null);
    try {
      await provider.request({
        method: "wallet_addEthereumChain",
        params: [
          {
            chainId: CHAIN_ID_HEX,
            chainName: CHAIN.name,
            rpcUrls: CHAIN.rpcUrls.default.http,
            nativeCurrency: CHAIN.nativeCurrency,
            blockExplorerUrls: CHAIN.blockExplorers ? [CHAIN.blockExplorers.default.url] : undefined,
          },
        ],
      });
      await provider.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CHAIN_ID_HEX }] });
      await syncChain();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [provider, syncChain]);

  const value = useMemo<WalletContextValue>(() => {
    const connection = !address
      ? "disconnected"
      : chainId !== STUDIONET_CHAIN_ID
        ? "wrong_network"
        : "ready";
    return {
      connection,
      noWallet: !provider,
      address,
      chainId,
      client: connection === "ready" && address ? createWalletClient(address) : null,
      connect,
      switchToStudionet,
      error,
    };
  }, [address, chainId, provider, connect, switchToStudionet, error]);

  return <WalletContext.Provider value={value}>{children}</WalletContext.Provider>;
}
