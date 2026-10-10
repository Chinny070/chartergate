import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Docket, ErrorBanner } from "./primitives";
import { ChainTime, Field } from "./common";
import { FindingRow } from "./Review";
import { PrecedentMemory } from "./Precedent";
import { TransactionTimeline } from "./TransactionTimeline";
import {
  APPEAL_GROUNDS,
  APPEAL_NOT_EVIDENCE,
  appealGate,
  DECISION_INFO,
  dissentOutcome,
  DISSENT_HEADLINE,
  DISSENT_LABEL,
  DISSENT_NOTE,
  DISSENT_REQUEST_NOTE,
  FROZEN_RECORD_DETAIL,
  FROZEN_RECORD_NOTE,
  materialDifferences,
  MAX_APPEAL_STATEMENT,
  PRECEDENT_AFTER_APPEAL,
  REPAIR_VS_APPEAL,
  WIN_IS_NOT_SUCCESS,
} from "../lib/appeal";
import { VERDICT_INFO } from "../lib/review";
import {
  getAppealRecord,
  getCharterSectionsAtVersionPage,
  getConstitutionalReview,
  getEffectiveRuling,
  getReviewPrecedents,
  requestAppeal,
  requestReasonedDissent,
  type AppealGround,
  type AppealRecord,
  type CharterRevision,
  type EffectiveRuling,
  type Proposal,
  type ReasonedDissent,
  type ReviewFinding,
} from "../lib/genlayer/charterGate";
import { useRead, useTx } from "../lib/genlayer/hooks";
import { sameAddress, shortAddress } from "../lib/format";
import { useWallet } from "../lib/genlayer/wallet-context";

const reviewNo = (id: number) => `#${String(id).padStart(3, "0")}`;

function VerdictLine({ label, verdict }: { label: string; verdict: string }) {
  const info = (VERDICT_INFO as Record<string, { label: string; tone: "eligible" | "warning" | "ineligible" | "active" | "final" | "precedent" }>)[verdict];
  return (
    <div>
      <div className="label">{label}</div>
      <Badge tone={info?.tone ?? "active"}>{info?.label ?? verdict}</Badge>
    </div>
  );
}

function FindingList({ findings, sections }: { findings: readonly ReviewFinding[]; sections: readonly CharterRevision[] }) {
  return (
    <div className="stack">
      {findings.map((f) => (
        <FindingRow key={f.section_id} finding={f} sections={sections} />
      ))}
    </div>
  );
}

/** The reasoned dissent, labelled for what it is. It never controls anything. */
export function DissentView({ dissent, sections }: { dissent: ReasonedDissent; sections: readonly CharterRevision[] }) {
  return (
    <Docket label={DISSENT_LABEL}>
      <div className="stack" aria-label="Reasoned dissent">
        <div className="row">
          <Badge tone="precedent">{DISSENT_HEADLINE.toUpperCase()}</Badge>
        </div>
        <p className="muted">{DISSENT_NOTE}</p>
        <VerdictLine label="Alternative verdict (does not control)" verdict={dissent.verdict} />
        <p>
          <span className="label">Sections where it disagrees </span>
          {dissent.disagreeing_section_ids.map((s) => `§${s}`).join(", ")}
        </p>
        <FindingList findings={dissent.findings} sections={sections} />
        <div className="label">Dissent hash</div>
        <div className="hash">{dissent.dissent_hash}</div>
        <ChainTime label="Written" value={dissent.created_at} />
      </div>
    </Docket>
  );
}

