import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Docket, ErrorBanner } from "./primitives";
import { ChainTime } from "./common";
import { PrecedentMemory } from "./Precedent";
import { TransactionTimeline } from "./TransactionTimeline";
import {
  adverseFindings,
  describeEvidence,
  FINDING_INFO,
  reviewLabel,
  reviewRequestGate,
  summarizeEvidence,
  VERDICT_INFO,
} from "../lib/review";
import {
  getCharterSectionsAtVersionPage,
  getConstitutionalReview,
  getProposalEvidencePage,
  getReviewEvidenceIdsPage,
  getReviewFindingsPage,
  getReviewIdForProposal,
  getReviewPrecedents,
  requestConstitutionalReview,
  type CharterRevision,
  type ConstitutionalReview,
  type Proposal,
  type ReviewFinding,
  type ReviewPrecedents,
} from "../lib/genlayer/charterGate";
import { useRead, useTx } from "../lib/genlayer/hooks";
import { sameAddress } from "../lib/format";
import { useWallet } from "../lib/genlayer/wallet-context";

const sectionTitle = (sections: readonly CharterRevision[], id: string) => sections.find((s) => s.section_id === id)?.title ?? "";

function EvidenceRefs({ ids }: { ids: readonly number[] }) {
  if (ids.length === 0) return <span className="muted">Evidence: none cited (decided on the proposal text)</span>;
  return (
    <span>
      <span className="label">Evidence </span>
      {ids.map((id, i) => (
        <span key={id}>
          {i > 0 && ", "}
          <Link to={`/evidence/${id}`}>#{id}</Link>
        </span>
      ))}
    </span>
  );
}

export function FindingRow({ finding, sections }: { finding: ReviewFinding; sections: readonly CharterRevision[] }) {
  const info = FINDING_INFO[finding.finding];
  return (
    <div className="finding" data-finding={finding.finding}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <strong>
          §{finding.section_id} {sectionTitle(sections, finding.section_id)}
        </strong>
        <Badge tone={info.tone}>{info.label}</Badge>
      </div>
      {finding.finding === "VIOLATED" && (
        <p className="label">{finding.repairable ? "REPAIRABLE: this failure looks curable" : "NOT REPAIRABLE: a conflict with the rule as written"}</p>
      )}
      {finding.finding === "UNCLEAR" && (
        <p>
          <span className="label">Undetermined for lack of verified evidence: </span>
          <span className="hash">{finding.missing_fact}</span>
        </p>
      )}
      {finding.finding !== "NOT_APPLICABLE" && <EvidenceRefs ids={finding.evidence_ids} />}
      {finding.rationale !== "" && <p className="muted">{finding.rationale}</p>}
    </div>
  );
}

/**
 * The audit view of one stored review. Pure: every value comes from the contract. The verdict is the
 * constitutional outcome and is NOT the transaction outcome: a review transaction that finalized and
 * executed successfully can carry any of the four verdicts.
 */
