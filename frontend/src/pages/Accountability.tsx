import { Link } from "react-router-dom";
import { AmendmentRow } from "../components/Amendment";
import { Badge, Docket, EmptyState } from "../components/primitives";
import { ReadBoundary } from "../components/common";
import { UNVERIFIED_NOTE } from "../lib/amendment";
import { shortAddress } from "../lib/format";
import { getAmendmentsPage, getProposalsPage, LIMITS } from "../lib/genlayer/charterGate";
import { useRead } from "../lib/genlayer/hooks";

/** What happened after governance decisions, and what is and is not verified. Two bounded list reads; each record has its own page. */
export function AccountabilityPage() {
  const amendments = useRead(() => getAmendmentsPage(0, LIMITS.pageSize));
  const proposals = useRead(() => getProposalsPage(0, LIMITS.pageSize));
  return (
    <div className="stack">
      <h1 style={{ fontSize: "clamp(2rem, 6vw, 4rem)" }}>Accountability</h1>
      <Docket label="What is recorded, and how much to trust it">
        <div className="stack">
          <p>
            <Badge tone="final">VERIFIED BY THE CONTRACT</Badge> An amendment is applied by the contract itself, so when it reports that an amendment was applied, the charter version it created and who applied it,
            the contract is reporting its own state.
          </p>
          <p>
            <Badge tone="warning">SELF-REPORTED</Badge> {UNVERIFIED_NOTE}
          </p>
        </div>
      </Docket>

      <h2 style={{ fontSize: "1.8rem" }}>Amendments</h2>
      <ReadBoundary read={amendments}>
        {(list) =>
          list.length === 0 ? (
            <EmptyState title="No amendments yet">When the charter is amended, its full history appears here.</EmptyState>
          ) : (
            <div className="docket-rows">
              {[...list].reverse().map((a) => (
                <AmendmentRow key={a.amendment_id} a={a} />
              ))}
            </div>
          )
        }
      </ReadBoundary>

      <h2 style={{ fontSize: "1.8rem" }}>Approved proposals</h2>
      <p className="muted">A proposal whose controlling ruling is ELIGIBLE can have its execution reported on its case page.</p>
      <ReadBoundary read={proposals}>
        {(list) => {
          const approved = list.filter((p) => p.status === "ELIGIBLE");
          return approved.length === 0 ? (
            <EmptyState title="No approved proposals yet">Proposals with an ELIGIBLE ruling appear here.</EmptyState>
          ) : (
            <div className="docket-rows">
              {[...approved].reverse().map((p) => (
                <Link key={p.proposal_id} to={`/proposals/${p.proposal_id}`} className="docket-row">
                  <span className="label">CASE {String(p.proposal_id).padStart(3, "0")}</span>
                  <strong>{p.title}</strong>
                  <span className="label">{shortAddress(p.proposer)}</span>
                  <span className="label">charter v{p.charter_version_at_submission}</span>
                  <Badge tone="eligible">ELIGIBLE</Badge>
                </Link>
              ))}
            </div>
          );
        }}
      </ReadBoundary>
    </div>
  );
}