/** ORIGINAL REVIEW -> APPEAL -> APPELLATE DECISION. The original is never renamed or replaced. */
export function AppellateHistory({
  record,
  effectiveVerdict,
  sections,
  children,
}: {
  record: AppealRecord;
  effectiveVerdict: string;
  sections: readonly CharterRevision[];
  children?: React.ReactNode;
}) {
  const { appeal, review, decision } = record;
  const kind = DECISION_INFO[decision.decision_kind];
  const ground = APPEAL_GROUNDS.find((g) => g.id === appeal.ground);
  const differs = materialDifferences(record.original_findings, record.findings);
  return (
    <div className="stack" aria-label="Appellate history">
      <Docket label={`Original review ${reviewNo(review.review_id)}`}>
        <div className="stack">
          <p className="muted">The original judgment is preserved exactly as it was issued. An appeal never edits it.</p>
          <VerdictLine label="Original judgment" verdict={review.verdict} />
          <FindingList findings={record.original_findings} sections={sections} />
          <div className="label">Review hash</div>
          <div className="hash">{review.review_hash}</div>
        </div>
      </Docket>

      <Docket label="Appeal">
        <div className="stack">
          <p>
            <span className="label">Ground </span>
            {ground?.label ?? appeal.ground}
          </p>
          <p style={{ whiteSpace: "pre-wrap" }}>{appeal.statement}</p>
          <p className="muted">{APPEAL_NOT_EVIDENCE}</p>
          <p className="muted">Filed by {shortAddress(appeal.appellant)}.</p>
          <ChainTime label="Filed" value={appeal.created_at} />
          <div className="label">Appeal hash</div>
          <div className="hash">{appeal.appeal_hash}</div>
        </div>
      </Docket>

      <Docket label="Appellate decision">
        <div className="stack">
          <div className="row">
            <Badge tone={kind.tone}>{kind.label}</Badge>
          </div>
          <p>{kind.explain}</p>
          <div className="grid-2">
            <VerdictLine label="Original judgment" verdict={appeal.original_verdict} />
            <VerdictLine label="Appellate judgment" verdict={decision.verdict} />
          </div>
          <div>
            <VerdictLine label="Effective constitutional verdict" verdict={effectiveVerdict} />
            <p className="muted">The effective verdict is the one that currently controls this proposal. Both judgments above remain inspectable.</p>
          </div>
          {differs.length > 0 && (
            <p>
              <span className="label">Sections changed by the appeal </span>
              {differs.map((s) => `§${s}`).join(", ")}
            </p>
          )}
          <FindingList findings={record.findings} sections={sections} />
          <PrecedentMemory
            precedents={{
              review_id: review.review_id,
              precedent_set_hash: appeal.precedent_set_hash,
              candidates: record.precedent_candidates,
              citations: record.citations,
            }}
            sections={sections}
          />
          <p className="muted">{PRECEDENT_AFTER_APPEAL[decision.decision_kind]}</p>
        </div>
      </Docket>

      <Docket label="Closed appellate record">
        <div className="stack">
          <p className="muted">{FROZEN_RECORD_DETAIL}</p>
          <p>
            <span className="label">Charter </span>v{appeal.charter_version}
            <span className="label"> · Evidence snapshot </span>
            {appeal.evidence_count} record{appeal.evidence_count === 1 ? "" : "s"}
            {record.evidence_ids.length > 0 && (
              <>
                {" "}
                (
                {record.evidence_ids.map((id, i) => (
                  <span key={id}>
                    {i > 0 && ", "}
                    <Link to={`/evidence/${id}`}>#{id}</Link>
                  </span>
                ))}
                )
              </>
            )}
          </p>
          <div className="label">Evidence-set hash</div>
          <div className="hash">{appeal.evidence_set_hash}</div>
          <div className="label">Appeal context hash</div>
          <div className="hash">{decision.appeal_context_hash}</div>
          <div className="label">Decision hash</div>
          <div className="hash">{decision.decision_hash}</div>
          <p className="muted">The decision hash commits to the findings, repairability, evidence references, verdict and disposition. It does not commit to any wording.</p>
        </div>
      </Docket>
      {children}
    </div>
  );
}

