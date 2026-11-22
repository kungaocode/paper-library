import { ExternalLink } from "lucide-react";
import Link from "next/link";

import { cn } from "@/lib/cn";

export function paperWindowPath(
  paperId: string,
  options: { page?: number; zoom?: number } = {},
): string {
  const path = `/papers/${encodeURIComponent(paperId)}/view`;
  const params = new URLSearchParams();

  if (options.page && options.page > 1) {
    params.set("page", String(Math.trunc(options.page)));
  }
  if (options.zoom && options.zoom !== 100) {
    params.set("zoom", String(Math.trunc(options.zoom)));
  }

  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

export function PaperWindowLink({
  paperId,
  page,
  zoom,
  label = "在新窗口打开",
  compact = false,
  className,
}: {
  paperId: string;
  page?: number;
  zoom?: number;
  label?: string;
  compact?: boolean;
  className?: string;
}) {
  return (
    <Link
      href={paperWindowPath(paperId, { page, zoom })}
      target="_blank"
      rel="noopener noreferrer"
      prefetch={false}
      aria-label={compact ? label : undefined}
      title={compact ? label : undefined}
      className={cn(
        compact
          ? "flex h-8 w-8 shrink-0 items-center justify-center rounded text-muted transition-colors hover:bg-[#e9ece8] hover:text-ink"
          : "inline-flex min-h-8 items-center gap-1.5 rounded font-medium text-ink transition-colors hover:text-accent",
        className,
      )}
    >
      {!compact ? <span>{label}</span> : null}
      <ExternalLink className={compact ? "h-4 w-4" : "h-3 w-3"} />
    </Link>
  );
}