export function ReviewResultView({
  review,
  findings,
  sections,
  snapshotIds,
  precedents = null,
}: {
  review: ConstitutionalReview;
  findings: readonly ReviewFinding[];
  sections: readonly CharterRevision[];
  snapshotIds: readonly number[];
  /** The precedent snapshot and citations of this review; null when not loaded. */
  precedents?: ReviewPrecedents | null;
}) {
  const info = VERDICT_INFO[review.verdict];
  const { violated, unclear } = adverseFindings(findings);
  return (
    <Docket label={reviewLabel(review)}>
      <div className="stack">
        <div>
          <div className="label">Constitutional verdict</div>
          <div className="row">
            <Badge tone={info.tone}>{info.label}</Badge>
          </div>
          <p>
            <strong>{info.headline}</strong> {info.explain}
          </p>
        </div>

        {review.verdict === "INELIGIBLE" && violated.length > 0 && (
          <p>
            Violated rule{violated.length > 1 ? "s" : ""}: {violated.map((f) => `§${f.section_id} ${sectionTitle(sections, f.section_id)}`).join("; ")}.
          </p>
        )}
        {review.verdict === "REPAIRABLE" && violated.length > 0 && (
          <p>
            Currently failing: {violated.map((f) => `§${f.section_id} ${sectionTitle(sections, f.section_id)}`).join("; ")}. The proposer can submit a repair as a new revision.
          </p>
        )}
        {review.verdict === "INSUFFICIENT_EVIDENCE" && unclear.length > 0 && (
          <p>
            Undetermined for lack of VERIFIED evidence: {unclear.map((f) => `§${f.section_id} ${sectionTitle(sections, f.section_id)} (${f.missing_fact})`).join("; ")}.
          </p>
        )}

        <div className="grid-2">
          <div>
            <div className="label">Charter applied</div>
            <div>Version {review.charter_version}</div>
            <div className="muted">The charter in force when the proposal was submitted, not the current charter.</div>
          </div>
          <div>
            <div className="label">Evidence snapshot</div>
            <div>
              {review.evidence_count_at_review} record{review.evidence_count_at_review === 1 ? "" : "s"}
              {snapshotIds.length > 0 && (
                <span className="muted">
                  {" "}
                  (
                  {snapshotIds.map((id, i) => (
                    <span key={id}>
                      {i > 0 && ", "}
                      <Link to={`/evidence/${id}`}>#{id}</Link>
                    </span>
                  ))}
                  )
                </span>
              )}
            </div>
            <div className="muted">Evidence submitted after the review does not change it.</div>
          </div>
        </div>

        <div className="stack">
          <div className="label">Material findings · one per charter section</div>
          {findings.map((f) => (
            <FindingRow key={f.section_id} finding={f} sections={sections} />
          ))}
        </div>

        {precedents && <PrecedentMemory precedents={precedents} sections={sections} />}

        <div className="grid-2">
          <ChainTime label="Reviewed" value={review.created_at} />
          <div>
            <div className="label">Requested by</div>
            <div className="hash">{review.requested_by}</div>
          </div>
        </div>
        <div>
          <div className="label">Evidence-set hash</div>
          <div className="hash" title={review.evidence_set_hash}>{review.evidence_set_hash}</div>
          <div className="label">Review context hash</div>
          <div className="hash" title={review.review_context_hash}>{review.review_context_hash}</div>
          <div className="label">Review hash</div>
          <div className="hash" title={review.review_hash}>{review.review_hash}</div>
          <p className="muted">
            The review hash commits to the context, the verdict and each finding's section, kind, repairability and evidence. It does not
            commit to the explanatory wording. The hashes are not a hash of any web page.
          </p>
        </div>
      </div>
    </Docket>
  );
}

function StoredReview({ reviewId, sections, onVerdict }: { reviewId: number; sections: readonly CharterRevision[]; onVerdict?: (v: string) => void }) {
  const read = useRead(
    async () => {
      const [review, findings, ids, precedents] = await Promise.all([
        getConstitutionalReview(reviewId),
        getReviewFindingsPage(reviewId),
        getReviewEvidenceIdsPage(reviewId),
        getReviewPrecedents(reviewId),
      ]);
      return { review, findings, ids, precedents };
    },
    [reviewId],
  );
  const verdict = read.data?.review.verdict;
  useEffect(() => {
    if (verdict) onVerdict?.(verdict);
  }, [verdict, onVerdict]);
  if (read.error) return <ErrorBanner title="Could not read the review">{read.error}</ErrorBanner>;
  if (read.data === null) return <Docket label="Constitutional review">Reading the finalized review from GenLayer…</Docket>;
  return (
    <ReviewResultView review={read.data.review} findings={read.data.findings} sections={sections} snapshotIds={read.data.ids} precedents={read.data.precedents} />
  );
}

/**
 * Constitutional review area of the proposal page. The transaction state lives here, above every read, so the
 * timeline and the result of a request survive the reloads that follow it (the Stage 2 unmount bug).
 */
