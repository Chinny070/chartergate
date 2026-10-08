import { studionet } from "genlayer-js/chains";
import type { Address } from "viem";

/** Verified against genlayer-js 1.1.8: `studionet` is a built-in GenLayerChain with id 61999. */
export const CHAIN = studionet;
export const STUDIONET_CHAIN_ID = 61999;

if (CHAIN.id !== STUDIONET_CHAIN_ID) {
  throw new Error(`genlayer-js studionet chain id ${CHAIN.id} != expected ${STUDIONET_CHAIN_ID}`);
}

const rawAddress = (import.meta.env.VITE_CHARTERGATE_ADDRESS ?? "").trim();

/** Placeholder until the contract is deployed manually. `null` means "not deployed". */
export const CHARTERGATE_ADDRESS: Address | null = /^0x[0-9a-fA-F]{40}$/.test(rawAddress)
  ? (rawAddress as Address)
  : null;

export const CHAIN_ID_HEX = `0x${STUDIONET_CHAIN_ID.toString(16)}`;
