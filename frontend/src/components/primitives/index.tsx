import type { ButtonHTMLAttributes, ReactNode } from "react";

export type Tone = "eligible" | "warning" | "ineligible" | "active" | "final" | "precedent";

export function Button({
  variant,
  className = "",
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "quiet" }) {
  const v = variant ? ` btn--${variant}` : "";
  return <button type="button" className={`btn${v} ${className}`} {...rest} />;
}

export function Badge({ tone, children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`badge${tone ? ` tone-${tone}` : ""}`}>{children}</span>;
}

export function Stamp({ tone = "final", children }: { tone?: Tone; children: ReactNode }) {
  return <span className={`stamp tone-${tone}`}>{children}</span>;
}

/** Court-paper surface with a clipped corner: for documents (constitution, rulings). */
export function Paper({ label, children }: { label?: string; children: ReactNode }) {
  return (
    <section className="paper">
      {label && <div className="label">{label}</div>}
      {children}
    </section>
  );
}

/** Dark bordered surface: for case metadata, evidence rows, status. */
export function Docket({ label, children }: { label?: string; children: ReactNode }) {
  return (
    <section className="docket">
      {label && <div className="label">{label}</div>}
      {children}
    </section>
  );
}

export function ErrorBanner({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="banner" role="alert">
      <strong>{title}</strong>
      {children && <div>{children}</div>}
    </div>
  );
}

export function EmptyState({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="docket">
      <h3>{title}</h3>
      {children && <p style={{ color: "var(--text-muted)" }}>{children}</p>}
    </div>
  );
}
