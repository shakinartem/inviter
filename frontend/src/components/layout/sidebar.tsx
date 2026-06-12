import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { Globe, HelpCircle, LayoutDashboard, LogOut, Search, Send, Settings, Shield, Users } from "lucide-react";

import { apiClient } from "@/lib/api-client";
import { getLocale, setLocale, t, type Locale } from "@/lib/i18n";
import { cn } from "@/lib/utils";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

interface SettingsData {
  site_name: string | null;
  logo_path: string | null;
  language: string;
}

function NavItems() {
  return (
    <>
      <NavLink
        to="/"
        end
        className={({ isActive }) =>
          cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            isActive ? "bg-ink text-white" : "text-muted hover:bg-stone-100 hover:text-ink",
          )
        }
      >
        <LayoutDashboard className="h-4 w-4" />
        {t("dashboard")}
      </NavLink>
      <NavLink
        to="/accounts"
        className={({ isActive }) =>
          cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            isActive ? "bg-ink text-white" : "text-muted hover:bg-stone-100 hover:text-ink",
          )
        }
      >
        <Users className="h-4 w-4" />
        {t("accounts")}
      </NavLink>
      <NavLink
        to="/proxies"
        className={({ isActive }) =>
          cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            isActive ? "bg-ink text-white" : "text-muted hover:bg-stone-100 hover:text-ink",
          )
        }
      >
        <Shield className="h-4 w-4" />
        {t("proxies")}
      </NavLink>
      <NavLink
        to="/parser"
        className={({ isActive }) =>
          cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            isActive ? "bg-ink text-white" : "text-muted hover:bg-stone-100 hover:text-ink",
          )
        }
      >
        <Search className="h-4 w-4" />
        {t("parser")}
      </NavLink>
      <NavLink
        to="/campaigns"
        className={({ isActive }) =>
          cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            isActive ? "bg-ink text-white" : "text-muted hover:bg-stone-100 hover:text-ink",
          )
        }
      >
        <Send className="h-4 w-4" />
        {t("campaigns")}
      </NavLink>
      <NavLink
        to="/settings"
        className={({ isActive }) =>
          cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            isActive ? "bg-ink text-white" : "text-muted hover:bg-stone-100 hover:text-ink",
          )
        }
      >
        <Settings className="h-4 w-4" />
        {t("settings")}
      </NavLink>
      <NavLink
        to="/help"
        className={({ isActive }) =>
          cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
            isActive ? "bg-ink text-white" : "text-muted hover:bg-stone-100 hover:text-ink",
          )
        }
      >
        <HelpCircle className="h-4 w-4" />
        {t("help")}
      </NavLink>
    </>
  );
}

export function Sidebar() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [locale, setLocaleState] = useState<Locale>(getLocale());

  useEffect(() => {
    apiClient
      .get<SettingsData>("/settings/")
      .then((res) => setSettings(res.data))
      .catch(() => {});
  }, []);

  const handleToggleLocale = () => {
    const next: Locale = locale === "ru" ? "en" : "ru";
    setLocale(next);
    setLocaleState(next);
    window.location.reload();
  };

  const handleLogout = () => {
    localStorage.removeItem("access_token");
    window.location.href = "/login";
  };

  const baseUrl = API_URL.replace("/api/v1", "");

  return (
    <aside className="flex h-full w-60 flex-col border-r border-black/5 bg-white/80 backdrop-blur-sm">
      <div className="flex h-14 items-center gap-2 border-b border-black/5 px-5">
        {settings?.logo_path ? (
          <img
            src={`${baseUrl}/${settings.logo_path}`}
            alt={settings.site_name ?? "Logo"}
            className="h-8 w-8 rounded-lg object-contain"
          />
        ) : (
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-ink text-sm font-bold text-white">
            T
          </div>
        )}
        <span className="text-sm font-semibold text-ink">
          {settings?.site_name || t("logoPlaceholder")}
        </span>
      </div>

      <nav className="flex-1 space-y-1 p-3">
        <NavItems />
      </nav>

      <div className="space-y-1 border-t border-black/5 p-3">
        <button
          onClick={handleToggleLocale}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted transition-colors hover:bg-stone-100 hover:text-ink"
        >
          <Globe className="h-4 w-4" />
          {locale === "ru" ? "EN" : "RU"}
        </button>
        <button
          onClick={handleLogout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium text-muted transition-colors hover:bg-red-50 hover:text-red-600"
        >
          <LogOut className="h-4 w-4" />
          {t("logout")}
        </button>
      </div>
    </aside>
  );
}