/** The appeal workspace: the frozen record, the ground, the statement. Loaded only when opened. */
function AppealWorkspace({
  ruling,
  proposal,
  busy,
  onSubmit,
  onCancel,
}: {
  ruling: EffectiveRuling;
  proposal: Proposal;
  busy: boolean;
  onSubmit: (ground: AppealGround, statement: string) => void;
  onCancel: () => void;
}) {
  const read = useRead(
    async () => {
      const [review, precedents, sections] = await Promise.all([
        getConstitutionalReview(ruling.review_id),
        getReviewPrecedents(ruling.review_id),
        getCharterSectionsAtVersionPage(proposal.charter_version_at_submission),
      ]);
      return { review, precedents, sections };
    },
    [ruling.review_id, proposal.charter_version_at_submission],
  );
  const [ground, setGround] = useState<AppealGround>("CHARTER_MISINTERPRETATION");
  const [statement, setStatement] = useState("");
  if (read.error) return <ErrorBanner title="Could not read the ruling you are appealing">{read.error}</ErrorBanner>;
  if (read.data === null) return <Docket label="Appeal workspace">Reading the closed record from GenLayer…</Docket>;
  const { review, precedents, sections } = read.data;
  const sawPrecedent = precedents.candidates.length > 0;
  const trimmed = statement.trim();
  const valid = trimmed.length >= 1 && trimmed.length <= MAX_APPEAL_STATEMENT && (ground !== "PRECEDENT_MISAPPLICATION" || sawPrecedent);
  return (
    <Docket label={`Appeal workspace · review ${reviewNo(review.review_id)}`}>
      <div className="stack">
        <p className="muted">{FROZEN_RECORD_DETAIL}</p>
        <VerdictLine label="Original constitutional verdict" verdict={review.verdict} />
        <FindingList findings={ruling.findings} sections={sections} />
        <div className="grid-2">
          <div>
            <div className="label">Charter version</div>v{review.charter_version}
          </div>
          <div>
            <div className="label">Frozen evidence snapshot</div>
            {review.evidence_count_at_review} record{review.evidence_count_at_review === 1 ? "" : "s"}
          </div>
        </div>
        <p>
          <span className="label">Frozen precedent snapshot </span>
          {sawPrecedent ? `${precedents.candidates.length} prior ruling${precedents.candidates.length === 1 ? "" : "s"} (advisory only)` : "none: this review saw no precedent"}
        </p>
        <p>
          <strong>{FROZEN_RECORD_NOTE}</strong>
        </p>
        <label className="field">
          <span className="label">Ground of appeal</span>
          <select value={ground} disabled={busy} onChange={(e) => setGround(e.target.value as AppealGround)}>
            {APPEAL_GROUNDS.filter((g) => g.id !== "PRECEDENT_MISAPPLICATION" || sawPrecedent).map((g) => (
              <option key={g.id} value={g.id}>
                {g.label}
              </option>
            ))}
          </select>
          <span className="muted">{APPEAL_GROUNDS.find((g) => g.id === ground)?.help}</span>
        </label>
        <Field label="Appeal statement" value={statement} onChange={setStatement} max={MAX_APPEAL_STATEMENT} multiline disabled={busy} hint={APPEAL_NOT_EVIDENCE} />
        <div className="row">
          <Button variant="primary" disabled={busy || !valid} onClick={() => onSubmit(ground, trimmed)}>
            FILE APPEAL
          </Button>
          <Button variant="quiet" disabled={busy} onClick={onCancel}>
            CANCEL
          </Button>
        </div>
        <p className="label">Validators reconstruct the record and judge it themselves, so this can take a minute or more.</p>
      </div>
    </Docket>
  );
}

/**
 * Appeal entry point and appellate history for a proposal. The transaction state lives here, above every read, so the
 * timeline survives the reloads that follow a transaction.
 */
