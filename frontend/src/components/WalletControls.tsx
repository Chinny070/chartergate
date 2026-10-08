import { CHAIN, STUDIONET_CHAIN_ID } from "../config/chain";
import { useWallet } from "../lib/genlayer/wallet-context";
import { Badge, Button } from "./primitives";

const short = (a: string) => `${a.slice(0, 6)}…${a.slice(-4)}`;

export function NetworkBadge() {
  const { connection, chainId } = useWallet();
  if (connection === "disconnected") return <Badge>{CHAIN.name} · {STUDIONET_CHAIN_ID}</Badge>;
  if (connection === "wrong_network")
    return <Badge tone="ineligible">Wrong network{chainId ? ` · ${chainId}` : ""}</Badge>;
  return <Badge tone="eligible">StudioNet · {STUDIONET_CHAIN_ID}</Badge>;
}

export function WalletButton() {
  const { connection, noWallet, address, connect, switchToStudionet } = useWallet();
  if (noWallet) {
    return (
      <Button disabled title="No injected wallet detected in this browser">
        NO WALLET FOUND
      </Button>
    );
  }
  if (connection === "disconnected") {
    return (
      <Button variant="primary" onClick={() => void connect()}>
        CONNECT WALLET
      </Button>
    );
  }
  if (connection === "wrong_network") {
    return (
      <Button variant="primary" onClick={() => void switchToStudionet()}>
        SWITCH TO STUDIONET
      </Button>
    );
  }
  return <Button variant="quiet">{short(address ?? "")}</Button>;
}
