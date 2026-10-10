import { Link } from "react-router-dom";
import { Badge } from "./primitives";
import { ADVISORY_NOTE, describeRule, hasPrecedent, NO_PRECEDENT, precedentBySection, TREATMENT_INFO } from "../lib/precedent";
import { getPrecedentCase, type CharterRevision, type ReviewPrecedents } from "../lib/genlayer/charterGate";
import { useRead } from "../lib/genlayer/hooks";
import { FINDING_INFO } from "../lib/review";

const sectionTitle = (sections: readonly CharterRevision[], id: string) => sections.find((s) => s.section_id === id)?.title ?? "";

/** One prior ruling, loaded only when the reader opens it (a single bounded read). */
function PrecedentCaseView({ reviewId, sectionId }: { reviewId: number; sectionId: string }) {
  const read = useRead(() => getPrecedentCase(reviewId, sectionId), [reviewId, sectionId]);
  if (read.error) return <p className="label">Could not read the prior ruling: {read.error}</p>;
  if (read.data === null) return <p className="muted">Reading the prior ruling…</p>;
  const c = read.data;
  const info = FINDING_INFO[c.finding.finding];
  return (
    <div className="stack" aria-label={`Prior review ${reviewId}`}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <span className="label">Prior ruling · {describeRule(c.rule)}</span>
        <Badge tone={info.tone}>{info.label}</Badge>
      </div>
      <div className="label">
        Judged {c.revision_number === 1 ? "the original proposal" : `revision ${c.revision_number}`} under charter v{c.review.charter_version} · overall verdict {c.review.verdict}
      </div>
      <strong>{c.title}</strong>
      <p style={{ whiteSpace: "pre-wrap" }}>{c.description}</p>
      <p className="muted">{c.finding.rationale}</p>
      {c.finding.evidence_ids.length > 0 && (
        <p>
          <span className="label">Evidence it relied on </span>
          {c.evidence.map((e, i) => (
            <span key={e.evidence_id}>
              {i > 0 && ", "}
              <Link to={`/evidence/${e.evidence_id}`}>#{e.evidence_id}</Link> ({e.normalized_fact})
            </span>
          ))}
        </p>
      )}
      <div className="label">Review hash</div>
      <div className="hash">{c.review.review_hash}</div>
      <p className="muted">That evidence belongs to the prior case. It is not evidence about the case you are reading.</p>
    </div>
  );
}

/** The precedent memory of one review: which prior rulings were available per rule, and which were followed or distinguished. */
export function PrecedentMemory({ precedents, sections }: { precedents: ReviewPrecedents; sections: readonly CharterRevision[] }) {
  const ids = sections.filter((s) => s.active).map((s) => s.section_id);
  return (
    <div className="stack" aria-label="Precedent memory">
      <div className="label">PRECEDENT MEMORY</div>
      <p className="muted">{ADVISORY_NOTE}</p>
      {!hasPrecedent(precedents) ? (
        <p>{NO_PRECEDENT}</p>
      ) : (
        <>
          {precedentBySection(precedents, ids).map((s) => (
            <div key={s.sectionId} className="finding" data-precedent-section={s.sectionId}>
              <strong>
                §{s.sectionId} {sectionTitle(sections, s.sectionId)}
              </strong>
              {s.candidates.length === 0 ? (
                <p className="muted">{NO_PRECEDENT}</p>
              ) : (
                <>
                  <p className="muted">
                    Same rule: {describeRule(s.rule)} · available prior rulings:{" "}
                    {s.candidates.map((c, i) => (
                      <span key={c.precedent_review_id}>
                        {i > 0 && ", "}Review #{String(c.precedent_review_id).padStart(3, "0")}
                      </span>
                    ))}
                  </p>
                  {s.citations.length === 0 && <p className="muted">No prior ruling was materially relied on.</p>}
                  {s.citations.map((c) => {
                    const t = TREATMENT_INFO[c.treatment];
                    return (
                      <div key={c.precedent_review_id} className="stack">
                        <div className="row" style={{ justifyContent: "space-between" }}>
                          <span>Prior Review #{String(c.precedent_review_id).padStart(3, "0")}</span>
                          <Badge tone={t.tone}>{t.label}</Badge>
                        </div>
                        <p className="muted">{t.explain}</p>
                        {c.treatment === "DISTINGUISHED" && c.reason !== "" && (
                          <p>
                            <span className="label">Material difference </span>
                            {c.reason}
                          </p>
                        )}
                        {c.treatment === "FOLLOWED" && c.reason !== "" && <p className="muted">{c.reason}</p>}
                      </div>
                    );
                  })}
                  <details>
                    <summary>Inspect the prior rulings for this rule</summary>
                    <div className="stack">
                      {s.candidates.map((c) => (
                        <PrecedentCaseView key={c.precedent_review_id} reviewId={c.precedent_review_id} sectionId={s.sectionId} />
                      ))}
                    </div>
                  </details>
                </>
              )}
            </div>
          ))}
          <div className="label">Precedent set hash</div>
          <div className="hash" title={precedents.precedent_set_hash}>
            {precedents.precedent_set_hash}
          </div>
          <p className="muted">
            The precedent set hash commits to exactly which prior rulings were available. Later reviews never change it. It does not commit to any
            explanatory wording.
          </p>
        </>
      )}
    </div>
  );
}
