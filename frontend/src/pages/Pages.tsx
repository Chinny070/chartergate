import { Link, useParams } from "react-router-dom";
import { CHARTERGATE_ADDRESS, CHAIN, STUDIONET_CHAIN_ID } from "../config/chain";
import { Badge, Docket, ErrorBanner } from "../components/primitives";
import { ReadBoundary } from "../components/common";
import { getDaoMetadata } from "../lib/genlayer/charterGate";
import { useRead } from "../lib/genlayer/hooks";
import { TransactionTimeline } from "../components/TransactionTimeline";
import { IDLE_TX } from "../lib/genlayer/tx";
import { useWallet } from "../lib/genlayer/wallet-context";

export function Home() {
  const { connection, noWallet, error } = useWallet();
  const meta = useRead(getDaoMetadata);
  return (
    <div className="stack">
      <section className="hero">
        <h1>
          Your DAO has rules.
          <br />
          Now it can <em>interpret</em> them.
        </h1>
        <p>
          A constitutional review layer for proposals, evidence, appeals, precedent, and execution
          on GenLayer.
        </p>
        <div className="row">
          <Badge tone="warning">Stage 2 · charter, proposals + evidence vault</Badge>
        </div>
      </section>

      <ReadBoundary read={meta}>
        {(m) => (
          <Docket label={`Charter overview · ${m.dao_name}`}>
            <p>{m.dao_description}</p>
            <div className="row">
              <Badge tone="final">Charter v{m.charter_version}</Badge>
              <Badge>{m.section_count} sections</Badge>
              <Badge>{m.proposal_count} proposals</Badge>
              <Badge>{m.evidence_count} evidence</Badge>
            </div>
          </Docket>
        )}
      </ReadBoundary>

      <div className="grid-2">
        <Docket label="Foundation status">
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            <li>
              Network: {CHAIN.name} (chain {STUDIONET_CHAIN_ID})
            </li>
            <li>
              Wallet:{" "}
              {noWallet
                ? "no injected wallet detected"
                : connection === "disconnected"
                  ? "not connected"
                  : connection === "wrong_network"
                    ? "connected, wrong network"
                    : "connected, ready"}
            </li>
            <li>Contract: {CHARTERGATE_ADDRESS ?? "not deployed (VITE_CHARTERGATE_ADDRESS unset)"}</li>
          </ul>
        </Docket>
        <Docket label="Transaction lifecycle">
          <TransactionTimeline tx={IDLE_TX} />
        </Docket>
      </div>
      {error && <ErrorBanner title="Wallet error">{error}</ErrorBanner>}
    </div>
  );
}

/** Honest placeholder: routes exist, features are planned for later stages. */
export function Planned({ title, stage }: { title: string; stage: string }) {
  const { id } = useParams();
  return (
    <div className="stack">
      <h1 style={{ fontSize: "clamp(2rem, 6vw, 4rem)" }}>{title}</h1>
      {id && <p className="hash">ref: {id}</p>}
      <Docket label="Not implemented">
        This page is planned for {stage}. So far CharterGate implements the charter, proposals and the evidence vault.
      </Docket>
      <Link to="/" className="label">
        ← back to court
      </Link>
    </div>
  );
}
