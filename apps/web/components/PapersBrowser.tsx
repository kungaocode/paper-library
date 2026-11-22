"use client";

import {
  Archive,
  ArrowDownAZ,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  FolderInput,
  LoaderCircle,
  Plus,
  Search,
  SlidersHorizontal,
  Sparkles,
  X,
} from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";

import { PaperTable, PaperViewToggle } from "@/components/PaperTable";
import { fetchCategories, fetchPapers } from "@/lib/api";
import { paperStatusLabel } from "@/lib/format";
import type { Category, Paper, PaperStatus, ReadingStatus } from "@/lib/types";

const pageSize = 8;

export function PapersBrowser() {
  const searchParams = useSearchParams();
  const [paperItems, setPaperItems] = useState<Paper[]>([]);
  const [categoryItems, setCategoryItems] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [category, setCategory] = useState("all");
  const [status, setStatus] = useState<PaperStatus | "all">("all");
  const [reading, setReading] = useState<ReadingStatus | "all">("all");
  const [year, setYear] = useState("all");
  const [sort, setSort] = useState("updated");
  const [view, setView] = useState<"table" | "list">("table");
  const [page, setPage] = useState(1);
  const [filtersOpen, setFiltersOpen] = useState(false);

  const loadPapers = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [papers, categories] = await Promise.all([
        fetchPapers(),
        fetchCategories(),
      ]);
      setPaperItems(papers);
      setCategoryItems(categories);
    } catch (reason) {
      setPaperItems([]);
      setCategoryItems([]);
      setError(
        reason instanceof Error
          ? reason.message
          : "无法读取论文库，请确认 API 服务已启动。",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPapers();
    const refresh = () => {
      void loadPapers();
    };
    window.addEventListener("paper-library-updated", refresh);
    return () => window.removeEventListener("paper-library-updated", refresh);
  }, [loadPapers]);

  useEffect(() => {
    setQuery(searchParams.get("q") ?? "");
  }, [searchParams]);

  const categoryNames = useMemo(
    () =>
      Object.fromEntries(
        categoryItems.map((item) => [item.id, item.nameZh]),
      ) as Record<string, string>,
    [categoryItems],
  );

  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const paper of paperItems) {
      counts.set(paper.categoryId, (counts.get(paper.categoryId) ?? 0) + 1);
    }
    return counts;
  }, [paperItems]);

  const filtered = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    const next = paperItems.filter((paper) => {
      const matchesQuery =
        !normalizedQuery ||
        paper.title.toLowerCase().includes(normalizedQuery) ||
        paper.titleZh?.toLowerCase().includes(normalizedQuery) ||
        paper.abstract.toLowerCase().includes(normalizedQuery) ||
        paper.authors.some((author) =>
          author.toLowerCase().includes(normalizedQuery),
        ) ||
        paper.tags.some((tag) => tag.toLowerCase().includes(normalizedQuery));
      const matchesCategory =
        category === "all" || paper.categoryId === category;
      const matchesStatus = status === "all" || paper.status === status;
      const matchesReading =
        reading === "all" || paper.readingStatus === reading;
      const matchesYear = year === "all" || String(paper.year) === year;

      return (
        matchesQuery &&
        matchesCategory &&
        matchesStatus &&
        matchesReading &&
        matchesYear
      );
    });

    return next.sort((left, right) => {
      if (sort === "year") return right.year - left.year;
      if (sort === "title") return left.title.localeCompare(right.title);
      if (sort === "confidence") return right.confidence - left.confidence;
      return right.updatedAt.localeCompare(left.updatedAt);
    });
  }, [category, paperItems, query, reading, sort, status, year]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, pageCount);
  const visiblePapers = filtered.slice(
    (safePage - 1) * pageSize,
    safePage * pageSize,
  );

  const activeFilterCount = [category, status, reading, year].filter(
    (value) => value !== "all",
  ).length;

  function resetFilters() {
    setCategory("all");
    setStatus("all");
    setReading("all");
    setYear("all");
    setPage(1);
  }

  const years = Array.from(new Set(paperItems.map((paper) => paper.year))).sort(
    (a, b) => b - a,
  );

  return (
    <>
      <section className="panel mt-5">
        <div className="flex flex-col gap-3 border-b border-line p-4 lg:flex-row lg:items-center">
          <div className="relative min-w-0 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
            <input
              className="field w-full pl-9 pr-9"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setPage(1);
              }}
              placeholder="搜索标题、作者、摘要和标签"
              aria-label="搜索论文"
            />
            {query ? (
              <button
                type="button"
                className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-1 text-muted hover:text-ink"
                onClick={() => setQuery("")}
                aria-label="清除搜索"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            ) : null}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => setFiltersOpen((value) => !value)}
            >
              <SlidersHorizontal className="h-4 w-4" />
              筛选
              {activeFilterCount ? (
                <span className="flex h-5 min-w-5 items-center justify-center rounded-full bg-accent px-1 text-[10px] text-white">
                  {activeFilterCount}
                </span>
              ) : null}
            </button>

            <label className="relative">
              <ArrowDownAZ className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted" />
              <select
                className="field appearance-none pl-9 pr-8"
                value={sort}
                onChange={(event) => setSort(event.target.value)}
                aria-label="排序"
              >
                <option value="updated">最近更新</option>
                <option value="year">发表年份</option>
                <option value="title">标题</option>
                <option value="confidence">置信度</option>
              </select>
            </label>

            <PaperViewToggle view={view} onChange={setView} />
            <Link href="/inbox" className="btn-primary">
              <Plus className="h-4 w-4" />
              添加论文
            </Link>
          </div>
        </div>

        {filtersOpen ? (
          <div className="grid gap-4 border-b border-line bg-[#fafbf9] px-4 py-4 sm:grid-cols-2 xl:grid-cols-5">
            <label>
              <span className="mb-2 block text-[11px] font-medium text-muted">
                分类
              </span>
              <select
                className="field w-full"
                value={category}
                onChange={(event) => {
                  setCategory(event.target.value);
                  setPage(1);
                }}
              >
                <option value="all">全部分类</option>
                {categoryItems.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.nameZh}（{categoryCounts.get(item.id) ?? 0}）
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span className="mb-2 block text-[11px] font-medium text-muted">
                处理状态
              </span>
              <select
                className="field w-full"
                value={status}
                onChange={(event) => {
                  setStatus(event.target.value as PaperStatus | "all");
                  setPage(1);
                }}
              >
                <option value="all">全部状态</option>
                {Object.entries(paperStatusLabel).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>

            <label>
              <span className="mb-2 block text-[11px] font-medium text-muted">
                阅读状态
              </span>
              <select
                className="field w-full"
                value={reading}
                onChange={(event) => {
                  setReading(event.target.value as ReadingStatus | "all");
                  setPage(1);
                }}
              >
                <option value="all">全部状态</option>
                <option value="unread">未读</option>
                <option value="reading">阅读中</option>
                <option value="finished">已读</option>
              </select>
            </label>

            <label>
              <span className="mb-2 block text-[11px] font-medium text-muted">
                年份
              </span>
              <select
                className="field w-full"
                value={year}
                onChange={(event) => {
                  setYear(event.target.value);
                  setPage(1);
                }}
              >
                <option value="all">全部年份</option>
                {years.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
            </label>

            <div className="flex items-end">
              <button
                type="button"
                className="btn-secondary w-full"
                onClick={resetFilters}
              >
                清除筛选
              </button>
            </div>
          </div>
        ) : null}

        {error ? (
          <div className="flex flex-col gap-3 border-b border-danger/20 bg-danger-soft px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="flex items-start gap-2 text-xs leading-5 text-danger">
              <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
              {error}
            </p>
            <button
              type="button"
              className="btn-secondary h-8 px-3 text-xs"
              onClick={() => void loadPapers()}
            >
              重试
            </button>
          </div>
        ) : null}

        <div className="flex flex-col gap-3 border-b border-line px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-muted">
            显示 <strong className="font-medium text-ink">{filtered.length}</strong>{" "}
            篇论文，共 {paperItems.length} 篇当前记录
          </p>
          <div className="flex items-center gap-4 text-[11px] text-muted">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-accent" />
              人工整理
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-signal" />
              AI 生成
            </span>
          </div>
        </div>

        {loading ? (
          <div className="flex min-h-64 flex-col items-center justify-center px-5 text-center">
            <LoaderCircle className="h-6 w-6 animate-spin text-accent" />
            <h2 className="mt-4 text-sm font-semibold text-ink">正在加载论文库</h2>
            <p className="mt-2 text-xs text-muted">从本地 API 读取论文索引。</p>
          </div>
        ) : visiblePapers.length ? (
          <PaperTable
            papers={visiblePapers}
            view={view}
            categoryNames={categoryNames}
          />
        ) : (
          <div className="flex min-h-64 flex-col items-center justify-center px-5 text-center">
            <Search className="h-6 w-6 text-muted/60" />
            <h2 className="mt-4 text-sm font-semibold text-ink">
              {paperItems.length ? "没有匹配的论文" : "知识库暂无论文"}
            </h2>
            <p className="mt-2 text-xs text-muted">
              {paperItems.length
                ? "调整关键词或清除筛选条件后重试。"
                : "从链接或 PDF 导入论文后，记录会显示在这里。"}
            </p>
            {paperItems.length ? (
              <button
                type="button"
                className="btn-secondary mt-5"
                onClick={() => {
                  setQuery("");
                  resetFilters();
                }}
              >
                清除条件
              </button>
            ) : (
              <Link className="btn-primary mt-5" href="/inbox">
                <Plus className="h-4 w-4" />
                导入第一篇论文
              </Link>
            )}
          </div>
        )}
      </section>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            className="btn-secondary"
            disabled
            title="批量归档接口尚未接入"
          >
            <Archive className="h-4 w-4" />
            归档
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled
            title="移动分类接口尚未接入"
          >
            <FolderInput className="h-4 w-4" />
            移动分类
          </button>
          <button
            type="button"
            className="btn-secondary"
            disabled
            title="重新分析接口尚未接入"
          >
            <Sparkles className="h-4 w-4" />
            重新分析
          </button>
          <span className="text-[10px] text-muted">批量操作尚未接入后端</span>
        </div>

        <div className="flex items-center gap-1">
          <button
            type="button"
            className="icon-btn"
            disabled={safePage <= 1}
            onClick={() => setPage((value) => Math.max(1, value - 1))}
            aria-label="上一页"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          {Array.from({ length: Math.min(pageCount, 5) }, (_, index) => {
            const item = index + 1;
            return (
              <button
                key={item}
                type="button"
                onClick={() => setPage(item)}
                className={`flex h-9 min-w-9 items-center justify-center rounded-md border px-2 text-xs ${
                  item === safePage
                    ? "border-ink bg-ink text-white"
                    : "border-line bg-white text-muted hover:text-ink"
                }`}
              >
                {item}
              </button>
            );
          })}
          <button
            type="button"
            className="icon-btn"
            disabled={safePage >= pageCount}
            onClick={() => setPage((value) => Math.min(pageCount, value + 1))}
            aria-label="下一页"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      </div>
    </>
  );
}
