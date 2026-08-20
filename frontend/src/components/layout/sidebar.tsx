import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  Shield,
  ShieldCheck,
  Search,
  Send,
  Settings,
  LogOut,
  Brain,
  BrainCircuit,
  Cable,
  Target,
  Webhook,
  TrendingUp,
  Layers3,
  FlaskConical,
  Calculator,
  BarChart3,
  BadgeDollarSign,
  Gauge,
  Activity,
  ArrowRightLeft,
  TimerReset,
  CheckCircle2,
  SlidersHorizontal,
  ClipboardCheck,
} from "lucide-react";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Overview" },
  { to: "/parser", icon: Search, label: "Discovery" },
  { to: "/audience", icon: Brain, label: "Audience" },
  { to: "/segments", icon: Target, label: "Opportunities" },
  { to: "/yield", icon: TrendingUp, label: "Expected Yield" },
  { to: "/portfolio", icon: Layers3, label: "Observational Portfolio" },
  { to: "/causal-portfolio", icon: Target, label: "Causal Portfolio" },
  { to: "/experiment-planner", icon: Calculator, label: "Experiment Planner" },
  { to: "/experiments", icon: FlaskConical, label: "Experiments" },
  { to: "/incremental-yield", icon: BarChart3, label: "Incremental Yield" },
  { to: "/contextual-yield", icon: BrainCircuit, label: "Contextual Yield" },
  { to: "/incremental-value", icon: BadgeDollarSign, label: "Incremental Value" },
  { to: "/contextual-value", icon: BadgeDollarSign, label: "Contextual Value" },
  { to: "/evidence-health", icon: Activity, label: "Evidence Health" },
  { to: "/capacity-allocation", icon: Layers3, label: "Capacity Allocation" },
  { to: "/capacity-economics", icon: Gauge, label: "Capacity Economics" },
  { to: "/campaigns", icon: Send, label: "Campaigns" },
  { to: "/campaign-preflight", icon: ClipboardCheck, label: "Execution Preflight" },
  { to: "/learning", icon: BrainCircuit, label: "Learning" },
  { to: "/outcome-sources", icon: Webhook, label: "Outcome Sources" },
  { to: "/connections", icon: Cable, label: "Connections" },
  { to: "/account-capacity", icon: ShieldCheck, label: "Account Capacity" },
  { to: "/adaptive-execution", icon: ArrowRightLeft, label: "Adaptive Execution" },
  { to: "/execution-sla", icon: TimerReset, label: "Execution SLA" },
  { to: "/execution-sla-calibration", icon: CheckCircle2, label: "SLA Calibration" },
  { to: "/sla-governance", icon: SlidersHorizontal, label: "SLA Governance" },
  { to: "/accounts", icon: Users, label: "Telegram Accounts" },
  { to: "/proxies", icon: Shield, label: "Proxies" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const handleLogout = () => {
    localStorage.removeItem("access_token");
    window.location.href = "/login";
  };

  return (
    <aside className="flex h-full w-60 flex-col border-r border-black/5 bg-white/80 backdrop-blur-sm">
      <div className="flex h-14 shrink-0 items-center gap-2 border-b border-black/5 px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink text-sm font-bold text-white">Q</div>
        <div>
          <span className="block text-sm font-semibold text-ink">Intent Intelligence</span>
          <span className="block text-[10px] uppercase tracking-wide text-muted">Qualive</span>
        </div>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {navItems.map((item) => (
          <NavLink key={item.to} to={item.to} end={item.to === "/"} className={({ isActive }) => cn("flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors", isActive ? "bg-ink text-white" : "text-muted hover:bg-stone-100 hover:text-ink")}>
            <item.icon className="h-4 w-4 shrink-0" />{item.label}
          </NavLink>
        ))}
      </nav>
      <div className="shrink-0 border-t border-black/5 p-3">
        <button onClick={handleLogout} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted transition-colors hover:bg-red-50 hover:text-red-600"><LogOut className="h-4 w-4" />Logout</button>
      </div>
    </aside>
  );
}
