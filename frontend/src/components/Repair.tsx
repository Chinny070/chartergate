import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Docket, ErrorBanner } from "./primitives";
import { Field, ChainTime } from "./common";
import { TransactionTimeline } from "./TransactionTimeline";
import { ReviewResultView } from "./Review";
import {
  awaitingReview,
  buildLineage,
  diffRevision,
  hasChanges,
  MAX_REPAIR_REVISIONS,
  repairGate,
  repairRejection,
  type FieldDiff,
  type LineageEntry,
  type ProposalText,
} from "../lib/repair";
import { statusLabel, statusTone, VERDICT_INFO } from "../lib/review";
import {
  getCharterSectionsAtVersionPage,
  getEffectiveProposal,
  getProposalReviewsPage,
  getProposalRevisionsPage,
  getRepairTargets,
  getReviewEvidenceIdsPage,
  getReviewFindingsPage,
  getReviewPrecedents,
  LIMITS,
  requestRevisionReview,
  submitRepairRevision,
  type CharterRevision,
  type ConstitutionalReview,
  type Proposal,
  type RepairTarget,
} from "../lib/genlayer/charterGate";
import { useRead, useTx } from "../lib/genlayer/hooks";
import { sameAddress, shortAddress } from "../lib/format";
import { useWallet } from "../lib/genlayer/wallet-context";

