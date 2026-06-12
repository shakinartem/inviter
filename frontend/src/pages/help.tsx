import { useEffect, useState } from "react";

import { apiClient } from "@/lib/api-client";
import { t } from "@/lib/i18n";

interface SettingsData {
  help_text: string | null;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderMarkdown(md: string): string {
  return md
    .split("\n")
    .map((line) => {
      const safeLine = escapeHtml(line);

      if (safeLine.startsWith("### ")) {
        return `<h3 class="mt-5 mb-2 text-base font-semibold text-ink">${safeLine.slice(4)}</h3>`;
      }
      if (safeLine.startsWith("## ")) {
        return `<h2 class="mt-6 mb-2 text-lg font-semibold text-ink">${safeLine.slice(3)}</h2>`;
      }
      if (safeLine.startsWith("# ")) {
        return `<h1 class="mb-4 text-2xl font-bold text-ink">${safeLine.slice(2)}</h1>`;
      }
      if (safeLine.startsWith("- ")) {
        return `<li class="ml-4 list-disc text-sm text-muted">${safeLine.slice(2)}</li>`;
      }
      if (safeLine.trim() === "") {
        return "<br/>";
      }

      const processed = safeLine.replace(
        /\*\*(.+?)\*\*/g,
        '<strong class="font-semibold text-ink">$1</strong>',
      );
      return `<p class="text-sm leading-relaxed text-muted">${processed}</p>`;
    })
    .join("\n");
}

export default function HelpPage() {
  const [content, setContent] = useState("");

  useEffect(() => {
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

      <article className="prose prose-sm max-w-none rounded-xl border border-black/5 bg-white p-8 shadow-sm">
        <div dangerouslySetInnerHTML={{ __html: content }} />
      </article>
    </div>
  );
}
