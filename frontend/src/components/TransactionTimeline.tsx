import { PHASE_LABEL, type TxPhase, type TxState } from "../lib/genlayer/tx";

const ORDER: TxPhase[] = ["ready", "awaiting_wallet", "submitted", "pending", "finalized"];

/** Renders a real TxState. The failed phase replaces the track with an explicit failure. */
export function TransactionTimeline({ tx }: { tx: TxState }) {
  const reached = tx.phase === "failed" ? -1 : ORDER.indexOf(tx.phase);
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
        <p role="alert" className="label" style={{ color: "var(--state-ineligible)" }}>
          {PHASE_LABEL.failed}: {tx.failure?.message}
        </p>
      )}
      {tx.hash && (
        <p className="hash">
          <span className="label">tx </span>
          {tx.hash}
        </p>
      )}
    </div>
  );
}
