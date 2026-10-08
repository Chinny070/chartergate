import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { NetworkBadge, WalletButton } from "../components/WalletControls";
import { Button } from "../components/primitives";

const NAV = [
  { to: "/", label: "COURT", end: true },
  { to: "/proposals", label: "PROPOSALS" },
  { to: "/constitution", label: "CONSTITUTION", end: true },
  { to: "/evidence", label: "EVIDENCE" },
  { to: "/precedent", label: "PRECEDENT" },
  { to: "/constitution/amend", label: "AMENDMENTS" },
  { to: "/accountability", label: "ACCOUNTABILITY" },
];

export function AppShell() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <header className="shell-header">
        <div className="container shell-header__bar">
          <NavLink to="/" className="wordmark" onClick={() => setOpen(false)}>
            CHARTER<b>GATE</b>
          </NavLink>
          <nav className="nav" aria-label="Primary">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end}>
                {n.label}
              </NavLink>
            ))}
          </nav>
          <NetworkBadge />
          <WalletButton />
          <Button
            className="nav-toggle"
            variant="quiet"
            aria-expanded={open}
            aria-controls="drawer"
            onClick={() => setOpen((o) => !o)}
          >
            {open ? "CLOSE" : "MENU"}
          </Button>
        </div>
        {open && (
          <nav id="drawer" className="drawer" aria-label="Primary mobile">
            {NAV.map((n) => (
              <NavLink key={n.to} to={n.to} end={n.end} onClick={() => setOpen(false)}>
                {n.label}
              </NavLink>
            ))}
          </nav>
        )}
      </header>
      <main className="container">
        <Outlet />
      </main>
      <footer className="shell-footer">
        <div className="container label">
          Frontend + GenLayer Intelligent Contract only · no backend · StudioNet (gasless)
        </div>
      </footer>
    </>
  );
}
