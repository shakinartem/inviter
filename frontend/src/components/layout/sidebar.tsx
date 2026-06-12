import { NavLink } from "react-router-dom";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Users,
  Shield,
  Search,
  Send,
  Settings,
  LogOut,
} from "lucide-react";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/accounts", icon: Users, label: "Accounts" },
  { to: "/proxies", icon: Shield, label: "Proxies" },
  { to: "/parser", icon: Search, label: "Parser" },
  { to: "/campaigns", icon: Send, label: "Campaigns" },
  { to: "/settings", icon: Settings, label: "Settings" },
];

export function Sidebar() {
  const handleLogout = () => {
    localStorage.removeItem("access_token");
    window.location.href = "/login";
  };

  return (
    <aside className="flex h-full w-60 flex-col border-r border-black/5 bg-white/80 backdrop-blur-sm">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2 border-b border-black/5 px-5">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink text-sm font-bold text-white">
          T
        </div>
        <span className="text-sm font-semibold text-ink">Inviter Pro</span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 p-3">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-ink text-white"
                  : "text-muted hover:bg-stone-100 hover:text-ink",
              )
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>

      {/* Logout */}
      <div className="border-t border-black/5 p-3">
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted transition-colors hover:bg-red-50 hover:text-red-600"
        >
          <LogOut className="h-4 w-4" />
          Logout
        </button>
      </div>
    </aside>
  );
}