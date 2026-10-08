import { BrowserRouter, Route, Routes } from "react-router-dom";
import { WalletProvider } from "../lib/genlayer/WalletProvider";
import { CharterPage } from "../pages/Charter";
import { EvidenceDetailPage, EvidencePage } from "../pages/Evidence";
import { Home, Planned } from "../pages/Pages";
import { ProposalDetailPage, ProposalsPage, SubmitProposalPage } from "../pages/Proposals";
import { AppShell } from "./AppShell";

export function App() {
  return (
    <WalletProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<Home />} />
            <Route path="proposals" element={<ProposalsPage />} />
            <Route path="proposals/:id" element={<ProposalDetailPage />} />
            <Route path="submit" element={<SubmitProposalPage />} />
            <Route path="constitution" element={<CharterPage />} />
            <Route path="constitution/amend" element={<Planned title="Amendments" stage="a later stage" />} />
            <Route path="evidence" element={<EvidencePage />} />
            <Route path="evidence/:id" element={<EvidenceDetailPage />} />
            <Route path="precedent" element={<Planned title="Precedent" stage="a later stage" />} />
            <Route path="appeals/:id" element={<Planned title="Appeal" stage="a later stage" />} />
            <Route path="accountability" element={<Planned title="Accountability" stage="a later stretch stage" />} />
            <Route path="*" element={<Planned title="Not found" stage="n/a" />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </WalletProvider>
  );
}
