import { useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Docket } from "./primitives";
import { ChainTime, Field } from "./common";
import { TransactionTimeline } from "./TransactionTimeline";
import {
  ACTION_INFO,
  amendmentFailure,
  amendmentGates,
  EVAL_NOTE,
  EXECUTION_INFO,
  GOVERNANCE_OFF_NOTE,
  GOVERNANCE_ON_NOTE,
  MAX_RATIONALE,
  STATUS_INFO,
} from "../lib/amendment";
import {
  AMENDMENT_ACTIONS,
  approveAmendment,
  applyAmendment,
  closeStaleAmendment,
  enableAmendmentGovernance,
  getAmendmentAccountability,
  LIMITS,
  proposeAmendment,
  rejectAmendment,
  requestAmendmentEvaluation,
  SECTION_ID_PATTERN,
  type Amendment,
  type AmendmentAccountability,
  type AmendmentAction,
  type CharterSection,
  type GovernanceStatus,
} from "../lib/genlayer/charterGate";
import type { ChainClient } from "../lib/genlayer/client";
import { useRead, useTx } from "../lib/genlayer/hooks";
import type { TxState } from "../lib/genlayer/tx";
import { sameAddress, shortAddress } from "../lib/format";
import { useWallet } from "../lib/genlayer/wallet-context";

const no = (id: number) => `#${String(id).padStart(3, "0")}`;

/** One line per amendment, from the page read (no extra reads). */
export function AmendmentRow({ a }: { a: Amendment }) {
  const info = STATUS_INFO[a.status];
  return (
    <Link to={`/constitution/amend/${a.amendment_id}`} className="docket-row">
      <span className="label">AMENDMENT {String(a.amendment_id).padStart(3, "0")}</span>
      <strong>
        {ACTION_INFO[a.action].label}: §{a.section_id}
        {a.title !== "" ? ` ${a.title}` : ""}
      </strong>
      <span className="label">against charter v{a.base_version}</span>
      <Badge tone={info.tone}>{info.label}</Badge>
    </Link>
  );
}

/** The governance switch. Owner only and one-way, so the control makes the consequence explicit first. */
export function GovernancePanel({ status, onChanged }: { status: GovernanceStatus; onChanged: () => void }) {
  const wallet = useWallet();
  const { tx, busy, run, reset } = useTx();
  const [understood, setUnderstood] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const isOwner = sameAddress(wallet.address, status.owner);

  async function enable() {
    if (!wallet.client) return;
    setMessage(null);
    const final = await run((c, on) => enableAmendmentGovernance(c, on), wallet.client);
    if (final.phase === "finalized") onChanged();
    else setMessage(amendmentFailure(final.failure?.code));
  }

  return (
    <Docket label="Charter governance">
      <div className="stack">
        <div className="row">
          <Badge tone={status.governance_enabled ? "final" : "warning"}>{status.governance_enabled ? "AMENDMENT GOVERNANCE ON" : "AMENDMENT GOVERNANCE OFF"}</Badge>
          <Badge>Charter v{status.charter_version}</Badge>
          <span className="label">owner {shortAddress(status.owner)}</span>
        </div>
        <p className="muted">{status.governance_enabled ? GOVERNANCE_ON_NOTE : GOVERNANCE_OFF_NOTE}</p>
        {!status.governance_enabled && isOwner && wallet.connection === "ready" && (
          <div className="stack">
            <label className="row">
              <input type="checkbox" checked={understood} disabled={busy} onChange={(e) => setUnderstood(e.target.checked)} />
              <span>I understand this cannot be undone: afterwards only approved amendments can change the charter.</span>
            </label>
            <Button variant="primary" disabled={!understood || busy} onClick={() => void enable()}>
              TURN ON AMENDMENT GOVERNANCE
            </Button>
          </div>
        )}
        {tx.phase !== "ready" && (
          <div>
            <TransactionTimeline tx={tx} />
            {message !== null && <p>{message}</p>}
            {!busy && (
              <Button variant="quiet" onClick={reset}>
                DISMISS
              </Button>
            )}
          </div>
        )}
      </div>
    </Docket>
  );
}

