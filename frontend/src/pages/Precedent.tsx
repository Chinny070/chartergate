import { Link } from "react-router-dom";
import { Badge, Docket, EmptyState } from "../components/primitives";
import { ReadBoundary } from "../components/common";
import { ADVISORY_NOTE } from "../lib/precedent";
import { getPrecedentOverview } from "../lib/genlayer/charterGate";
import { useRead } from "../lib/genlayer/hooks";

/** The exact rules of the current charter and how many reviews interpreted each. One read. */
export function PrecedentPage() {
  const read = useRead(getPrecedentOverview);
  return (
    <div className="stack">
      <h1 style={{ fontSize: "clamp(2rem, 6vw, 4rem)" }}>Precedent</h1>
      <Docket label="How precedent works here">
        <div className="stack">
          <p>{ADVISORY_NOTE}</p>
          <p className="muted">
            Earlier rulings are matched only by the exact rule: a section id and the section revision that applied (for example §s3 revision 4). A rule that was amended is a different rule, so its old
            rulings are not matched to the new wording. A review that the appeal process modified or reversed is no longer offered as automatic precedent. Precedent is never evidence about a case.
          </p>
        </div>
      </Docket>
      <ReadBoundary read={read}>
        {(rules) =>
          rules.length === 0 ? (
            <EmptyState title="No active rules">The charter has no active sections yet.</EmptyState>
          ) : (
            <div className="stack">
              {rules.map((r) => (
                <Docket key={r.rule} label={`§${r.section_id} · ${r.rule}`}>
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <strong>{r.title}</strong>
                    <Badge tone={r.review_count > 0 ? "precedent" : "active"}>
                      {r.review_count} {r.review_count === 1 ? "review" : "reviews"}
                    </Badge>
                  </div>
                  <p className="muted">
                    {r.review_count === 0
                      ? "No review has interpreted this exact rule yet, so a new case under it has no precedent."
                      : `Most recent: ${[...r.newest_review_ids]
                          .reverse()
                          .map((id) => `review #${String(id).padStart(3, "0")}`)
                          .join(", ")}. Open a case to see how its review used earlier rulings.`}
                  </p>
                </Docket>
              ))}
            </div>
          )
        }
      </ReadBoundary>
      <Link to="/proposals" className="label">
        → open a case
      </Link>
    </div>
  );
}
