import { describeOutcomeLine, PHASE_LABEL, type TxPhase, type TxState } from "../lib/genlayer/tx";

const ORDER: TxPhase[] = ["ready", "awaiting_wallet", "submitted", "pending", "finalized"];

/**
 * Renders a real TxState. `finalized` appears only for consensus FINALIZED + successful execution.
 * A failed transaction replaces the track with an explicit failure, and still shows what the network
 * and the contract each reported, because "finalized by consensus" and "executed successfully" differ.
 */
export function TransactionTimeline({ tx }: { tx: TxState }) {
  const reached = tx.phase === "failed" ? -1 : ORDER.indexOf(tx.phase);
  const outcome = describeOutcomeLine(tx);
  return (
    <div>
      <ol className="timeline" aria-label="Transaction lifecycle">
        {ORDER.map((p, i) => (
          <li key={p} data-phase={p} data-reached={i <= reached} data-current={i === reached}>
            {PHASE_LABEL[p]}
          </li>
        ))}
      </ol>
      {tx.phase === "failed" && (
        <div role="alert" style={{ color: "var(--state-ineligible)" }}>
          <p className="label" style={{ color: "inherit", margin: "8px 0 0" }}>
            {PHASE_LABEL.failed}
          </p>
          <p style={{ margin: "4px 0 0" }}>{tx.failure?.message}</p>
          {tx.failure?.code && <p className="hash">{tx.failure.code}</p>}
        </div>
      )}
      {outcome && <p className="label">{outcome}</p>}
      {tx.hash && (
        <p className="hash">
          <span className="label">tx </span>
          {tx.hash}
        </p>
      )}
    </div>
  );
}
