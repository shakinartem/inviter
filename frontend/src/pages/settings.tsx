import { useEffect, useState } from "react";
import { toast } from "sonner";

import { apiClient } from "@/lib/api-client";
import { t, getLocale, setLocale, type Locale } from "@/lib/i18n";

interface SettingsData {
  id: string;
  language: string;
  site_name: string | null;
  logo_path: string | null;
  help_text: string | null;
  system_config: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000/api/v1";

function getAssetBaseUrl() {
  return API_URL.replace(/\/api\/v1\/?$/, "");
}

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [language, setLanguage] = useState<Locale>(getLocale());
  const [siteName, setSiteName] = useState("");
  const [helpText, setHelpText] = useState("");
  const [systemConfig, setSystemConfig] = useState("{}");
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [removingLogo, setRemovingLogo] = useState(false);

  const refreshSettings = async () => {
    const res = await apiClient.get<SettingsData>("/settings/");
    const data = res.data;
    setSettings(data);
    setLanguage((data.language as Locale) || "ru");
    setSiteName(data.site_name ?? "");
    setHelpText(data.help_text ?? "");
    setSystemConfig(data.system_config ? JSON.stringify(data.system_config, null, 2) : "{}");
  };

  useEffect(() => {
    refreshSettings().catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const parsedConfig = JSON.parse(systemConfig);
      await apiClient.put("/settings/", {
        language,
        site_name: siteName,
        help_text: helpText,
        system_config: parsedConfig,
      });
      setLocale(language);
      toast.success(t("saved"));
      await refreshSettings();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : t("saveError");
      toast.error(message);
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadingLogo(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      await apiClient.post("/settings/logo", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(t("logoUploaded"));
      await refreshSettings();
    } catch {
      toast.error(t("logoUploadError"));
    } finally {
      setUploadingLogo(false);
      e.target.value = "";
    }
  };

  const handleLogoRemove = async () => {
    setRemovingLogo(true);
    try {
      await apiClient.delete("/settings/logo");
      toast.success(t("logoRemoved"));
      await refreshSettings();
    } catch {
      toast.error(t("logoRemoveError"));
    } finally {
      setRemovingLogo(false);
    }
  };

  const baseUrl = getAssetBaseUrl();

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-ink">{t("settingsTitle")}</h1>
        <p className="mt-1 text-sm text-muted">{t("settingsSubtitle")}</p>
      </div>

      <section className="rounded-xl border border-black/5 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">
          {t("language")}
        </h2>
        <div className="flex gap-3">
          <button
            onClick={() => setLanguage("ru")}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              language === "ru" ? "bg-ink text-white" : "bg-stone-100 text-muted hover:bg-stone-200"
            }`}
          >
            RU {t("languageRu")}
          </button>
          <button
            onClick={() => setLanguage("en")}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              language === "en" ? "bg-ink text-white" : "bg-stone-100 text-muted hover:bg-stone-200"
            }`}
          >
            EN {t("languageEn")}
          </button>
        </div>
      </section>

      <section className="rounded-xl border border-black/5 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">
          {t("siteName")}
        </h2>
        <input
          type="text"
          value={siteName}
          onChange={(e) => setSiteName(e.target.value)}
          placeholder={t("siteNamePlaceholder")}
          className="w-full rounded-lg border border-black/10 bg-surface px-4 py-2.5 text-sm text-ink placeholder:text-muted/50 focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
        />
      </section>

      <section className="rounded-xl border border-black/5 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">
          {t("uploadLogo")}
        </h2>
        {settings?.logo_path ? (
          <div className="mb-4 space-y-3">
            <div>
              <p className="mb-2 text-xs text-muted">{t("logoCurrent")}</p>
              <img
                src={`${baseUrl}/${settings.logo_path}`}
                alt={settings.site_name ?? "Logo"}
                className="h-16 w-auto rounded-lg border border-black/10 bg-stone-50 object-contain"
              />
            </div>
            <button
              type="button"
              onClick={handleLogoRemove}
              disabled={removingLogo}
              className="rounded-lg border border-red-200 px-4 py-2 text-sm font-medium text-red-600 transition-colors hover:bg-red-50 disabled:opacity-50"
            >
              {removingLogo ? t("saving") : t("removeLogo")}
            </button>
          </div>
        ) : (
          <p className="mb-4 text-sm text-muted">{t("noLogo")}</p>
        )}
        <label
          className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-black/20 px-4 py-3 text-sm text-muted transition-colors hover:border-ink hover:text-ink ${
            uploadingLogo ? "pointer-events-none opacity-50" : ""
          }`}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-4 w-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          {uploadingLogo ? "..." : t("uploadLogo")}
          <input
            type="file"
            accept=".png,.jpg,.jpeg,.webp"
            onChange={handleLogoUpload}
            disabled={uploadingLogo}
            className="hidden"
          />
        </label>
      </section>

      <section className="rounded-xl border border-black/5 bg-white p-6 shadow-sm">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">
          {t("helpText")}
        </h2>
        <p className="mb-4 text-xs text-muted/70">{t("helpTextHint")}</p>
        <textarea
          value={helpText}
          onChange={(e) => setHelpText(e.target.value)}
          rows={10}
          spellCheck={false}
          className="w-full rounded-lg border border-black/10 bg-surface px-4 py-3 font-mono text-xs text-ink placeholder:text-muted/50 focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
          placeholder="# Help"
        />
      </section>

      <section className="rounded-xl border border-black/5 bg-white p-6 shadow-sm">
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted">
          {t("systemSettings")}
        </h2>
        <p className="mb-4 text-xs text-muted/70">{t("systemSettingsHint")}</p>
        <textarea
          value={systemConfig}
          onChange={(e) => setSystemConfig(e.target.value)}
          rows={8}
          spellCheck={false}
          className="w-full rounded-lg border border-black/10 bg-surface px-4 py-3 font-mono text-xs text-ink placeholder:text-muted/50 focus:border-ink focus:outline-none focus:ring-1 focus:ring-ink"
          placeholder='{"key": "value"}'
        />
      </section>

      <div className="flex justify-end pb-8">
        <button
          onClick={handleSave}
          disabled={saving}
          className="rounded-lg bg-ink px-6 py-2.5 text-sm font-medium text-white transition-colors hover:bg-ink/90 disabled:opacity-50"
        >
          {saving ? t("saving") : t("save")}
        </button>
      </div>
    </div>
  );
}
