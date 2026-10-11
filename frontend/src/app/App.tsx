import { BrowserRouter, Route, Routes } from "react-router-dom";
import { WalletProvider } from "../lib/genlayer/WalletProvider";
import { CharterPage } from "../pages/Charter";
import { EvidenceDetailPage, EvidencePage } from "../pages/Evidence";
import { AccountabilityPage } from "../pages/Accountability";
import { AmendmentDetailPage, AmendmentsPage } from "../pages/Amendments";
import { AppealRedirectPage } from "../pages/AppealRedirect";
import { Home, NotFound } from "../pages/Pages";
import { PrecedentPage } from "../pages/Precedent";
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
            <Route path="constitution/amend" element={<AmendmentsPage />} />
            <Route path="constitution/amend/:id" element={<AmendmentDetailPage />} />
            <Route path="evidence" element={<EvidencePage />} />
            <Route path="evidence/:id" element={<EvidenceDetailPage />} />
            <Route path="precedent" element={<PrecedentPage />} />
            <Route path="appeals/:id" element={<AppealRedirectPage />} />
            <Route path="accountability" element={<AccountabilityPage />} />
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </WalletProvider>
  );
}
