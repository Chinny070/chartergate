import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AmendmentPanel, AmendmentRow, GovernancePanel, ProposeAmendmentForm } from "../components/Amendment";
import { Docket, EmptyState } from "../components/primitives";
import { ReadBoundary } from "../components/common";
import { getAmendmentsPage, getCharterSectionsPage, getGovernanceStatus, LIMITS } from "../lib/genlayer/charterGate";
import { useRead } from "../lib/genlayer/hooks";

/** Governance status, proposing, and every amendment. One read each for the status, the sections and the list. */
export function AmendmentsPage() {
  const status = useRead(getGovernanceStatus);
  const sections = useRead(() => getCharterSectionsPage(0, LIMITS.pageSize));
  const list = useRead(() => getAmendmentsPage(0, LIMITS.pageSize));
  const [tick, setTick] = useState(0);
  const refresh = () => {
    status.reload();
    list.reload();
    sections.reload();
    setTick((t) => t + 1);
  };

  return (
    <div className="stack" data-refresh={tick}>
      <h1 style={{ fontSize: "clamp(2rem, 6vw, 4rem)" }}>Amendments</h1>
      <p className="muted">
        A constitution that can change needs a record of how it changed. An amendment is proposed against one exact charter version, advised on for compatibility, approved by the
        owner and then applied. Earlier charter versions are never altered.
      </p>
      <ReadBoundary read={status}>
        {(s) => (
          <>
            <GovernancePanel status={s} onChanged={refresh} />
            <ReadBoundary read={sections}>{(secs) => <ProposeAmendmentForm charterVersion={s.charter_version} sections={secs} onChanged={refresh} />}</ReadBoundary>
          </>
        )}
      </ReadBoundary>
      <ReadBoundary read={list}>
        {(amendments) =>
          amendments.length === 0 ? (
            <EmptyState title="No amendments yet">Proposed amendments will appear here with their whole history.</EmptyState>
          ) : (
            <div className="docket-rows">
              {[...amendments].reverse().map((a) => (
                <AmendmentRow key={a.amendment_id} a={a} />
              ))}
            </div>
          )
        }
      </ReadBoundary>
      <Link to="/constitution" className="label">
        ← the charter
      </Link>
    </div>
  );
}

export function AmendmentDetailPage() {
  const { id } = useParams();
  const num = Number(id);
  const valid = Number.isInteger(num) && num >= 1;
  const status = useRead(getGovernanceStatus);
  if (!valid) return <Docket label="Amendment">This is not a valid amendment id.</Docket>;
  return (
    <div className="stack">
      <ReadBoundary read={status}>{(s) => <AmendmentPanel amendmentId={num} ownerAddress={s.owner} />}</ReadBoundary>
      <Link to="/constitution/amend" className="label">
        ← all amendments
      </Link>
    </div>
  );
}
