import type { ReactNode } from "react";
import { CHARTERGATE_ADDRESS } from "../config/chain";
import type { ReadState } from "../lib/genlayer/hooks";
import { Docket, EmptyState, ErrorBanner } from "./primitives";

/** Shows loading / not-deployed / error states for an on-chain read, then the children. */
export function ReadBoundary<T>({ read, children }: { read: ReadState<T>; children: (data: T) => ReactNode }) {
  if (read.notDeployed) {
    return (
      <EmptyState title="Contract not deployed">
        Set <span className="hash">VITE_CHARTERGATE_ADDRESS</span> in <span className="hash">frontend/.env</span> after
        you deploy CharterGate to StudioNet. {CHARTERGATE_ADDRESS}
      </EmptyState>
    );
  }
  if (read.error) return <ErrorBanner title="Could not read the contract">{read.error}</ErrorBanner>;
  if (read.loading || read.data === null) return <Docket label="Loading">Reading finalized state from GenLayer…</Docket>;
  return <>{children(read.data)}</>;
}

/** Human-readable time beside the canonical on-chain value (spec: show both). */
export function ChainTime({ label, value }: { label: string; value: string }) {
  const d = new Date(value);
  const human = Number.isNaN(d.getTime())
    ? value
    : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }) + " UTC";
  return (
    <div>
      <div className="label">{label}</div>
      <div>{human}</div>
      <div className="hash" style={{ opacity: 0.7 }}>
        {value}
      </div>
    </div>
  );
}

export function Field({
  label,
  value,
  onChange,
  max,
  multiline,
  hint,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  max: number;
  multiline?: boolean;
  hint?: string;
  disabled?: boolean;
}) {
  const over = value.trim().length > max;
  const props = {
    value,
    disabled,
    onChange: (e: { target: { value: string } }) => onChange(e.target.value),
    "aria-invalid": over,
  };
  return (
    <label className="field">
      <span className="label">{label}</span>
      {multiline ? <textarea rows={5} {...props} /> : <input type="text" {...props} />}
      <span className="field__meta" data-over={over}>
        {hint && <span>{hint} · </span>}
        {value.trim().length}/{max}
      </span>
    </label>
  );
}
