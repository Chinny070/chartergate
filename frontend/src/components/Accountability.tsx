import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Docket } from "./primitives";
import { ChainTime, Field } from "./common";
import { TransactionTimeline } from "./TransactionTimeline";
import { MAX_EXECUTION_NOTE, nextOutcomes, PROPOSAL_EXECUTION_INFO, REPORT_INFO, reportFailure, reportGate, UNVERIFIED_NOTE } from "../lib/amendment";
import { getProposalAccountability, reportExecution, type ExecutionOutcome, type Proposal, type ProposalAccountability } from "../lib/genlayer/charterGate";
import { useRead, useTx } from "../lib/genlayer/hooks";
import { sameAddress, shortAddress } from "../lib/format";
import { useWallet } from "../lib/genlayer/wallet-context";

/** The decision, and what the proposer reported about executing it. Pure: every value comes from the contract. */
export function ProposalAccountabilityView({ acc }: { acc: ProposalAccountability }) {
  const info = PROPOSAL_EXECUTION_INFO[acc.execution_state];
  return (
    <div className="stack" aria-label="Execution accountability">
      <div className="row">
        <Badge tone={info.tone}>{info.label}</Badge>
        <Badge tone="warning">NOT VERIFIED BY THE CONTRACT</Badge>
      </div>
      <p className="muted">{info.explain}</p>
      <p className="muted">An ELIGIBLE result means constitutional review passed. It is not a DAO vote, ratification or execution approval.</p>
      <p className="muted">{UNVERIFIED_NOTE}</p>
      {acc.review_id > 0 && (
        <div className="stack">
          <p>
            <span className="label">Decision </span>
            {acc.effective_verdict !== "" ? acc.effective_verdict : "none"} · review #{String(acc.review_id).padStart(3, "0")}
            {acc.appeal_id > 0 ? ` · appellate decision of appeal ${acc.appeal_id}` : ""} · charter v{acc.charter_version}
          </p>
          <div className="label">Ruling hash</div>
          <div className="hash">{acc.ruling_hash}</div>
        </div>
      )}
      {acc.reports.length === 0 ? (
        <p>No execution has been reported.</p>
      ) : (
        <ol className="stack" aria-label="Execution reports" style={{ listStyle: "none", padding: 0 }}>
          {acc.reports.map((r) => {
            const o = REPORT_INFO[r.outcome];
            return (
              <li key={r.report_number}>
                <div className="row" style={{ justifyContent: "space-between" }}>
                  <strong>REPORT {r.report_number}</strong>
                  <Badge tone={o.tone}>{o.label}</Badge>
                </div>
                <p style={{ whiteSpace: "pre-wrap" }}>{r.note}</p>
                <p className="muted">
                  {o.explain} Reported by {shortAddress(r.reporter)} · against the decision above · {r.verified ? "verified" : "not verified"}
                </p>
                <ChainTime label="Reported" value={r.reported_at} />
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}

/** The report form and the record, for one proposal. The transaction state lives above the read so it survives the reload. */
export function ProposalAccountabilityPanel({ proposal, refreshKey = 0 }: { proposal: Proposal; refreshKey?: number }) {
  const wallet = useWallet();
  const { tx, busy, run, reset } = useTx();
  const [tick, setTick] = useState(0);
  const [outcome, setOutcome] = useState<ExecutionOutcome | "">("");
  const [note, setNote] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const read = useRead(() => getProposalAccountability(proposal.proposal_id), [proposal.proposal_id, tick, refreshKey]);

  const acc = read.data;
  // A proposal that was never approved has no execution to account for: show nothing rather than an empty, misleading section.
  if (acc === null) return read.error ? <Docket label="Execution accountability">Could not read the record: {read.error}</Docket> : null;
  if (!acc.approved && acc.reports.length === 0 && tx.phase === "ready") return null;

  const isProposer = sameAddress(wallet.address, proposal.proposer);
  const gate = reportGate({ connection: wallet.connection, isProposer, state: acc.execution_state });
  const options = nextOutcomes(acc.execution_state);
  const first = options.length > 0 ? options[0] : "";
  const chosen: ExecutionOutcome | "" = outcome !== "" && options.includes(outcome) ? outcome : first;
  const valid = chosen !== "" && note.trim().length > 0 && note.trim().length <= MAX_EXECUTION_NOTE;

  async function submit() {
    if (!wallet.client || chosen === "") return;
    setMessage(null);
    const final = await run((c, on) => reportExecution(c, proposal.proposal_id, chosen, note.trim(), on), wallet.client);
    if (final.phase === "finalized") {
      setNote("");
      setOutcome("");
      setTick((t) => t + 1);
    } else {
      setMessage(reportFailure(final.failure?.code));
    }
  }

  return (
    <Docket label="Execution accountability">
      <div className="stack">
        <ProposalAccountabilityView acc={acc} />
        {gate.allowed && (
          <div className="stack">
            <label className="field">
              <span className="label">Report</span>
              <select value={chosen} disabled={busy} onChange={(e) => setOutcome(e.target.value as ExecutionOutcome)}>
                {options.map((o) => (
                  <option key={o} value={o}>
                    {REPORT_INFO[o].label}
                  </option>
                ))}
              </select>
              <span className="muted">{chosen !== "" ? REPORT_INFO[chosen].explain : ""}</span>
            </label>
            <Field label="Note" value={note} onChange={setNote} max={MAX_EXECUTION_NOTE} multiline disabled={busy} hint="What happened. It is recorded as your statement and cannot be edited later." />
            <Button variant="primary" disabled={!valid || busy} onClick={() => void submit()}>
              RECORD REPORT
            </Button>
          </div>
        )}
        {!gate.allowed && gate.reason && <p className="label">{gate.reason}</p>}
        {tx.phase !== "ready" && (
          <div>
            <TransactionTimeline tx={tx} />
            {tx.phase === "finalized" && <p>Finalized and recorded. That records your statement; it does not verify it.</p>}
            {message !== null && <p>{message}</p>}
            {!busy && (
              <Button variant="quiet" onClick={reset}>
                DISMISS
              </Button>
            )}
          </div>
        )}
        <Link to="/accountability" className="label">
          how accountability works
        </Link>
      </div>
    </Docket>
  );
}
