"use client";

import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Expand,
  FileQuestion,
  Highlighter,
  List,
  Minus,
  PanelLeftClose,
  Plus,
  Search,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { PaperWindowLink } from "@/components/PaperWindowLink";
import { paperFileUrl } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Paper } from "@/lib/types";

export function PaperReader({ paper }: { paper: Paper }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState(100);
  const [thumbnailPanelOpen, setThumbnailPanelOpen] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const pdfUrl = paperFileUrl(paper);
  const pageCount = Math.max(paper.pageCount, 1);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setFullscreen(document.fullscreenElement === containerRef.current);
    };
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () =>
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  function setCurrentPage(value: number) {
    if (!Number.isFinite(value)) return;
    setPage(Math.max(1, Math.min(pageCount, Math.trunc(value))));
  }

  async function toggleFullscreen() {
    if (!containerRef.current) return;
    if (document.fullscreenElement) {
      await document.exitFullscreen();
      return;
    }
    await containerRef.current.requestFullscreen();
  }

  return (
    <section
      ref={containerRef}
      className="flex min-w-0 flex-1 flex-col bg-[#e7e9e5]"
    >
      <div className="flex h-10 shrink-0 items-center gap-1.5 overflow-x-auto border-b border-[#cfd4d0] bg-[#f8f9f7] px-2">
        <button
          type="button"
          className="flex h-8 w-8 items-center justify-center rounded text-muted hover:bg-[#e9ece8] hover:text-ink disabled:opacity-50"
          onClick={() => setThumbnailPanelOpen((value) => !value)}
          aria-label="切换页码栏"
          disabled={!pdfUrl}
        >
          {thumbnailPanelOpen ? (
            <PanelLeftClose className="h-4 w-4" />
          ) : (
            <List className="h-4 w-4" />
          )}
        </button>

        <span className="mx-1 h-5 w-px bg-line" />

        <button
          type="button"
          className="flex h-8 w-8 items-center justify-center rounded text-muted hover:bg-[#e9ece8] hover:text-ink disabled:opacity-50"
          onClick={() => setCurrentPage(page - 1)}
          aria-label="上一页"
          disabled={!pdfUrl || page <= 1}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <div className="flex h-8 items-center rounded border border-line bg-white text-xs">
          <input
            className="w-10 bg-transparent px-2 text-center text-ink outline-none disabled:text-muted"
            value={page}
            onChange={(event) => setCurrentPage(Number(event.target.value))}
            aria-label="当前页码"
            disabled={!pdfUrl}
          />
          <span className="pr-2 text-muted">/ {pageCount}</span>
        </div>
        <button
          type="button"
          className="flex h-8 w-8 items-center justify-center rounded text-muted hover:bg-[#e9ece8] hover:text-ink disabled:opacity-50"
          onClick={() => setCurrentPage(page + 1)}
          aria-label="下一页"
          disabled={!pdfUrl || page >= pageCount}
        >
          <ChevronRight className="h-4 w-4" />
        </button>

        <span className="mx-1 h-5 w-px bg-line" />

        <button
          type="button"
          className="flex h-8 w-8 items-center justify-center rounded text-muted hover:bg-[#e9ece8] hover:text-ink disabled:opacity-50"
          onClick={() => setZoom((value) => Math.max(55, value - 5))}
          aria-label="缩小"
          disabled={!pdfUrl}
        >
          <Minus className="h-4 w-4" />
        </button>
        <button
          type="button"
          className="flex h-8 min-w-14 items-center justify-center gap-1 rounded text-xs text-muted hover:bg-[#e9ece8] hover:text-ink disabled:opacity-50"
          onClick={() => setZoom(100)}
          disabled={!pdfUrl}
        >
          {zoom}%
          <ChevronDown className="h-3 w-3" />
        </button>
        <button
          type="button"
          className="flex h-8 w-8 items-center justify-center rounded text-muted hover:bg-[#e9ece8] hover:text-ink disabled:opacity-50"
          onClick={() => setZoom((value) => Math.min(150, value + 5))}
          aria-label="放大"
          disabled={!pdfUrl}
        >
          <Plus className="h-4 w-4" />
        </button>

        <div className="relative ml-auto hidden w-56 md:block">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
          <input
            className="h-8 w-full rounded border border-line bg-white pl-8 pr-3 text-xs placeholder:text-muted/65"
            placeholder="搜索尚未接入"
            aria-label="在论文中检索"
            disabled
            title="浏览器内置 PDF 搜索尚未接入页面控制"
          />
        </div>
        <button
          type="button"
          className="flex h-8 w-8 items-center justify-center rounded text-muted hover:bg-[#e9ece8] hover:text-ink disabled:opacity-50"
          aria-label="高亮"
          title="文本高亮接口尚未接入"
          disabled
        >
          <Highlighter className="h-4 w-4" />
        </button>
        {pdfUrl ? (
          <PaperWindowLink
            paperId={paper.id}
            page={page}
            zoom={zoom}
            compact
            label="在新窗口打开 PDF"
          />
        ) : null}
        <button
          type="button"
          className="hidden h-8 w-8 items-center justify-center rounded text-muted hover:bg-[#e9ece8] hover:text-ink disabled:opacity-50 sm:flex"
          aria-label={fullscreen ? "退出全屏" : "全屏"}
          onClick={() => void toggleFullscreen()}
          disabled={!pdfUrl}
        >
          <Expand className="h-4 w-4" />
        </button>
      </div>

      {pdfUrl ? (
        <div className="flex min-h-0 flex-1">
          {thumbnailPanelOpen ? (
            <aside className="hidden w-[68px] shrink-0 overflow-y-auto border-r border-[#cfd4d0] bg-[#f0f2ef] px-2 py-3 md:block">
              <div className="space-y-3">
                {Array.from({ length: pageCount }, (_, index) => index + 1).map(
                  (item) => (
                    <button
                      key={item}
                      type="button"
                      className="block w-full text-left"
                      onClick={() => setCurrentPage(item)}
                    >
                      <span
                        className={cn(
                          "mx-auto flex h-10 w-[44px] items-center justify-center border bg-white text-[11px] shadow-sm",
                          page === item
                            ? "border-accent text-accent ring-2 ring-accent/15"
                            : "border-[#d8dcd8] text-muted",
                        )}
                      >
                        {item}
                      </span>
                      <span
                        className={cn(
                          "mt-1 block text-center text-[9px]",
                          page === item
                            ? "font-medium text-accent"
                            : "text-muted",
                        )}
                      >
                        第 {item} 页
                      </span>
                    </button>
                  ),
                )}
              </div>
            </aside>
          ) : null}
          <div className="flex min-w-0 flex-1 flex-col">
            <div className="relative min-h-[520px] flex-1 bg-[#cfd4d0] xl:min-h-0">
              <iframe
                key={`${pdfUrl}-${page}-${zoom}`}
                src={`${pdfUrl}#page=${page}&zoom=${zoom}`}
                title={`${paper.title} PDF`}
                className="absolute inset-0 h-full w-full bg-white"
              />
            </div>
            <div className="flex items-center justify-between border-t border-[#cfd4d0] bg-[#f8f9f7] px-3 py-1 text-[10px] text-muted">
              <span>浏览器内置 PDF 阅读器</span>
              <PaperWindowLink
                paperId={paper.id}
                page={page}
                zoom={zoom}
                className="text-accent hover:text-[#0b625c]"
              />
            </div>
          </div>
        </div>
      ) : (
        <div className="flex min-h-[520px] flex-1 flex-col items-center justify-center bg-[#eef0ed] px-6 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-md bg-white text-muted shadow-panel">
            <FileQuestion className="h-5 w-5" />
          </span>
          <h2 className="mt-4 text-sm font-semibold text-ink">PDF 文件不可用</h2>
          <p className="mt-2 max-w-sm text-xs leading-5 text-muted">
            当前论文记录没有可访问的本地 PDF。迁移记录如果文件路径失效，需要修复目录后重新启动 API。
          </p>
        </div>
      )}
    </section>
  );
}
