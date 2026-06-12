import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { t, getLocale, setLocale, type Locale } from "@/lib/i18n";
import { toast } from "sonner";

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

export default function SettingsPage() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [language, setLanguage] = useState<Locale>(getLocale());
  const [siteName, setSiteName] = useState("");
  const [systemConfig, setSystemConfig] = useState("{}");
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [, setLogoPreview] = useState<string | null>(null);

  useEffect(() => {
    apiClient
      .get<SettingsData>("/settings/")
      .then((res) => {
        const data = res.data;
        setSettings(data);
        setLanguage((data.language as Locale) || "ru");
        setSiteName(data.site_name ?? "");
        setSystemConfig(data.system_config ? JSON.stringify(data.system_config, null, 2) : "{}");
        if (data.logo_path) {
          setLogoPreview(`${API_URL.replace("/api/v1", "")}/${data.logo_path}`);
        }
      })
      .catch(() => {});
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const parsedConfig = JSON.parse(systemConfig);
      await apiClient.put("/settings/", {
        language,
        site_name: siteName,
        system_config: parsedConfig,
      });
      setLocale(language);
      toast.success(t("saved"));
      // Re-fetch
      const res = await apiClient.get<SettingsData>("/settings/");
      setSettings(res.data);
      if (res.data.logo_path) {
        setLogoPreview(`${API_URL.replace("/api/v1", "")}/${res.data.logo_path}`);
      }
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
      // Re-fetch settings to get updated logo_path
      const res = await apiClient.get<SettingsData>("/settings/");
      setSettings(res.data);
      if (res.data.logo_path) {
        const url = `${API_URL.replace("/api/v1", "")}/${res.data.logo_path}`;
        setLogoPreview(url);
      }
    } catch {
      toast.error(t("logoUploadError"));
    } finally {
      setUploadingLogo(false);
    }
  };

  const baseUrl = API_URL.replace("/api/v1", "");

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-ink">{t("settingsTitle")}</h1>
        <p className="mt-1 text-sm text-muted">{t("settingsSubtitle")}</p>
      </div>

      {/* Language */}
      <section className="rounded-xl border border-black/5 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">
          {t("language")}
        </h2>
        <div className="flex gap-3">
          <button
            onClick={() => setLanguage("ru")}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              language === "ru"
                ? "bg-ink text-white"
                : "bg-stone-100 text-muted hover:bg-stone-200"
            }`}
          >
            🇷🇺 {t("languageRu")}
          </button>
          <button
            onClick={() => setLanguage("en")}
            className={`rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
              language === "en"
                ? "bg-ink text-white"
                : "bg-stone-100 text-muted hover:bg-stone-200"
            }`}
          >
            🇬🇧 {t("languageEn")}
          </button>
        </div>
      </section>

      {/* Site name */}
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

      {/* Logo */}
      <section className="rounded-xl border border-black/5 bg-white p-6 shadow-sm">
        <h2 className="mb-4 text-sm font-semibold uppercase tracking-wide text-muted">
          {t("uploadLogo")}
        </h2>
        {settings?.logo_path ? (
          <div className="mb-4">
            <p className="mb-2 text-xs text-muted">{t("logoCurrent")}</p>
            <img
              src={`${baseUrl}/${settings.logo_path}`}
              alt="Logo"
              className="h-16 w-auto rounded-lg border border-black/10 bg-stone-50 object-contain"
            />
          </div>
        ) : (
          <p className="mb-4 text-sm text-muted">{t("noLogo")}</p>
        )}
        <label
          className={`inline-flex cursor-pointer items-center gap-2 rounded-lg border border-dashed border-black/20 px-4 py-3 text-sm text-muted transition-colors hover:border-ink hover:text-ink ${
            uploadingLogo ? "pointer-events-none opacity-50" : ""
          }`}
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="17 8 12 3 7 8" />
            <line x1="12" y1="3" x2="12" y2="15" />
          </svg>
          {uploadingLogo ? "…" : t("uploadLogo")}
          <input
            type="file"
            accept="image/*"
            onChange={handleLogoUpload}
            disabled={uploadingLogo}
            className="hidden"
          />
        </label>
      </section>

      {/* System config */}
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

      {/* Save button */}
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