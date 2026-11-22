import { CircleAlert, CircleCheck, Clock3, LoaderCircle } from "lucide-react";

import { cn } from "@/lib/cn";
import { paperStatusLabel } from "@/lib/format";
import type { PaperStatus, ReadingStatus } from "@/lib/types";

const statusStyles: Record<PaperStatus, string> = {
  uploaded: "border-line bg-[#f5f6f4] text-muted",
  extracting: "border-[#b7d8d3] bg-accent-soft text-accent",
  text_extracted: "border-[#b7d8d3] bg-accent-soft text-accent",
  classifying: "border-[#ead0a7] bg-signal-soft text-signal",
  analyzing: "border-[#ead0a7] bg-signal-soft text-signal",
  ready: "border-[#b7d8d3] bg-accent-soft text-accent",
  needs_review: "border-[#ead0a7] bg-signal-soft text-signal",
  failed: "border-[#f1bbb5] bg-danger-soft text-danger",
  archived: "border-line bg-[#f5f6f4] text-muted",
};

const statusIcons: Partial<Record<PaperStatus, typeof Clock3>> = {
  extracting: LoaderCircle,
  classifying: LoaderCircle,
  analyzing: LoaderCircle,
  ready: CircleCheck,
  needs_review: CircleAlert,
  failed: CircleAlert,
};

export function StatusBadge({
  status,
  className,
}: {
  status: PaperStatus;
  className?: string;
}) {
  const Icon = statusIcons[status] ?? Clock3;
  const isSpinning =
    status === "extracting" || status === "classifying" || status === "analyzing";

  return (
    <span
      className={cn(
        "inline-flex h-6 items-center gap-1.5 rounded-full border px-2 text-[11px] font-medium",
        statusStyles[status],
        className,
      )}
    >
      <Icon className={cn("h-3 w-3", isSpinning && "animate-spin")} />
      {paperStatusLabel[status]}
    </span>
  );
}

export function ReadingBadge({ status }: { status: ReadingStatus }) {
  const label = {
    unread: "未读",
    reading: "阅读中",
    finished: "已读",
  }[status];

  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted">
      <span
        className={cn(
          "h-2 w-2 rounded-full",
          status === "finished" && "bg-accent",
          status === "reading" && "bg-signal",
          status === "unread" && "bg-[#bfc6c3]",
        )}
      />
      {label}
    </span>
  );
}