/** Propose an amendment. It is written against the charter version shown here. */
export function ProposeAmendmentForm({ charterVersion, sections, onChanged }: { charterVersion: number; sections: readonly CharterSection[]; onChanged: () => void }) {
  const wallet = useWallet();
  const { tx, busy, run, reset } = useTx();
  const [action, setAction] = useState<AmendmentAction>("UPDATE");
  const [sectionId, setSectionId] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [rationale, setRationale] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const active = sections.filter((s) => s.active);
  const target = sections.find((s) => s.section_id === sectionId);

  const needsText = action !== "DEACTIVATE";
  const idOk = sectionId.length > 0 && sectionId.length <= LIMITS.sectionId && SECTION_ID_PATTERN.test(sectionId);
  const valid =
    idOk &&
    rationale.trim().length > 0 &&
    rationale.trim().length <= MAX_RATIONALE &&
    (!needsText || (title.trim().length > 0 && title.trim().length <= LIMITS.sectionTitle && body.trim().length > 0 && body.trim().length <= LIMITS.sectionBody));

  function choose(next: AmendmentAction) {
    setAction(next);
    setSectionId("");
    setTitle("");
    setBody("");
  }

  function pick(id: string) {
    setSectionId(id);
    const s = sections.find((x) => x.section_id === id);
    if (action === "UPDATE" && s) {
      setTitle(s.title);
      setBody(s.body);
    }
  }

  async function submit() {
    if (!wallet.client) return;
    setMessage(null);
    const final = await run(
      (c, on) =>
        proposeAmendment(c, action, sectionId, needsText ? title.trim() : "", needsText ? body.trim() : "", charterVersion, rationale.trim(), 0, on),
      wallet.client,
    );
    if (final.phase === "finalized") {
      setSectionId("");
      setTitle("");
      setBody("");
      setRationale("");
      onChanged();
    } else {
      setMessage(amendmentFailure(final.failure?.code));
    }
  }

  const blocked = wallet.connection === "disconnected" ? "Connect your wallet to propose." : wallet.connection === "wrong_network" ? "Switch your wallet to StudioNet (chain 61999)." : null;

  return (
    <Docket label={`Propose an amendment · written against charter v${charterVersion}`}>
      <div className="stack">
        <p className="muted">
          Anyone can propose. Nothing changes until a model has advised on compatibility, the owner has approved it and it has been applied, and it applies only if the charter is
          still at v{charterVersion}.
        </p>
        <label className="field">
          <span className="label">What it does</span>
          <select value={action} disabled={busy} onChange={(e) => choose(e.target.value as AmendmentAction)}>
            {AMENDMENT_ACTIONS.map((a) => (
              <option key={a} value={a}>
                {ACTION_INFO[a].label}
              </option>
            ))}
          </select>
          <span className="muted">{ACTION_INFO[action].help}</span>
        </label>
        {action === "ADD" ? (
          <Field label="New section id" value={sectionId} onChange={setSectionId} max={LIMITS.sectionId} hint="letters, digits . _ -" disabled={busy} />
        ) : (
          <label className="field">
            <span className="label">Section</span>
            <select value={sectionId} disabled={busy} onChange={(e) => pick(e.target.value)}>
              <option value="">Choose an active section</option>
              {active.map((s) => (
                <option key={s.section_id} value={s.section_id}>
                  §{s.section_id} {s.title}
                </option>
              ))}
            </select>
          </label>
        )}
        {action === "DEACTIVATE" && target && <p className="muted">§{target.section_id} {target.title} will stop applying to new proposals.</p>}
        {needsText && (
          <>
            <Field label="Title" value={title} onChange={setTitle} max={LIMITS.sectionTitle} disabled={busy} />
            <Field label="Body" value={body} onChange={setBody} max={LIMITS.sectionBody} multiline disabled={busy} />
          </>
        )}
        <Field label="Why" value={rationale} onChange={setRationale} max={MAX_RATIONALE} multiline disabled={busy} hint="Your argument for the change. It is not evidence." />
        <div className="row">
          <Button variant="primary" disabled={!valid || busy || blocked !== null} onClick={() => void submit()}>
            PROPOSE AMENDMENT
          </Button>
        </div>
        {blocked !== null && <p className="label">{blocked}</p>}
        {tx.phase !== "ready" && (
          <div>
            <TransactionTimeline tx={tx} />
            {tx.phase === "finalized" && <p>Finalized. The amendment was recorded as PROPOSED. It changes nothing yet.</p>}
            {message !== null && <p>{message}</p>}
            {!busy && (
              <Button variant="quiet" onClick={reset}>
                DISMISS
              </Button>
            )}
          </div>
        )}
      </div>
    </Docket>
  );
}

