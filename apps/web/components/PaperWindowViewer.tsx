"use client";

import {
  ArrowLeft,
  CircleAlert,
  FileQuestion,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchPaperById, paperFileUrl } from "@/lib/api";
import { formatAuthors } from "@/lib/format";
import type { Paper } from "@/lib/types";

function boundedInteger(
  value: string | null,
  fallback: number,
  minimum: number,
  maximum: number,
): number {
  if (value === null || value.trim() === "") return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(minimum, Math.min(maximum, Math.trunc(parsed)));
}

function pdfViewerUrl(pdfUrl: string, page: number, zoom: number): string {
  const url = new URL(pdfUrl);
  url.hash = `page=${page}&zoom=${zoom}`;
  return url.toString();
}

export function PaperWindowViewer({ paperId }: { paperId: string }) {
  const searchParams = useSearchParams();
  const [paper, setPaper] = useState<Paper | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadPaper = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setPaper(await fetchPaperById(paperId));
    } catch (reason) {
      setPaper(null);
      setError(
        reason instanceof Error ? reason.message : "无法读取论文信息。",
      );
    } finally {
      setLoading(false);
    }
  }, [paperId]);

  useEffect(() => {
    void loadPaper();
  }, [loadPaper]);

  const pdfUrl = paper ? paperFileUrl(paper) : null;
  const pageCount = paper ? Math.max(paper.pageCount, 1) : 1;
  const page = boundedInteger(searchParams.get("page"), 1, 1, pageCount);
  const zoom = boundedInteger(searchParams.get("zoom"), 100, 55, 150);
  const framedUrl = useMemo(
    () => (pdfUrl ? pdfViewerUrl(pdfUrl, page, zoom) : null),
    [page, pdfUrl, zoom],
  );

  if (loading) {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-[#e7e9e5] px-6 text-center">
        <div>
          <LoaderCircle className="mx-auto h-7 w-7 animate-spin text-accent" />
          <p className="mt-3 text-sm font-medium text-ink">正在准备论文阅读器</p>
          <p className="mt-1 text-xs text-muted">正在读取论文信息和 PDF 地址</p>
        </div>
      </main>
    );
  }

  if (!paper || error) {
    return (
      <main className="flex min-h-dvh items-center justify-center bg-[#e7e9e5] px-6 text-center">
        <div className="w-full max-w-md border border-line bg-white p-6 shadow-panel">
          <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-md bg-danger-soft text-danger">
            <CircleAlert className="h-5 w-5" />
          </span>
          <h1 className="mt-4 text-base font-semibold text-ink">
            论文阅读器无法打开
          </h1>
          <p className="mt-2 break-words text-xs leading-5 text-muted">
            {error || "论文不存在或已被删除。"}
          </p>
          <div className="mt-5 flex flex-wrap justify-center gap-2">
            <button
              type="button"
              onClick={() => void loadPaper()}
              className="btn-secondary"
            >
              <RefreshCw className="h-4 w-4" />
              重试
            </button>
            <Link href="/papers" className="btn-primary">
              返回论文库
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="flex h-dvh min-h-[560px] flex-col overflow-hidden bg-[#cfd4d0]">
      <header className="shrink-0 border-b border-[#cfd4d0] bg-[#f8f9f7] px-3 py-2 sm:px-4">
        <div className="mx-auto flex max-w-[1800px] items-center gap-3">
          <Link
            href={`/papers/${encodeURIComponent(paper.id)}`}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded border border-line bg-white text-muted transition-colors hover:border-[#aab3af] hover:text-ink"
            aria-label="返回论文详情"
            title="返回论文详情"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div className="min-w-0 flex-1">
            <h1
              className="truncate text-sm font-semibold leading-5 text-ink"
              title={paper.title}
            >
              {paper.title}
            </h1>
            <p className="mt-0.5 truncate text-[10px] text-muted">
              {formatAuthors(paper.authors)}
              {paper.venue || paper.year
                ? ` · ${[paper.venue, paper.year || null].filter(Boolean).join(" ")}`
                : ""}
            </p>
          </div>
          <div className="hidden shrink-0 items-center gap-2 text-[10px] text-muted sm:flex">
            <span>第 {page} / {pageCount} 页</span>
            <span>{zoom}%</span>
          </div>
          {pdfUrl ? (
            <a
              href={pdfUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded border border-line bg-white px-3 text-xs font-medium text-ink transition-colors hover:border-[#aab3af]"
            >
              原始 PDF
            </a>
          ) : null}
        </div>
      </header>

      <div className="min-h-0 flex-1 bg-[#cfd4d0]">
        {framedUrl ? (
          <iframe
            src={framedUrl}
            title={`${paper.title} PDF`}
            className="h-full w-full bg-white"
          />
        ) : (
          <div className="flex h-full items-center justify-center px-6 text-center">
            <div className="max-w-sm">
              <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-md bg-white text-muted shadow-panel">
                <FileQuestion className="h-5 w-5" />
              </span>
              <h2 className="mt-4 text-sm font-semibold text-ink">
                PDF 文件不可用
              </h2>
              <p className="mt-2 text-xs leading-5 text-muted">
                当前论文记录没有可访问的本地 PDF，请返回详情页检查文件状态。
              </p>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
