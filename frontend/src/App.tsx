import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "sonner";
import { AppLayout } from "@/components/layout/layout";
import DashboardPage from "@/pages/dashboard";
import AccountsPage from "@/pages/accounts";
import AccountCapacityPage from "@/pages/account-capacity";
import AdaptiveExecutionPage from "@/pages/adaptive-execution";
import ExecutionSLAPage from "@/pages/execution-sla";
import ExecutionSLACalibrationPage from "@/pages/execution-sla-calibration";
import SLAGovernancePage from "@/pages/sla-governance";
import CampaignPreflightPage from "@/pages/campaign-preflight";
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
import CausalPortfolioPage from "@/pages/causal-portfolio";
import ExperimentsPage from "@/pages/experiments";
import ExperimentPlannerPage from "@/pages/experiment-planner";
import IncrementalYieldPage from "@/pages/incremental-yield";
import ContextualYieldPage from "@/pages/contextual-yield";
import IncrementalValuePage from "@/pages/incremental-value";
import ContextualValuePage from "@/pages/contextual-value";
import CapacityAllocationPage from "@/pages/capacity-allocation";
import CapacityEconomicsPage from "@/pages/capacity-economics";
import EvidenceHealthPage from "@/pages/evidence-health";
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
            <Route path="account-capacity" element={<AccountCapacityPage />} />
            <Route path="adaptive-execution" element={<AdaptiveExecutionPage />} />
            <Route path="execution-sla" element={<ExecutionSLAPage />} />
            <Route path="execution-sla-calibration" element={<ExecutionSLACalibrationPage />} />
            <Route path="sla-governance" element={<SLAGovernancePage />} />
            <Route path="campaign-preflight" element={<CampaignPreflightPage />} />
            <Route path="proxies" element={<ProxiesPage />} />
            <Route path="parser" element={<ParserPage />} />
            <Route path="audience" element={<AudiencePage />} />
            <Route path="segments" element={<SegmentsPage />} />
            <Route path="yield" element={<YieldForecastPage />} />
            <Route path="portfolio" element={<OpportunityPortfolioPage />} />
            <Route path="causal-portfolio" element={<CausalPortfolioPage />} />
            <Route path="experiment-planner" element={<ExperimentPlannerPage />} />
            <Route path="experiments" element={<ExperimentsPage />} />
            <Route path="incremental-yield" element={<IncrementalYieldPage />} />
            <Route path="contextual-yield" element={<ContextualYieldPage />} />
            <Route path="incremental-value" element={<IncrementalValuePage />} />
            <Route path="contextual-value" element={<ContextualValuePage />} />
            <Route path="evidence-health" element={<EvidenceHealthPage />} />
            <Route path="capacity-allocation" element={<CapacityAllocationPage />} />
            <Route path="capacity-economics" element={<CapacityEconomicsPage />} />
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