/** Pure view of one amendment's accountability. */
export function AmendmentAccountabilityView({ acc }: { acc: AmendmentAccountability }) {
  const a = acc.amendment;
  const status = STATUS_INFO[a.status];
  const exec = EXECUTION_INFO[acc.execution_state];
  return (
    <div className="stack" aria-label="Amendment accountability">
      <Docket label={`Amendment ${no(a.amendment_id)}`}>
        <div className="stack">
          <div className="row">
            <Badge tone={status.tone}>{status.label}</Badge>
            <Badge>{ACTION_INFO[a.action].label}</Badge>
            <Badge>against charter v{a.base_version}</Badge>
          </div>
          <p className="muted">{status.explain}</p>
          <p>
            <span className="label">Section </span>§{a.section_id}
          </p>
          {a.action !== "DEACTIVATE" && (
            <>
              <strong>{a.title}</strong>
              <p style={{ whiteSpace: "pre-wrap" }}>{a.body}</p>
            </>
          )}
          <div className="label">Why (the proposer's argument, not evidence)</div>
          <p style={{ whiteSpace: "pre-wrap" }}>{a.rationale}</p>
          {a.source_proposal_id > 0 && (
            <p>
              <span className="label">Prompted by </span>
              <Link to={`/proposals/${a.source_proposal_id}`}>case {String(a.source_proposal_id).padStart(3, "0")}</Link>
            </p>
          )}
          <p className="muted">Proposed by {shortAddress(a.proposer)}</p>
          <div className="label">Amendment hash</div>
          <div className="hash">{a.amendment_hash}</div>
        </div>
      </Docket>

      <Docket label="Compatibility evaluation">
        <div className="stack">
          <p className="muted">{EVAL_NOTE}</p>
          {a.eval_verdict === "" ? (
            <p>Not evaluated yet.</p>
          ) : (
            <>
              <div className="row">
                <Badge tone={a.eval_verdict === "COMPATIBLE" ? "eligible" : "ineligible"}>{a.eval_verdict}</Badge>
              </div>
              {a.eval_verdict === "CONFLICTING" && (
                <p>
                  <span className="label">Conflicts with </span>
                  {a.eval_conflicting_section_ids.length > 0 ? a.eval_conflicting_section_ids.map((s) => `§${s}`).join(", ") : "the charter's overall purpose"}
                </p>
              )}
              <ChainTime label="Evaluated" value={a.evaluated_at} />
              <div className="label">Evaluation hash</div>
              <div className="hash">{a.eval_hash}</div>
            </>
          )}
        </div>
      </Docket>

      <Docket label="Execution and accountability">
        <div className="stack">
          <div className="row">
            <Badge tone={exec.tone}>{exec.label}</Badge>
            {acc.contract_verified && <Badge tone="final">VERIFIED BY THE CONTRACT</Badge>}
          </div>
          <p className="muted">{exec.explain}</p>
          {a.applied_version > 0 && (
            <p>
              Changed charter v{a.base_version} into <strong>v{a.applied_version}</strong>, applied by {shortAddress(a.applied_by)}.
            </p>
          )}
          {a.decided_by !== "" && (
            <p className="muted">
              {a.status === "REJECTED" ? "Closed" : "Decided"} by {shortAddress(a.decided_by)}
            </p>
          )}
          <p className="muted">The current charter is v{acc.current_charter_version}.</p>
          <ol className="stack" aria-label="Amendment history" style={{ listStyle: "none", padding: 0 }}>
            {acc.events.map((e, i) => (
              <li key={`${e.kind}-${i}`}>
                <strong>{e.kind}</strong> · {shortAddress(e.actor)} · at charter v{e.charter_version}
                <ChainTime label="When" value={e.at} />
              </li>
            ))}
          </ol>
        </div>
      </Docket>
    </div>
  );
}

/** The actions available on one amendment, each gated by role, status and staleness, with one transaction state above the reads. */
export function AmendmentPanel({ amendmentId, ownerAddress }: { amendmentId: number; ownerAddress: string | null }) {
  const wallet = useWallet();
  const { tx, busy, run, reset } = useTx();
  const [message, setMessage] = useState<string | null>(null);
  const read = useRead(() => getAmendmentAccountability(amendmentId), [amendmentId]);

  if (read.error) return <Docket label="Amendment">Could not read this amendment: {read.error}</Docket>;
  if (read.data === null) return <Docket label="Amendment">Reading the amendment from GenLayer…</Docket>;
  const acc = read.data;
  const a = acc.amendment;
  const gates = amendmentGates({
    connection: wallet.connection,
    isOwner: sameAddress(wallet.address, ownerAddress),
    isProposer: sameAddress(wallet.address, a.proposer),
    status: a.status,
    evalVerdict: a.eval_verdict,
    stale: acc.stale,
  });

  async function go(send: Parameters<typeof run>[0]) {
    if (!wallet.client) return;
    setMessage(null);
    const final = await run(send, wallet.client);
    if (final.phase === "finalized") read.reload();
    else setMessage(amendmentFailure(final.failure?.code));
  }

  const buttons = [
    { key: "evaluate", label: "REQUEST EVALUATION", gate: gates.evaluate, send: (c: ChainClient, on: (s: TxState) => void) => requestAmendmentEvaluation(c, amendmentId, on) },
    { key: "approve", label: "APPROVE (OWNER)", gate: gates.approve, send: (c: ChainClient, on: (s: TxState) => void) => approveAmendment(c, amendmentId, on) },
    { key: "apply", label: "APPLY TO THE CHARTER", gate: gates.apply, send: (c: ChainClient, on: (s: TxState) => void) => applyAmendment(c, amendmentId, on) },
    { key: "reject", label: "REJECT / WITHDRAW", gate: gates.reject, send: (c: ChainClient, on: (s: TxState) => void) => rejectAmendment(c, amendmentId, on) },
    { key: "close", label: "CLOSE AS SUPERSEDED", gate: gates.closeStale, send: (c: ChainClient, on: (s: TxState) => void) => closeStaleAmendment(c, amendmentId, on) },
  ];
  const offered = buttons.filter((b) => b.gate.allowed);

  return (
    <div className="stack">
      <AmendmentAccountabilityView acc={acc} />
      <Docket label="Actions">
        <div className="stack">
          {acc.stale && <p>The charter has changed since this amendment was written, so it can no longer be evaluated, approved or applied. It can be closed as superseded.</p>}
          {offered.length === 0 ? (
            <p className="muted">{gates.evaluate.reason ?? gates.apply.reason ?? "No action is available to you on this amendment."}</p>
          ) : (
            <div className="row">
              {offered.map((b) => (
                <Button key={b.key} variant={b.key === "apply" || b.key === "approve" ? "primary" : "quiet"} disabled={busy} onClick={() => void go(b.send)}>
                  {b.label}
                </Button>
              ))}
            </div>
          )}
          {tx.phase !== "ready" && (
            <div>
              <TransactionTimeline tx={tx} />
              {tx.phase === "finalized" && <p>Finalized and executed. The amendment above shows its new state.</p>}
              {message !== null && <p>{message}</p>}
              {!busy && (
                <Button variant="quiet" onClick={reset}>
                  DISMISS
                </Button>
              )}
            </div>
          )}
        </div>
      </Docket>
    </div>
  );
}
