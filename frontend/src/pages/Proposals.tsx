import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Badge, Button, Docket, EmptyState, ErrorBanner } from "../components/primitives";
import { ChainTime, Field, ReadBoundary } from "../components/common";
import { EvidenceList, SubmitEvidenceForm } from "../components/Evidence";
import { shortAddress } from "../lib/format";
import { TransactionTimeline } from "../components/TransactionTimeline";
import {
  getCharterSectionsAtVersionPage,
  getProposal,
  getProposalEvidencePage,
  getProposalsPage,
  LIMITS,
  submitProposal,
  type EvidenceRecord,
  type Proposal,
} from "../lib/genlayer/charterGate";
import { useRead, useTx } from "../lib/genlayer/hooks";
import { useWallet } from "../lib/genlayer/wallet-context";

/** Stage 1 proposals only reach SUBMITTED; this label is deliberately not a verdict. */
const StatusBadge = ({ status }: { status: string }) => <Badge tone="active">{status}</Badge>;

export function ProposalsPage() {
  const read = useRead(() => getProposalsPage(0, LIMITS.pageSize));
  return (
    <div className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h1 style={{ fontSize: "clamp(2rem, 6vw, 4rem)" }}>Proposal docket</h1>
        <Link to="/submit" className="btn btn--primary" style={{ textDecoration: "none" }}>
          SUBMIT PROPOSAL
        </Link>
      </div>
      <ReadBoundary read={read}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="No proposals yet">Submitted proposals will appear here.</EmptyState>
          ) : (
            <div className="docket-rows">
              {[...list].reverse().map((p) => (
                <Link key={p.proposal_id} to={`/proposals/${p.proposal_id}`} className="docket-row">
                  <span className="label">CASE {String(p.proposal_id).padStart(3, "0")}</span>
                  <strong>{p.title}</strong>
                  <span className="label">{shortAddress(p.proposer)}</span>
                  <span className="label">charter v{p.charter_version_at_submission}</span>
                  <StatusBadge status={p.status} />
                </Link>
              ))}
            </div>
          )
        }
      </ReadBoundary>
      <p className="label">Open a case to submit evidence. Eligibility verdicts, precedent and appeals are not implemented yet (later stages).</p>
    </div>
  );
}

export function ProposalDetailPage() {
  const { id } = useParams();
  const num = Number(id);
  const valid = Number.isInteger(num) && num >= 1;
  const read = useRead(() => (valid ? getProposal(num) : Promise.reject(new Error("Invalid proposal id"))), [num]);

  return (
    <div className="stack">
      <ReadBoundary read={read}>
        {(p: Proposal) => (
          <>
            <div className="label">CASE {String(p.proposal_id).padStart(3, "0")}</div>
            <h1 style={{ fontSize: "clamp(2rem, 6vw, 4rem)" }}>{p.title}</h1>
            <div className="grid-2">
              <div className="stack">
                <Docket label="Description">
                  <p style={{ whiteSpace: "pre-wrap" }}>{p.description}</p>
                </Docket>
                <Docket label="Requested action">
                  <p style={{ whiteSpace: "pre-wrap" }}>{p.requested_action}</p>
                </Docket>
                <CharterAtSubmission version={p.charter_version_at_submission} />
                <ProposalEvidence proposal={p} />
                <Docket label="Constitutional review">
                  Not implemented. Judgment, precedent and appeals arrive in later stages. Evidence can be attached above,
                  but nothing yet decides whether this proposal complies with the charter.
                </Docket>
              </div>
              <Docket label="Status">
                <div className="stack">
                  <StatusBadge status={p.status} />
                  <div>
                    <div className="label">Proposer</div>
                    <div className="hash">{p.proposer}</div>
                  </div>
                  <div>
                    <div className="label">Submitted under charter</div>
                    <div>v{p.charter_version_at_submission}</div>
                  </div>
                  <ChainTime label="Submitted" value={p.created_at} />
                </div>
              </Docket>
            </div>
          </>
        )}
      </ReadBoundary>
      <Link to="/proposals" className="label">
        ← all proposals
      </Link>
    </div>
  );
}

