import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { AppLayout } from "@/components/layout/layout";
import DashboardPage from "@/pages/dashboard";
import AccountsPage from "@/pages/accounts";
import ConnectionsPage from "@/pages/connections";
import ProxiesPage from "@/pages/proxies";
import ParserPage from "@/pages/parser";
import AudiencePage from "@/pages/audience";
import SegmentsPage from "@/pages/segments";
import CampaignsPage from "@/pages/campaigns";
import LearningPage from "@/pages/learning";
import OutcomeSourcesPage from "@/pages/outcome-sources";
import YieldForecastPage from "@/pages/yield-forecast";
import OpportunityPortfolioPage from "@/pages/opportunity-portfolio";
import ExperimentsPage from "@/pages/experiments";
import ExperimentPlannerPage from "@/pages/experiment-planner";
import LoginPage from "@/pages/login";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 10_000,
    },
  },
});

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem("access_token");
  if (!token) return <Navigate to="/login" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/" element={<PrivateRoute><AppLayout /></PrivateRoute>}>
            <Route index element={<DashboardPage />} />
            <Route path="connections" element={<ConnectionsPage />} />
            <Route path="accounts" element={<AccountsPage />} />
            <Route path="proxies" element={<ProxiesPage />} />
            <Route path="parser" element={<ParserPage />} />
            <Route path="audience" element={<AudiencePage />} />
            <Route path="segments" element={<SegmentsPage />} />
            <Route path="yield" element={<YieldForecastPage />} />
            <Route path="portfolio" element={<OpportunityPortfolioPage />} />
            <Route path="experiment-planner" element={<ExperimentPlannerPage />} />
            <Route path="experiments" element={<ExperimentsPage />} />
            <Route path="campaigns" element={<CampaignsPage />} />
            <Route path="learning" element={<LearningPage />} />
            <Route path="outcome-sources" element={<OutcomeSourcesPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
      <Toaster position="top-right" richColors />
    </QueryClientProvider>
  );
}