/** A deterministic field-level comparison between the current revision and the proposed one. */
export function DiffView({ diffs }: { diffs: readonly FieldDiff[] }) {
  return (
    <div className="stack" aria-label="Revision comparison">
      {diffs.map((d) => (
        <div key={d.field} data-changed={d.changed}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className="label">{d.label}</span>
            <Badge tone={d.changed ? "warning" : "active"}>{d.changed ? "CHANGED" : "UNCHANGED"}</Badge>
          </div>
          {d.changed && (
            <div className="grid-2">
              <div>
                <div className="label">Before</div>
                <p style={{ whiteSpace: "pre-wrap" }}>{d.before}</p>
              </div>
              <div>
                <div className="label">After</div>
                <p style={{ whiteSpace: "pre-wrap" }}>{d.after}</p>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

/** What the parent review found: each repairable violation, with the charter text as it read at submission. */
export function RepairTargets({ targets, charterVersion }: { targets: readonly RepairTarget[]; charterVersion: number }) {
  return (
    <div className="stack">
      <div className="label">REPAIR REQUIRED · charter v{charterVersion} governs every revision of this proposal</div>
      {targets.map((t) => (
        <div key={t.section_id} className="finding" data-finding="VIOLATED">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <strong>
              §{t.section_id} {t.title}
            </strong>
            <Badge tone="warning">VIOLATED · REPAIRABLE</Badge>
          </div>
          <p className="muted">{t.rationale}</p>
          <p className="muted" style={{ whiteSpace: "pre-wrap" }}>
            The rule: {t.body}
          </p>
          {t.evidence_ids.length > 0 && (
            <p>
              <span className="label">Evidence </span>
              {t.evidence_ids.map((id, i) => (
                <span key={id}>
                  {i > 0 && ", "}
                  <Link to={`/evidence/${id}`}>#{id}</Link>
                </span>
              ))}
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

/** The revision timeline. Each revision and each review stays independently inspectable; nothing is shown as replaced. */
export function RevisionTimeline({ entries, sections }: { entries: readonly LineageEntry[]; sections: readonly CharterRevision[] }) {
  return (
    <ol className="stack" aria-label="Revision history" style={{ listStyle: "none", padding: 0 }}>
      {entries.map((e) => (
        <li key={e.revisionNumber} data-revision={e.revisionNumber}>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <strong>
              REVISION {e.revisionNumber}
              {e.revisionNumber === 1 ? " · Original proposal" : ""}
            </strong>
            {e.review ? (
              <Badge tone={VERDICT_INFO[e.review.verdict].tone}>Review: {VERDICT_INFO[e.review.verdict].label}</Badge>
            ) : (
              <Badge tone="precedent">AWAITING REVIEW</Badge>
            )}
          </div>
          <div className="muted">
            {e.revisionNumber === 1
              ? "The proposal as first submitted. It is never edited."
              : `Repair addressing ${e.addressed.length ? e.addressed.map((s) => `§${s}`).join(", ") : "no listed target"} · ${shortAddress(e.revisionHash)}`}
          </div>
          <ChainTime label="Created" value={e.createdAt} />
          {e.review && e.review.review_id > 0 && (
            <div className="muted">
              Review #{String(e.review.review_id).padStart(3, "0")} judged revision {e.revisionNumber}, under charter v{e.review.charter_version}.
            </div>
          )}
        </li>
      ))}
      <li className="muted">{sections.length === 0 ? "" : `Charter sections in force: ${sections.filter((s) => s.active).length}`}</li>
    </ol>
  );
}

/** The audit view of one revision's review, loaded on demand. */
function RevisionReview({ review, sections }: { review: ConstitutionalReview; sections: readonly CharterRevision[] }) {
  const read = useRead(
    async () => {
      const [findings, ids, precedents] = await Promise.all([
        getReviewFindingsPage(review.review_id),
        getReviewEvidenceIdsPage(review.review_id),
        getReviewPrecedents(review.review_id),
      ]);
      return { findings, ids, precedents };
    },
    [review.review_id],
  );
  if (read.error) return <ErrorBanner title="Could not read the review">{read.error}</ErrorBanner>;
  if (read.data === null) return <Docket label="Constitutional review">Reading the finalized review from GenLayer…</Docket>;
  return <ReviewResultView review={review} findings={read.data.findings} sections={sections} snapshotIds={read.data.ids} precedents={read.data.precedents} />;
}

/**
 * Repair workspace + revision history for a proposal. The transaction state lives here, above every read, so the
 * timeline and the repair assessment survive the reloads that follow a transaction (the Stage 2 unmount bug).
 */
export function LineagePanel({ proposal, onStatus, refreshKey = 0 }: { proposal: Proposal; onStatus?: (status: string) => void; refreshKey?: number }) {
  const wallet = useWallet();
  const repairTx = useTx();
  const reviewTx = useTx();
  const [tick, setTick] = useState(0);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<ProposalText | null>(null);
  const [outcome, setOutcome] = useState<null | { kind: "accepted"; revision: number } | { kind: "rejected"; reason: string; code: string }>(null);

  const effective = useRead(() => getEffectiveProposal(proposal.proposal_id), [proposal.proposal_id, tick, refreshKey]);
  const revisions = useRead(() => getProposalRevisionsPage(proposal.proposal_id), [proposal.proposal_id, tick, refreshKey]);
  const reviews = useRead(() => getProposalReviewsPage(proposal.proposal_id), [proposal.proposal_id, tick, refreshKey]);
  const status = effective.data?.status ?? proposal.status;
  const targets = useRead(() => (status === "REPAIRABLE" ? getRepairTargets(proposal.proposal_id) : Promise.resolve([])), [proposal.proposal_id, tick, status, refreshKey]);
  const sections = useRead(
    () => getCharterSectionsAtVersionPage(proposal.charter_version_at_submission),
    [proposal.charter_version_at_submission],
  );

  const reloadAll = () => setTick((t) => t + 1);
  const isProposer = sameAddress(wallet.address, proposal.proposer);
  const ready = effective.data !== null && revisions.data !== null && reviews.data !== null && targets.data !== null;
  const readError = effective.error ?? revisions.error ?? reviews.error ?? targets.error;
  const entries = ready ? buildLineage(proposal, revisions.data!, reviews.data!) : [];
  const pending = awaitingReview(entries);
  const current = effective.data;
  const diffs = current && draft ? diffRevision(current, draft) : [];
  const gate = repairGate({
    connection: wallet.connection,
    isProposer,
    status,
    revisionCount: revisions.data?.length ?? 0,
    targets: targets.data?.length ?? 0,
  });

  const liveStatus = effective.data?.status;
  useEffect(() => {
    if (liveStatus) onStatus?.(liveStatus);
  }, [liveStatus, onStatus]);

  async function submit() {
    if (!wallet.client || !draft) return;
    setOutcome(null);
    const final = await repairTx.run(
      (c, on) => submitRepairRevision(c, proposal.proposal_id, draft.title.trim(), draft.description.trim(), draft.requested_action.trim(), on),
      wallet.client,
    );
    if (final.phase === "finalized") {
      setOutcome({ kind: "accepted", revision: (revisions.data?.length ?? 0) + 2 });
      setEditing(false);
      setDraft(null);
      reloadAll();
      return;
    }
    const rej = repairRejection(final.failure?.code);
    if (rej) setOutcome({ kind: "rejected", ...rej });
  }

  async function review(revisionId: number) {
    if (!wallet.client) return;
    const final = await reviewTx.run((c, on) => requestRevisionReview(c, revisionId, on), wallet.client);
    if (final.phase === "finalized") reloadAll();
  }

  const nothingToShow = ready && entries.length === 1 && status !== "REPAIRABLE";
  if (nothingToShow && repairTx.tx.phase === "ready" && reviewTx.tx.phase === "ready") return null;

  return (
    <div className="stack">
      {readError && <ErrorBanner title="Could not read the proposal lineage">{readError}</ErrorBanner>}

      {ready && status === "REPAIRABLE" && (
        <Docket label="Repair required">
          <div className="stack">
            <RepairTargets targets={targets.data!} charterVersion={proposal.charter_version_at_submission} />
            {!editing && gate.allowed && (
              <Button
                variant="primary"
                onClick={() => {
                  setDraft({ title: current!.title, description: current!.description, requested_action: current!.requested_action });
                  setEditing(true);
                  setOutcome(null);
                  repairTx.reset();
                }}
              >
                REPAIR PROPOSAL
              </Button>
            )}
            {!gate.allowed && gate.reason && <p className="label">{gate.reason}</p>}
            <p className="label">
              Repair {(revisions.data?.length ?? 0) + 1} of at most {MAX_REPAIR_REVISIONS}. A repair is a new immutable revision: the original and its review stay exactly as they are.
            </p>
          </div>
        </Docket>
      )}

      {editing && draft && current && (
        <Docket label={`Repair editor · revision ${current.revision_number + 1}`}>
          <div className="stack">
            <p className="muted">
              Governed by charter v{current.charter_version}. A repair must keep the same fundamental purpose and materially address at least one
              repair target. GenLayer judges that; changing wording alone is not a repair.
            </p>
            <div className="grid-2">
              <div className="stack">
                <div className="label">Current revision {current.revision_number}</div>
                <strong>{current.title}</strong>
                <p style={{ whiteSpace: "pre-wrap" }}>{current.description}</p>
                <p style={{ whiteSpace: "pre-wrap" }}>{current.requested_action}</p>
              </div>
              <div className="stack">
                <div className="label">Proposed revision {current.revision_number + 1}</div>
                <Field label="Title" value={draft.title} onChange={(v) => setDraft({ ...draft, title: v })} max={LIMITS.proposalTitle} disabled={repairTx.busy} />
                <Field label="Description" value={draft.description} onChange={(v) => setDraft({ ...draft, description: v })} max={LIMITS.proposalDescription} multiline disabled={repairTx.busy} />
                <Field label="Requested action" value={draft.requested_action} onChange={(v) => setDraft({ ...draft, requested_action: v })} max={LIMITS.proposalAction} multiline disabled={repairTx.busy} />
              </div>
            </div>
            <DiffView diffs={diffs} />
            <div className="row">
              <Button variant="primary" disabled={repairTx.busy || !hasChanges(diffs) || draft.title.trim() === "" || draft.description.trim() === "" || draft.requested_action.trim() === ""} onClick={() => void submit()}>
                SUBMIT REPAIR
              </Button>
              <Button variant="quiet" disabled={repairTx.busy} onClick={() => setEditing(false)}>
                CANCEL
              </Button>
            </div>
            {!hasChanges(diffs) && <p className="label">Nothing has changed yet, so there is nothing to submit.</p>}
            <p className="label">Validators assess the repair themselves, so this can take a minute or more.</p>
          </div>
        </Docket>
      )}

      {repairTx.tx.phase !== "ready" && (
        <Docket label="Repair transaction">
          <TransactionTimeline tx={repairTx.tx} />
          {outcome?.kind === "accepted" && (
            <p>
              Finalized. That is the <strong>transaction</strong>. <strong>Repair assessment: admissible.</strong> Revision {outcome.revision} is now part of this
              proposal's history and awaits its own constitutional review.
            </p>
          )}
          {outcome?.kind === "rejected" && (
            <p>
              Finalized. That is the <strong>transaction</strong>, which the contract rolled back. <strong>Repair rejected:</strong> {outcome.reason} No revision was created.
            </p>
          )}
          {!repairTx.busy && (
            <Button variant="quiet" onClick={repairTx.reset}>
              DISMISS
            </Button>
          )}
        </Docket>
      )}

      {ready && pending && (
        <Docket label={`Revision ${pending.revisionNumber} · awaiting constitutional review`}>
          <div className="stack">
            <p>
              Revision {pending.revisionNumber} was accepted as a repair. That does not make it compliant: it needs a full constitutional review under charter v
              {proposal.charter_version_at_submission}.
            </p>
            <strong>{pending.text.title}</strong>
            {isProposer && wallet.connection === "ready" ? (
              <Button variant="primary" disabled={reviewTx.busy} onClick={() => void review(pending.revisionId)}>
                REQUEST REVIEW OF REVISION {pending.revisionNumber}
              </Button>
            ) : (
              <p className="label">Only the proposer, with a connected wallet on StudioNet, can request this review.</p>
            )}
          </div>
        </Docket>
      )}

      {reviewTx.tx.phase !== "ready" && (
        <Docket label="Revision review transaction">
          <TransactionTimeline tx={reviewTx.tx} />
          {reviewTx.tx.phase === "finalized" && (
            <p>
              Finalized. That is the <strong>transaction</strong>. The <strong>constitutional verdict</strong> for the revision is in its review below.
            </p>
          )}
          {!reviewTx.busy && (
            <Button variant="quiet" onClick={reviewTx.reset}>
              DISMISS
            </Button>
          )}
        </Docket>
      )}

      {ready && entries.length > 1 && (
        <Docket label={`Current revision ${entries[entries.length - 1].revisionNumber}`}>
          <div className="stack">
            <p className="muted">
              The effective text of this proposal is its latest revision. The original (revision 1) above is unchanged and stays readable.
            </p>
            <strong>{entries[entries.length - 1].text.title}</strong>
            <p style={{ whiteSpace: "pre-wrap" }}>{entries[entries.length - 1].text.description}</p>
            <p style={{ whiteSpace: "pre-wrap" }}>{entries[entries.length - 1].text.requested_action}</p>
            <div className="label">Revision hash</div>
            <div className="hash">{entries[entries.length - 1].revisionHash}</div>
          </div>
        </Docket>
      )}

      {ready && entries.length > 1 && (
        <Docket label="Revision history">
          <RevisionTimeline entries={entries} sections={sections.data ?? []} />
          <div className="stack">
            {entries
              .filter((e) => e.revisionId > 0)
              .map((e, i) => (
                <details key={`diff-${e.revisionNumber}`}>
                  <summary>Revision {e.revisionNumber}: what changed from revision {e.revisionNumber - 1}</summary>
                  <DiffView diffs={diffRevision(entries[i].text, e.text)} />
                </details>
              ))}
            {entries
              .filter((e) => e.revisionId > 0 && e.review)
              .map((e) => (
                <details key={e.revisionNumber}>
                  <summary>
                    Revision {e.revisionNumber}: review #{String(e.review!.review_id).padStart(3, "0")} · {statusLabel(e.review!.verdict)}
                  </summary>
                  <RevisionReview review={e.review!} sections={sections.data ?? []} />
                </details>
              ))}
            <p className="muted">
              Earlier revisions and reviews are never replaced: revision 1 may be {statusLabel("REPAIRABLE")} while a later revision is
              {" "}
              {statusLabel("ELIGIBLE")}. Both facts stand.
            </p>
            <Badge tone={statusTone(status)}>CURRENT STATUS · {statusLabel(status)}</Badge>
          </div>
        </Docket>
      )}
    </div>
  );
}
