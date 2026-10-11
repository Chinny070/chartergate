import { Link, Navigate, useParams } from "react-router-dom";
import { Docket } from "../components/primitives";
import { getAppealRecord } from "../lib/genlayer/charterGate";
import { useRead } from "../lib/genlayer/hooks";

/** An appeal is shown inside its case. This route resolves an appeal id to that case. */
export function AppealRedirectPage() {
  const { id } = useParams();
  const num = Number(id);
  const valid = Number.isInteger(num) && num >= 1;
  const read = useRead(() => (valid ? getAppealRecord(num) : Promise.reject(new Error("Invalid appeal id"))), [num]);
  if (read.data) return <Navigate to={`/proposals/${read.data.appeal.proposal_id}`} replace />;
  return (
    <div className="stack">
      <Docket label={`Appeal ${valid ? num : ""}`}>{read.error ? `Could not find this appeal: ${read.error}` : "Finding the case this appeal belongs to…"}</Docket>
      <Link to="/proposals" className="label">
        ← all proposals
      </Link>
    </div>
  );
}
