"use client";

import {
  ArrowDownToLine,
  ArrowUpRight,
  BookOpen,
  Clock3,
  ListFilter,
  Table2,
} from "lucide-react";
import Link from "next/link";

import { ReadingBadge, StatusBadge } from "@/components/StatusBadge";
import { cn } from "@/lib/cn";
import { formatAuthors, formatDateTime } from "@/lib/format";
import type { Paper } from "@/lib/types";

function SourceMark({ source }: { source: Paper["source"] }) {
  const meta = {
    manual: { label: "人工", className: "text-accent" },
    model: { label: "AI", className: "text-signal" },
    migration: { label: "迁移", className: "text-muted" },
  }[source];

  return (
    <span className={cn("text-[11px] font-medium", meta.className)}>
      {meta.label}
    </span>
  );
}

export function PaperTable({
  papers,
  view = "table",
  categoryNames = {},
}: {
  papers: Paper[];
  view?: "table" | "list";
  categoryNames?: Record<string, string>;
}) {
  if (view === "list") {
    return (
      <div className="divide-y divide-line">
        {papers.map((paper) => (
          <Link
            key={paper.id}
            href={`/papers/${paper.id}`}
            className="group grid gap-4 px-4 py-5 transition-colors hover:bg-[#f8faf8] sm:grid-cols-[minmax(0,1fr)_170px_120px] sm:px-5"
          >
            <div className="min-w-0">
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <StatusBadge status={paper.status} />
                <SourceMark source={paper.source} />
                {paper.tags.slice(0, 2).map((tag) => (
                  <span
                    key={tag}
                    className="rounded bg-[#f0f2ef] px-1.5 py-0.5 text-[10px] text-muted"
                  >
                    {tag}
                  </span>
                ))}
              </div>
              <h3 className="line-clamp-2 text-sm font-semibold leading-5 text-ink group-hover:text-accent">
                {paper.title}
              </h3>
              <p className="mt-1.5 line-clamp-1 text-xs text-muted">
                {formatAuthors(paper.authors)}
              </p>
            </div>
            <div className="text-xs text-muted">
              <span className="block font-medium text-ink">
                {paper.venue} · {paper.year}
              </span>
              <span className="mt-1 block">
                更新于 {formatDateTime(paper.updatedAt)}
              </span>
            </div>
            <div className="flex items-start justify-between gap-3 sm:justify-end">
              <ReadingBadge status={paper.readingStatus} />
              <ArrowUpRight className="h-4 w-4 text-muted transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5 group-hover:text-accent" />
            </div>
          </Link>
        ))}
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[980px] border-collapse text-left">
        <thead>
          <tr className="border-b border-line bg-[#f7f8f6] text-[11px] uppercase tracking-[0.08em] text-muted">
            <th className="px-4 py-3 font-medium">论文</th>
            <th className="w-[170px] px-3 py-3 font-medium">分类</th>
            <th className="w-[130px] px-3 py-3 font-medium">发表</th>
            <th className="w-[110px] px-3 py-3 font-medium">状态</th>
            <th className="w-[110px] px-3 py-3 font-medium">阅读</th>
            <th className="w-[110px] px-3 py-3 font-medium">来源</th>
          </tr>
        </thead>
        <tbody>
          {papers.map((paper) => (
            <tr
              key={paper.id}
              className="group border-b border-line last:border-0 hover:bg-[#f8faf8]"
            >
              <td className="px-4 py-4 align-top">
                <Link
                  href={`/papers/${paper.id}`}
                  className="block max-w-[620px]"
                >
                  <span className="line-clamp-2 text-[13px] font-semibold leading-5 text-ink group-hover:text-accent">
                    {paper.title}
                  </span>
                  <span className="mt-1.5 block line-clamp-1 text-[11px] text-muted">
                    {formatAuthors(paper.authors)}
                  </span>
                  <span className="mt-2 flex items-center gap-3 text-[10px] text-muted">
                    <span>{paper.pageCount} 页</span>
                    <span>{paper.fileSize}</span>
                    <span>更新于 {formatDateTime(paper.updatedAt)}</span>
                  </span>
                </Link>
              </td>
              <td className="px-3 py-4 align-top">
                <span className="line-clamp-2 text-xs leading-5 text-ink">
                  {categoryNames[paper.categoryId] ?? "未映射分类"}
                </span>
              </td>
              <td className="px-3 py-4 align-top">
                <span className="text-xs text-ink">{paper.venue}</span>
                <span className="mt-1 block text-[11px] text-muted">
                  {paper.year}
                </span>
              </td>
              <td className="px-3 py-4 align-top">
                <StatusBadge status={paper.status} />
              </td>
              <td className="px-3 py-4 align-top">
                <ReadingBadge status={paper.readingStatus} />
              </td>
              <td className="px-3 py-4 align-top">
                <SourceMark source={paper.source} />
                <span className="mt-1 block text-[10px] text-muted">
                  {Math.round(paper.confidence * 100)}%
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function PaperViewToggle({
  view,
  onChange,
}: {
  view: "table" | "list";
  onChange: (view: "table" | "list") => void;
}) {
  return (
    <div className="inline-flex h-10 items-center rounded-md border border-line bg-white p-1">
      <button
        type="button"
        onClick={() => onChange("table")}
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded text-muted",
          view === "table" && "bg-ink text-white",
        )}
        aria-label="表格视图"
      >
        <Table2 className="h-4 w-4" />
      </button>
      <button
        type="button"
        onClick={() => onChange("list")}
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded text-muted",
          view === "list" && "bg-ink text-white",
        )}
        aria-label="列表视图"
      >
        <ListFilter className="h-4 w-4" />
      </button>
    </div>
  );
}

export function PaperMiniList({ papers }: { papers: Paper[] }) {
  return (
    <div className="divide-y divide-line">
      {papers.map((paper) => (
        <Link
          href={`/papers/${paper.id}`}
          key={paper.id}
          className="group flex items-start gap-3 px-5 py-4 transition-colors hover:bg-[#f8faf8]"
        >
          <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded bg-[#eef2ef] text-muted group-hover:bg-accent-soft group-hover:text-accent">
            <BookOpen className="h-4 w-4" />
          </span>
          <span className="min-w-0 flex-1">
            <span className="line-clamp-2 text-xs font-medium leading-5 text-ink group-hover:text-accent">
              {paper.title}
            </span>
            <span className="mt-1 flex items-center gap-2 text-[10px] text-muted">
              <span>
                {paper.venue} {paper.year}
              </span>
              <span className="h-1 w-1 rounded-full bg-line" />
              <Clock3 className="h-3 w-3" />
              {formatDateTime(paper.updatedAt)}
            </span>
          </span>
          <ArrowDownToLine className="mt-1 h-3.5 w-3.5 shrink-0 text-muted/60" />
        </Link>
      ))}
    </div>
  );
}
