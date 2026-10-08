import { useState } from "react";
import { Badge, Button, Docket, Paper } from "../components/primitives";
import { ChainTime, Field, ReadBoundary } from "../components/common";
import { sameAddress, shortAddress } from "../lib/format";
import { TransactionTimeline } from "../components/TransactionTimeline";
import {
  addCharterSection,
  deactivateCharterSection,
  getCharterSectionsPage,
  getDaoMetadata,
  LIMITS,
  SECTION_ID_PATTERN,
  updateCharterSection,
  type CharterSection,
} from "../lib/genlayer/charterGate";
import { useRead, useTx } from "../lib/genlayer/hooks";
import { useWallet } from "../lib/genlayer/wallet-context";

export function CharterPage() {
  const wallet = useWallet();
  const meta = useRead(getDaoMetadata);
  const sections = useRead(() => getCharterSectionsPage(0, LIMITS.pageSize));
  const { tx, busy, run, reset } = useTx();
  const isOwner = sameAddress(wallet.address, meta.data?.owner);

  const refresh = () => {
    meta.reload();
    sections.reload();
  };

  async function mutate(send: Parameters<typeof run>[0]) {
    if (!wallet.client) return false;
    const final = await run(send, wallet.client);
    if (final.phase === "finalized") refresh();
    return final.phase === "finalized";
  }

  return (
    <div className="stack">
      <h1 style={{ fontSize: "clamp(2rem, 6vw, 4rem)" }}>Charter</h1>
      <ReadBoundary read={meta}>
        {(m) => (
          <Docket label={m.dao_name}>
            <p>{m.dao_description}</p>
            <div className="row">
              <Badge tone="final">Charter v{m.charter_version}</Badge>
              <Badge>{m.section_count} sections</Badge>
              <span className="label">owner {shortAddress(m.owner)}</span>
            </div>
            <div className="grid-2" style={{ marginTop: 16 }}>
              <ChainTime label="Created" value={m.created_at} />
              <ChainTime label="Last charter change" value={m.updated_at} />
            </div>
          </Docket>
        )}
      </ReadBoundary>

      {isOwner && (
        <AddSection busy={busy} onAdd={(id, t, b) => mutate((c, on) => addCharterSection(c, id, t, b, on))} />
      )}
      {wallet.connection === "ready" && meta.data && !isOwner && (
        <p className="label">Read-only: only the contract owner can change the charter.</p>
      )}
      {tx.phase !== "ready" && (
        <Docket label="Transaction">
          <TransactionTimeline tx={tx} />
          {!busy && (
            <Button variant="quiet" onClick={reset}>
              DISMISS
            </Button>
          )}
        </Docket>
      )}

      <ReadBoundary read={sections}>
        {(list) =>
          list.length === 0 ? (
            <Docket label="No sections yet">The owner has not added any charter sections.</Docket>
          ) : (
            <div className="stack">
              {list.map((s) => (
                <SectionCard
                  key={s.section_id}
                  section={s}
                  canEdit={isOwner}
                  busy={busy}
                  onSave={(t, b) => mutate((c, on) => updateCharterSection(c, s.section_id, t, b, on))}
                  onDeactivate={() => mutate((c, on) => deactivateCharterSection(c, s.section_id, on))}
                />
              ))}
            </div>
          )
        }
      </ReadBoundary>
    </div>
  );
}

function AddSection({ busy, onAdd }: { busy: boolean; onAdd: (id: string, t: string, b: string) => Promise<boolean> }) {
  const [id, setId] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const valid =
    id.length > 0 &&
    id.length <= LIMITS.sectionId &&
    SECTION_ID_PATTERN.test(id) &&
    title.trim().length > 0 &&
    title.trim().length <= LIMITS.sectionTitle &&
    body.trim().length > 0 &&
    body.trim().length <= LIMITS.sectionBody;

  return (
    <Docket label="Owner · add section">
      <div className="stack">
        <Field label="Section id" value={id} onChange={setId} max={LIMITS.sectionId} hint="letters, digits . _ -" disabled={busy} />
        <Field label="Title" value={title} onChange={setTitle} max={LIMITS.sectionTitle} disabled={busy} />
        <Field label="Body" value={body} onChange={setBody} max={LIMITS.sectionBody} multiline disabled={busy} />
        <Button
          variant="primary"
          disabled={!valid || busy}
          onClick={async () => {
            if (await onAdd(id, title, body)) {
              setId("");
              setTitle("");
              setBody("");
            }
          }}
        >
          ADD SECTION
        </Button>
      </div>
    </Docket>
  );
}

function SectionCard(props: {
  section: CharterSection;
  canEdit: boolean;
  busy: boolean;
  onSave: (title: string, body: string) => Promise<boolean>;
  onDeactivate: () => Promise<boolean>;
}) {
  const { section: s, canEdit, busy } = props;
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(s.title);
  const [body, setBody] = useState(s.body);
  const valid =
    title.trim().length > 0 && title.trim().length <= LIMITS.sectionTitle && body.trim().length > 0 && body.trim().length <= LIMITS.sectionBody;

  return (
    <Paper label={`§${s.section_id}`}>
      <div className="row" style={{ justifyContent: "space-between" }}>
        <h2 style={{ fontSize: "2rem", opacity: s.active ? 1 : 0.55 }}>{s.title}</h2>
        {s.active ? <Badge tone="eligible">Active</Badge> : <Badge tone="ineligible">Deactivated</Badge>}
      </div>
      {editing ? (
        <div className="stack">
          <Field label="Title" value={title} onChange={setTitle} max={LIMITS.sectionTitle} disabled={busy} />
          <Field label="Body" value={body} onChange={setBody} max={LIMITS.sectionBody} multiline disabled={busy} />
          <div className="row">
            <Button
              variant="primary"
              disabled={!valid || busy}
              onClick={async () => {
                if (await props.onSave(title, body)) setEditing(false);
              }}
            >
              SAVE
            </Button>
            <Button variant="quiet" disabled={busy} onClick={() => setEditing(false)}>
              CANCEL
            </Button>
          </div>
        </div>
      ) : (
        <p style={{ whiteSpace: "pre-wrap" }}>{s.body}</p>
      )}
      <div className="grid-2">
        <ChainTime label="Created" value={s.created_at} />
        <ChainTime label="Updated" value={s.updated_at} />
      </div>
      {canEdit && s.active && !editing && (
        <div className="row" style={{ marginTop: 12 }}>
          <Button variant="quiet" disabled={busy} onClick={() => setEditing(true)}>
            EDIT
          </Button>
          <Button variant="quiet" disabled={busy} onClick={() => void props.onDeactivate()}>
            DEACTIVATE
          </Button>
        </div>
      )}
    </Paper>
  );
}