export function AppealPanel({ proposal, refreshKey = 0, onChanged }: { proposal: Proposal; refreshKey?: number; onChanged?: () => void }) {
  const wallet = useWallet();
  const appealTx = useTx();
  const dissentTx = useTx();
  const [tick, setTick] = useState(0);
  const [open, setOpen] = useState(false);
  const [dissentResult, setDissentResult] = useState<string | null>(null);

  const ruling = useRead(() => getEffectiveRuling(proposal.proposal_id), [proposal.proposal_id, tick, refreshKey]);
  const appealId = ruling.data?.appeal_id ?? 0;
  const record = useRead(() => (appealId > 0 ? getAppealRecord(appealId) : Promise.resolve(null)), [appealId, tick, refreshKey]);
  const sections = useRead(() => getCharterSectionsAtVersionPage(proposal.charter_version_at_submission), [proposal.charter_version_at_submission]);

  const isProposer = sameAddress(wallet.address, proposal.proposer);
  const reload = () => {
    setTick((t) => t + 1);
    onChanged?.();
  };

  if (ruling.error) return <ErrorBanner title="Could not read the controlling ruling">{ruling.error}</ErrorBanner>;
  const data = ruling.data;
  const quiet = appealTx.tx.phase === "ready" && dissentTx.tx.phase === "ready";
  if (data === null) return null;
  if (data.review_id === 0 && quiet) return null;

  const adverse = data.original_verdict !== "" && data.original_verdict !== "ELIGIBLE";
  const gate = appealGate({
    connection: wallet.connection,
    isProposer,
    appealable: data.appealable,
    blockedReason: data.appealable ? "" : data.appeal_id > 0 ? "APPEAL_ALREADY_EXISTS" : data.controlled_by === "REVIEW" && !adverse ? "REVIEW_NOT_ADVERSE" : "REPAIR_ALREADY_STARTED",
  });

  async function file(ground: AppealGround, statement: string) {
    if (!wallet.client) return;
    const final = await appealTx.run((c, on) => requestAppeal(c, data!.review_id, ground, statement, on), wallet.client);
    if (final.phase === "finalized") {
      setOpen(false);
      reload();
    }
  }

  async function dissent() {
    if (!wallet.client || appealId === 0) return;
    setDissentResult(null);
    const final = await dissentTx.run((c, on) => requestReasonedDissent(c, appealId, on), wallet.client);
    if (final.phase === "finalized") {
      reload();
      return;
    }
    const out = dissentOutcome(final.failure?.code);
    if (out) setDissentResult(out.reason);
  }

  const sectionList = sections.data ?? [];
  const rec = record.data;

  return (
    <div className="stack">
      {data.appealable && !open && (
        <Docket label="Appeal decision">
          <div className="stack">
            <p>{REPAIR_VS_APPEAL.appeal}</p>
            <p className="muted">{REPAIR_VS_APPEAL.repair}</p>
            <p className="muted">{FROZEN_RECORD_NOTE}</p>
            {gate.allowed ? (
              <Button variant="primary" onClick={() => setOpen(true)}>
                APPEAL DECISION
              </Button>
            ) : (
              gate.reason && <p className="label">{gate.reason}</p>
            )}
          </div>
        </Docket>
      )}

      {open && data.appealable && <AppealWorkspace ruling={data} proposal={proposal} busy={appealTx.busy} onSubmit={(g, s) => void file(g, s)} onCancel={() => setOpen(false)} />}

      {appealTx.tx.phase !== "ready" && (
        <Docket label="Appeal transaction">
          <TransactionTimeline tx={appealTx.tx} />
          {appealTx.tx.phase === "finalized" && (
            <p>
              Finalized. That is the <strong>transaction</strong>. {WIN_IS_NOT_SUCCESS}
            </p>
          )}
          {!appealTx.busy && (
            <Button variant="quiet" onClick={appealTx.reset}>
              DISMISS
            </Button>
          )}
        </Docket>
      )}

      {appealId > 0 && record.error && <ErrorBanner title="Could not read the appellate record">{record.error}</ErrorBanner>}

      {rec !== null && rec !== undefined && (
        <AppellateHistory record={rec} effectiveVerdict={data.effective_verdict} sections={sectionList}>
          {rec.dissent !== null ? (
            <DissentView dissent={rec.dissent} sections={sectionList} />
          ) : (
            isProposer &&
            wallet.connection === "ready" && (
              <Docket label={DISSENT_LABEL}>
                <div className="stack">
                  <p className="muted">{DISSENT_REQUEST_NOTE}</p>
                  <p className="muted">{DISSENT_NOTE}</p>
                  <Button variant="quiet" disabled={dissentTx.busy} onClick={() => void dissent()}>
                    REQUEST REASONED DISSENT
                  </Button>
                  {dissentResult !== null && <p>{dissentResult}</p>}
                </div>
              </Docket>
            )
          )}
        </AppellateHistory>
      )}

      {dissentTx.tx.phase !== "ready" && (
        <Docket label="Reasoned dissent transaction">
          <TransactionTimeline tx={dissentTx.tx} />
          {dissentTx.tx.phase === "finalized" && (
            <p>
              Finalized. That is the <strong>transaction</strong>. A dissent never changes the effective judgment.
            </p>
          )}
          {dissentResult !== null && <p>{dissentResult}</p>}
          {!dissentTx.busy && (
            <Button variant="quiet" onClick={dissentTx.reset}>
              DISMISS
            </Button>
          )}
        </Docket>
      )}
    </div>
  );
}
