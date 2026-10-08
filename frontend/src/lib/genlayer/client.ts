import { createClient } from "genlayer-js";
import type { GenLayerChain, GenLayerClient } from "genlayer-js/types";
import type { Address } from "viem";
import { CHAIN } from "../../config/chain";

export type ChainClient = GenLayerClient<GenLayerChain>;

/** Read-only client: no account, no wallet. Reads go straight to the StudioNet RPC. */
export const readClient: ChainClient = createClient({ chain: CHAIN });

/**
 * Wallet-bound client. Passing `account` as an address string (not a local account object)
 * makes genlayer-js 1.1.8 route signing methods through `window.ethereum` (verified in
 * its createClient transport). No private key ever touches this app.
 */
export function createWalletClient(account: Address): ChainClient {
  return createClient({ chain: CHAIN, account });
}
