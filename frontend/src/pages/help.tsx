import { useEffect, useState } from "react";
import { apiClient } from "@/lib/api-client";
import { t } from "@/lib/i18n";

interface SettingsData {
  help_text: string | null;
}

/**
 * Render basic markdown (headers, bold, lists) as HTML.
 * No external lib needed — covers the i18n help content.
 */
function renderMarkdown(md: string): string {
  return md
    .split("\n")
    .map((line) => {
      if (line.startsWith("### ")) return `<h3>${line.slice(4)}</h3>`;
      if (line.startsWith("## ")) return `<h2 class="mt-6 mb-2 text-lg font-semibold text-ink">${line.slice(3)}</h2>`;
      if (line.startsWith("# ")) return `<h1 class="mb-4 text-2xl font-bold text-ink">${line.slice(2)}</h1>`;
      if (line.startsWith("- ")) return `<li class="ml-4 list-disc text-sm text-muted">${line.slice(2)}</li>`;
      if (line.trim() === "") return "<br/>";
      // bold
      let processed = line.replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-ink">$1</strong>');
      return `<p class="text-sm leading-relaxed text-muted">${processed}</p>`;
    })
    .join("\n");
}

export default function HelpPage() {
  const [content, setContent] = useState("");

  useEffect(() => {
    // Try fetching help_text from backend settings; fall back to i18n default
    apiClient
      .get<SettingsData>("/settings/")
      .then((res) => {
        const helpText = res.data.help_text || t("helpContent");
        setContent(renderMarkdown(helpText));
      })
      .catch(() => {
        setContent(renderMarkdown(t("helpContent")));
      });
  }, []);

  return (
    <div className="mx-auto max-w-3xl space-y-6 pb-8">
      <div>
        <h1 className="text-2xl font-bold text-ink">{t("helpTitle")}</h1>
        <p className="mt-1 text-sm text-muted">{t("helpSubtitle")}</p>
      </div>

      <article className="rounded-xl border border-black/5 bg-white p-8 shadow-sm prose prose-sm max-w-none">
        <div dangerouslySetInnerHTML={{ __html: content }} />
      </article>
    </div>
  );
}