/** Evidence attached to this proposal, plus the form to add more (proposer only). */
function ProposalEvidence({ proposal }: { proposal: Proposal }) {
  const read = useRead(() => getProposalEvidencePage(proposal.proposal_id), [proposal.proposal_id]);
  // Keep showing the last records while a reload is in flight. Otherwise the loading state unmounts the
  // form right after a transaction finalizes and the submitter never sees the "Finalized" result.
  const [shown, setShown] = useState<{ id: number; records: EvidenceRecord[] } | null>(null);
  if (read.data !== null && shown?.records !== read.data) setShown({ id: proposal.proposal_id, records: read.data });
  const stale = shown?.id === proposal.proposal_id ? shown.records : null;
  const records = read.data ?? stale;
  return (
    <div className="stack">
      <h2 style={{ fontSize: "1.8rem" }}>Evidence</h2>
      {records === null ? (
        <ReadBoundary read={read}>{() => null}</ReadBoundary>
      ) : (
        <>
          <EvidenceList records={[...records].reverse()} empty="No evidence has been attached to this proposal yet." />
          <SubmitEvidenceForm proposal={proposal} evidenceCount={records.length} onFinalized={read.reload} />
        </>
      )}
    </div>
  );
}

/** The charter text that applied when this proposal was submitted, rebuilt from on-chain history. */
function CharterAtSubmission({ version }: { version: number }) {
  const read = useRead(() => getCharterSectionsAtVersionPage(version, 0, LIMITS.pageSize), [version]);
  return (
    <Docket label={`Charter in force at submission · v${version}`}>
      <ReadBoundary read={read}>
        {(sections) =>
          sections.length === 0 ? (
            <p>The charter had no sections when this proposal was submitted.</p>
          ) : (
            <div className="stack">
              {sections.map((s) => (
                <div key={s.section_id}>
                  <div className="label">
                    §{s.section_id} {s.active ? "" : "· deactivated"}
                  </div>
                  <strong>{s.title}</strong>
                  <p style={{ whiteSpace: "pre-wrap" }}>{s.body}</p>
                </div>
              ))}
            </div>
          )
        }
      </ReadBoundary>
    </Docket>
  );
}

export function SubmitProposalPage() {
  const wallet = useWallet();
  const { tx, busy, run, reset } = useTx();
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [action, setAction] = useState("");
  const [submittedOk, setSubmittedOk] = useState(false);

  const fits = (v: string, max: number) => v.trim().length > 0 && v.trim().length <= max;
  const valid =
    fits(title, LIMITS.proposalTitle) && fits(description, LIMITS.proposalDescription) && fits(action, LIMITS.proposalAction);

  async function submit() {
    if (!wallet.client) return;
    setSubmittedOk(false);
    const final = await run((c, on) => submitProposal(c, title, description, action, on), wallet.client);
    if (final.phase === "finalized") {
      setTitle("");
      setDescription("");
      setAction("");
      setSubmittedOk(true);
    }
  }

  return (
    <div className="stack">
      <h1 style={{ fontSize: "clamp(2rem, 6vw, 4rem)" }}>Submit proposal</h1>
      {wallet.connection !== "ready" && (
        <ErrorBanner title="Wallet not ready">
          {wallet.connection === "wrong_network"
            ? "Switch your wallet to StudioNet (chain 61999) to submit."
            : "Connect a wallet to submit a proposal."}
        </ErrorBanner>
      )}
      <Docket label="Proposal">
        <div className="stack">
          <Field label="Title" value={title} onChange={setTitle} max={LIMITS.proposalTitle} disabled={busy} />
          <Field label="Description" value={description} onChange={setDescription} max={LIMITS.proposalDescription} multiline disabled={busy} />
          <Field label="Requested action" value={action} onChange={setAction} max={LIMITS.proposalAction} multiline disabled={busy} />
          <Button variant="primary" disabled={!valid || busy || wallet.connection !== "ready"} onClick={() => void submit()}>
            SUBMIT PROPOSAL
          </Button>
        </div>
      </Docket>
      {tx.phase !== "ready" && (
        <Docket label="Transaction">
          <TransactionTimeline tx={tx} />
          {submittedOk && (
            <p>
              Finalized on GenLayer. <Link to="/proposals">View the docket</Link>.
            </p>
          )}
          {!busy && (
            <Button variant="quiet" onClick={reset}>
              DISMISS
            </Button>
          )}
        </Docket>
      )}
      <p className="label">
        A submitted proposal is stored as SUBMITTED under the current charter version. Nothing reviews it yet.
      </p>
    </div>
  );
}
