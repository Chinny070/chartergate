import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Docket, ErrorBanner } from "./primitives";
import { ChainTime, Field } from "./common";
import { TransactionTimeline } from "./TransactionTimeline";
import {
  checkSourceUrl,
  describeRetrieval,
  displayHost,
  evidenceLabel,
  reasonText,
  shortHash,
  SOURCE_KIND_INFO,
  STATUS_INFO,
} from "../lib/evidence";
import {
  getCharterSectionsAtVersionPage,
  LIMITS,
  SOURCE_KINDS,
  submitEvidence,
  type EvidenceRecord,
  type Proposal,
  type SourceKind,
} from "../lib/genlayer/charterGate";
import { useRead, useTx } from "../lib/genlayer/hooks";
import { sameAddress, shortAddress } from "../lib/format";
import { useWallet } from "../lib/genlayer/wallet-context";

const isHttpUrl = (u: string) => /^https?:\/\//i.test(u);

export function EvidenceStatusBadge({ record }: { record: EvidenceRecord }) {
  const s = STATUS_INFO[record.status];
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

export function RetrievalBadge({ record }: { record: Pick<EvidenceRecord, "source_kind" | "retrieval_method"> }) {
  return <Badge tone="active">{describeRetrieval(record).badge}</Badge>;
}

/** What the source actually says, labelled by whether it was verified. */
function factLine(r: EvidenceRecord): { label: string; text: string } {
  if (r.normalized_fact === "") return { label: "Extracted fact", text: "Nothing was recorded from this source." };
  const label = r.status === "VERIFIED" ? "Verified fact" : "What the source says";
  return { label, text: `${r.normalized_fact} = ${r.normalized_value}` };
}

/**
 * One Evidence Vault record, as an evidence stamp on a docket. `detail` adds the hash explanation and
 * the full provenance. The protocol timestamp (not browser time) is the source of every date shown.
 */
export function EvidenceCard({ record, detail = false, charterText }: { record: EvidenceRecord; detail?: boolean; charterText?: string }) {
  const status = STATUS_INFO[record.status];
  const retrieval = describeRetrieval(record);
  const fact = factLine(record);
  return (
    <article className={`evidence evidence--${record.status.toLowerCase()}`} aria-label={evidenceLabel(record.evidence_id)}>
      <header className="evidence__head">
        {detail ? (
          <h2 className="evidence__no">{evidenceLabel(record.evidence_id)}</h2>
        ) : (
          <Link className="evidence__no" to={`/evidence/${record.evidence_id}`}>
            {evidenceLabel(record.evidence_id)}
          </Link>
        )}
        <EvidenceStatusBadge record={record} />
        <RetrievalBadge record={record} />
      </header>

      <dl className="kv">
        <div>
          <dt>Source</dt>
          <dd>
            {isHttpUrl(record.source_url) ? (
              <a href={record.source_url} target="_blank" rel="noreferrer noopener">
                {displayHost(record.source_url)}
              </a>
            ) : (
              displayHost(record.source_url)
            )}
            {detail && <div className="hash">{record.source_url}</div>}
          </dd>
        </div>
        <div>
          <dt>Retrieval</dt>
          <dd>
            <strong>{retrieval.badge}</strong>
            {detail && <div className="muted">{retrieval.detail}</div>}
          </dd>
        </div>
        <div>
          <dt>Retrieved</dt>
          <dd>
            <ChainTime label="" value={record.retrieved_at} />
          </dd>
        </div>
        <div>
          <dt>Claim</dt>
          <dd>{record.claim}</dd>
        </div>
        <div>
          <dt>{fact.label}</dt>
          <dd>
            <span className="hash">{fact.text}</span>
            {record.excerpt && <blockquote className="quote">“{record.excerpt}”</blockquote>}
          </dd>
        </div>
        <div>
          <dt>Charter relationship</dt>
          <dd>
            {record.related_section_id === "" ? (
              "None"
            ) : (
              <>
                §{record.related_section_id}
                <span className="muted"> · as it read at charter v{record.related_revision_version}</span>
                {charterText && <div className="muted">{charterText}</div>}
              </>
            )}
          </dd>
        </div>
        <div>
          <dt>Evidence hash</dt>
          <dd className="hash">{detail ? record.content_hash : shortHash(record.content_hash)}</dd>
        </div>
        <div>
          <dt>Status</dt>
          <dd>
            <strong>{status.label}</strong>
            <div className="muted">
              {status.explain} {reasonText(record.status_reason)}
            </div>
          </dd>
        </div>
        {detail && (
          <>
            <div>
              <dt>Submitted by</dt>
              <dd className="hash">{record.submitter}</dd>
            </div>
            <div>
              <dt>Proposal</dt>
              <dd>
                <Link to={`/proposals/${record.proposal_id}`}>Case {String(record.proposal_id).padStart(3, "0")}</Link>
              </dd>
            </div>
          </>
        )}
      </dl>
    </article>
  );
}

/** What this record does and does not prove: shown on the detail page so the hash is never oversold. */
export function EvidenceNotes() {
  return (
    <Docket label="What this record proves">
      <ul className="notes">
        <li>
          GenLayer itself fetched the source (the submitter did not paste it), and several validators independently re-fetched it
          and agreed on the result.
        </li>
        <li>
          <strong>The time is protocol time</strong>: when the transaction was processed. It is not a time written on the web page,
          and the page may have been published earlier.
        </li>
        <li>
          <strong>The evidence hash is a hash of the normalised evidence</strong> (source, retrieval method, status, fact, value and
          charter relationship). It is <strong>not</strong> a hash of the web page, and the page itself is not archived. It does not
          prove what the page contained, only what the validators agreed they read.
        </li>
        <li>This is evidence, not a ruling. Nothing here decides whether a proposal complies with the charter.</li>
      </ul>
    </Docket>
  );
}

export function EvidenceList({ records, empty }: { records: EvidenceRecord[]; empty: string }) {
  if (records.length === 0) return <Docket label="Evidence">{empty}</Docket>;
  return (
    <div className="stack">
      {records.map((r) => (
        <EvidenceCard key={r.evidence_id} record={r} />
      ))}
    </div>
  );
}

/**
 * Submit evidence for a proposal. The submitter supplies only what they control (URL, kind, claim and
 * an optional charter section). The status, fact, value, hash and timestamps are produced by the
 * contract and agreed by validators; none of them is ever sent from here.
 */
export function SubmitEvidenceForm({ proposal, evidenceCount, onFinalized }: { proposal: Proposal; evidenceCount: number; onFinalized: () => void }) {
  const wallet = useWallet();
  const { tx, busy, run, reset } = useTx();
  const [url, setUrl] = useState("");
  const [kind, setKind] = useState<SourceKind>("STATIC_WEB");
  const [claim, setClaim] = useState("");
  const [section, setSection] = useState("");
  const [done, setDone] = useState(false);

  // Sections as they read when THIS proposal was submitted, never the latest charter.
  const sections = useRead(
    () => getCharterSectionsAtVersionPage(proposal.charter_version_at_submission),
    [proposal.charter_version_at_submission],
  );
  const options = (sections.data ?? []).filter((s) => s.active);

  const urlProblem = url.trim() === "" ? null : checkSourceUrl(url);
  const claimOk = claim.trim().length > 0 && claim.trim().length <= LIMITS.claim;
  const isProposer = sameAddress(wallet.address, proposal.proposer);
  const full = evidenceCount >= LIMITS.evidencePerProposal;

  const blocker =
    wallet.connection === "disconnected"
      ? "Connect your wallet to submit evidence."
      : wallet.connection === "wrong_network"
        ? "Switch your wallet to StudioNet (chain 61999)."
        : !isProposer
          ? `Only the proposer (${shortAddress(proposal.proposer)}) can attach evidence to this proposal.`
          : full
            ? `This proposal already has the maximum of ${LIMITS.evidencePerProposal} evidence records.`
            : null;

  const canSubmit = !busy && blocker === null && url.trim() !== "" && urlProblem === null && claimOk;

  async function submit() {
    if (!wallet.client) return;
    setDone(false);
    const final = await run(
      (c, on) => submitEvidence(c, proposal.proposal_id, url.trim(), kind, claim.trim(), section, on),
      wallet.client,
    );
    if (final.phase === "finalized") {
      setDone(true);
      setUrl("");
      setClaim("");
      onFinalized();
    }
  }

  return (
    <Docket label="Submit evidence">
      <div className="stack">
        <p className="muted">
          You provide the source and the claim to check. CharterGate then fetches the source <strong>through GenLayer</strong>, and
          validators re-fetch it independently. The extracted fact, status and hash come from the contract, not from you.
        </p>
        {blocker && <ErrorBanner title="Cannot submit yet">{blocker}</ErrorBanner>}

        <Field label="Source URL" value={url} onChange={setUrl} max={LIMITS.sourceUrl} hint="public http(s) address" disabled={busy} />
        {urlProblem && (
          <p role="alert" className="label" style={{ color: "var(--state-ineligible)" }}>
            {urlProblem.message}
          </p>
        )}

        <fieldset className="kinds" disabled={busy}>
          <legend className="label">Source type</legend>
          {SOURCE_KINDS.map((k) => (
            <label key={k} className="kind" data-selected={kind === k}>
              <input type="radio" name="source-kind" value={k} checked={kind === k} onChange={() => setKind(k)} />
              <span>
                <strong>{SOURCE_KIND_INFO[k].label}</strong>
                <span className="muted">{SOURCE_KIND_INFO[k].help}</span>
              </span>
            </label>
          ))}
        </fieldset>

        <Field label="Claim to check" value={claim} onChange={setClaim} max={LIMITS.claim} multiline hint="what the source should show" disabled={busy} />

        <label className="field">
          <span className="label">Related charter rule (optional)</span>
          <select value={section} onChange={(e) => setSection(e.target.value)} disabled={busy || sections.loading}>
            <option value="">None</option>
            {options.map((s) => (
              <option key={s.section_id} value={s.section_id}>
                §{s.section_id} · {s.title}
              </option>
            ))}
          </select>
          <span className="field__meta">As the charter read at v{proposal.charter_version_at_submission}, when this proposal was submitted.</span>
        </label>

        <Button variant="primary" disabled={!canSubmit} onClick={() => void submit()}>
          SUBMIT EVIDENCE
        </Button>
        <p className="label">Validators fetch the source themselves, so this can take a minute or more.</p>
      </div>

      {tx.phase !== "ready" && (
        <div style={{ marginTop: 16 }}>
          <TransactionTimeline tx={tx} />
          {done && (
            <p>
              Finalized. The new record appears below; <strong>check its status</strong>. A successful transaction can still record
              SOURCE UNAVAILABLE or UNVERIFIABLE.
            </p>
          )}
          {!busy && (
            <Button variant="quiet" onClick={reset}>
              DISMISS
            </Button>
          )}
        </div>
      )}
    </Docket>
  );
}