export function ConstitutionalReviewPanel({ proposal, onVerdict, onFinalized }: { proposal: Proposal; onVerdict?: (v: string) => void; onFinalized?: () => void }) {
  const wallet = useWallet();
  const { tx, busy, run, reset } = useTx();
  const [done, setDone] = useState(false);
  const reviewId = useRead(() => getReviewIdForProposal(proposal.proposal_id), [proposal.proposal_id]);
  const evidence = useRead(() => getProposalEvidencePage(proposal.proposal_id), [proposal.proposal_id]);
  const sections = useRead(
    () => getCharterSectionsAtVersionPage(proposal.charter_version_at_submission),
    [proposal.charter_version_at_submission],
  );
  // Keep what was last read while a reload is in flight, so nothing below unmounts after a transaction.
  const [lastId, setLastId] = useState<number | null>(null);
  if (reviewId.data !== null && reviewId.data !== lastId) setLastId(reviewId.data);
  const id = reviewId.data ?? lastId;

  const charter = sections.data ?? [];
  const active = charter.filter((s) => s.active).length;
  const summary = summarizeEvidence(evidence.data ?? []);
  // A failed or unfinished read must never be shown as a fact ("0 active sections", "cannot be reviewed").
  const readsError = sections.error ?? evidence.error ?? reviewId.error;
  const readsReady = sections.data !== null && evidence.data !== null && id !== null;
  const gate = reviewRequestGate({
    connection: wallet.connection,
    isProposer: sameAddress(wallet.address, proposal.proposer),
    hasReview: (id ?? 0) > 0,
    status: proposal.status,
    activeSections: active,
  });

  async function request() {
    if (!wallet.client) return;
    setDone(false);
    const final = await run((c, on) => requestConstitutionalReview(c, proposal.proposal_id, on), wallet.client);
    if (final.phase === "finalized") {
      setDone(true);
      reviewId.reload();
      evidence.reload();
      onFinalized?.();
    }
  }

  return (
    <div className="stack">
      {(id ?? 0) === 0 && (
        <Docket label="Constitutional review">
          <div className="stack">
            <div>
              <div className="label">Charter in force</div>
              <div>v{proposal.charter_version_at_submission}</div>
              <div className="muted">
                {sections.data === null
                  ? sections.error
                    ? "The charter could not be read."
                    : "Reading the charter…"
                  : `${active} active section${active === 1 ? "" : "s"} will each receive a finding.`}
              </div>
            </div>
            <div>
              <div className="label">Evidence available</div>
              <div>{evidence.data === null ? (evidence.error ? "The evidence could not be read." : "Reading evidence…") : describeEvidence(summary)}</div>
              <div className="muted">
                Only VERIFIED records can support a finding. Evidence added after the review is requested is not part of it.
              </div>
            </div>
            {readsError && !readsReady && <p className="label">Some of this page could not be read, so the review action is hidden. Reload to try again.</p>}
            {readsReady && !gate.allowed && gate.reason && <p className="label">{gate.reason}</p>}
            {readsReady && gate.allowed && (
              <Button variant="primary" disabled={busy} onClick={() => void request()}>
                REQUEST REVIEW
              </Button>
            )}
            <p className="label">Validators judge the proposal themselves, so this can take a minute or more.</p>
          </div>
        </Docket>
      )}

      {tx.phase !== "ready" && (
        <Docket label="Review transaction">
          <TransactionTimeline tx={tx} />
          {done && (
            <p>
              Finalized. That is the <strong>transaction</strong>: the network agreed and the contract ran. The{" "}
              <strong>constitutional verdict</strong> is shown below and may be any of the four outcomes.
            </p>
          )}
          {!busy && (
            <Button variant="quiet" onClick={reset}>
              DISMISS
            </Button>
          )}
        </Docket>
      )}

      {reviewId.error && <ErrorBanner title="Could not read review state">{reviewId.error}</ErrorBanner>}
      {(id ?? 0) > 0 && <StoredReview reviewId={id as number} sections={charter} onVerdict={onVerdict} />}
    </div>
  );
}
