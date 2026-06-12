import { cn } from "@/lib/utils";

type StatusType = "active" | "idle" | "limited" | "cooldown" | "banned" | "inactive" | "error"
  | "draft" | "paused" | "completed" | "failed" | "pending" | "processing" | "success" | "floodwait"
  | "working" | true | false | null;

const statusConfig: Record<string, { label: string; className: string }> = {
  active: { label: "Active", className: "bg-green-100 text-green-700 border-green-200" },
  idle: { label: "Idle", className: "bg-stone-100 text-stone-600 border-stone-200" },
  limited: { label: "Limited", className: "bg-yellow-100 text-yellow-700 border-yellow-200" },
  cooldown: { label: "Cooldown", className: "bg-orange-100 text-orange-700 border-orange-200" },
  banned: { label: "Banned", className: "bg-red-100 text-red-700 border-red-200" },
  inactive: { label: "Inactive", className: "bg-gray-100 text-gray-500 border-gray-200" },
  error: { label: "Error", className: "bg-red-100 text-red-700 border-red-200" },
  draft: { label: "Draft", className: "bg-stone-100 text-stone-600 border-stone-200" },
  paused: { label: "Paused", className: "bg-yellow-100 text-yellow-700 border-yellow-200" },
  completed: { label: "Completed", className: "bg-green-100 text-green-700 border-green-200" },
  failed: { label: "Failed", className: "bg-red-100 text-red-700 border-red-200" },
  pending: { label: "Pending", className: "bg-stone-100 text-stone-600 border-stone-200" },
  processing: { label: "Processing", className: "bg-blue-100 text-blue-700 border-blue-200" },
  success: { label: "Success", className: "bg-green-100 text-green-700 border-green-200" },
  floodwait: { label: "FloodWait", className: "bg-orange-100 text-orange-700 border-orange-200" },
  working: { label: "Working", className: "bg-green-100 text-green-700 border-green-200" },
  "true": { label: "Yes", className: "bg-green-100 text-green-700 border-green-200" },
  "false": { label: "No", className: "bg-red-100 text-red-700 border-red-200" },
};

export function StatusBadge({ status }: { status: StatusType }) {
  const key = status === true ? "true" : status === false ? "false" : String(status ?? "unknown");
  const config = statusConfig[key] ?? { label: key, className: "bg-stone-100 text-stone-600 border-stone-200" };

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
        config.className,
      )}
    >
      {config.label}
    </span>
  );
}