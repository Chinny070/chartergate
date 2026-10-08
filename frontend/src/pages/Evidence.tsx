import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Badge, Docket } from "../components/primitives";
import { ReadBoundary } from "../components/common";
import { EvidenceCard, EvidenceList, EvidenceNotes } from "../components/Evidence";
import { STATUS_INFO } from "../lib/evidence";
import {
  EVIDENCE_STATUSES,
  getCharterSectionAtVersion,
  getEvidence,
  getEvidencePage,
  getProposal,
  LIMITS,
  type EvidenceStatus,
} from "../lib/genlayer/charterGate";
import { useRead } from "../lib/genlayer/hooks";

type Filter = "ALL" | EvidenceStatus;

/** The vault: every evidence record on the contract, newest first. */
export function EvidencePage() {
  const read = useRead(() => getEvidencePage(0, LIMITS.pageSize));
  const [filter, setFilter] = useState<Filter>("ALL");
  return (
    <div className="stack">
      <h1 style={{ fontSize: "clamp(2rem, 6vw, 4rem)" }}>Evidence vault</h1>
      <p className="muted" style={{ maxWidth: "62ch" }}>
        Sources that GenLayer fetched itself, with when, how, and what the validators agreed they read. Evidence is attached from a
        proposal's page. This is evidence, not a ruling: nothing here judges a proposal.
      </p>
      <ReadBoundary read={read}>
        {(list) => {
          const records = [...list].reverse().filter((r) => filter === "ALL" || r.status === filter);
          return (
            <>
              <div className="row" role="group" aria-label="Filter by status">
                {(["ALL", ...EVIDENCE_STATUSES] as Filter[]).map((f) => (
                  <button
                    key={f}
                    type="button"
                    className="chip"
                    aria-pressed={filter === f}
                    onClick={() => setFilter(f)}
                  >
                    {f === "ALL" ? "ALL" : STATUS_INFO[f].label}
                  </button>
                ))}
              </div>
              <EvidenceList
                records={records}
                empty={list.length === 0 ? "No evidence has been submitted yet." : "No evidence matches this filter."}
              />
            </>
          );
        }}
      </ReadBoundary>
    </div>
  );
}

/** One record in full, with the exact charter text it relates to, rebuilt from on-chain history. */
export function EvidenceDetailPage() {
  const { id } = useParams();
  const num = Number(id);
  const valid = Number.isInteger(num) && num >= 1;
  const read = useRead(() => (valid ? getEvidence(num) : Promise.reject(new Error("Invalid evidence id"))), [num]);

  return (
    <div className="stack">
      <ReadBoundary read={read}>
        {(record) => (
          <>
            <ProposalContext proposalId={record.proposal_id} />
            <div className="grid-2">
              <EvidenceWithCharter record={record} />
              <EvidenceNotes />
            </div>
          </>
        )}
      </ReadBoundary>
      <Link to="/evidence" className="label">
        ← evidence vault
      </Link>
    </div>
  );
}

function EvidenceWithCharter({ record }: { record: Parameters<typeof EvidenceCard>[0]["record"] }) {
  const rule = useRead(
    () =>
      record.related_section_id === ""
        ? Promise.resolve(null)
        : getCharterSectionAtVersion(record.related_section_id, record.related_revision_version),
    [record.related_section_id, record.related_revision_version],
  );
  return (
    <div className="stack">
      <EvidenceCard record={record} detail />
      {record.related_section_id !== "" && (
        <Docket label={`Charter rule §${record.related_section_id} as it read at v${record.related_revision_version}`}>
          <ReadBoundary read={rule}>
            {(r) =>
              r === null ? null : (
                <>
                  <strong>{r.title}</strong>
                  <p style={{ whiteSpace: "pre-wrap" }}>{r.body}</p>
                  {!r.active && <Badge tone="ineligible">Deactivated at this version</Badge>}
                </>
              )
            }
          </ReadBoundary>
        </Docket>
      )}
    </div>
  );
}

function ProposalContext({ proposalId }: { proposalId: number }) {
  const read = useRead(() => getProposal(proposalId), [proposalId]);
  return (
    <ReadBoundary read={read}>
      {(p) => (
        <Docket label="Evidence for">
          <Link to={`/proposals/${p.proposal_id}`}>
            <strong>{p.title}</strong>
          </Link>
          <span className="muted"> · submitted under charter v{p.charter_version_at_submission}</span>
        </Docket>
      )}
    </ReadBoundary>
  );
}
