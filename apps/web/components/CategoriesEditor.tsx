"use client";

import {
  CircleAlert,
  FolderTree,
  LoaderCircle,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchCategories, fetchPapers } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";
import type { Category, Paper } from "@/lib/types";

const groups = [
  { id: "all", label: "全部主题" },
  { id: "security", label: "安全与对齐" },
  { id: "reasoning", label: "推理与规划" },
  { id: "systems", label: "系统与检索" },
] as const;

type GroupId = (typeof groups)[number]["id"];

export function CategoriesEditor() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [group, setGroup] = useState<GroupId>("all");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState("");

  const loadCategories = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextCategories, nextPapers] = await Promise.all([
        fetchCategories(),
        fetchPapers(),
      ]);
      setCategories(nextCategories);
      setPapers(nextPapers);
      setSelectedId((current) => current || nextCategories[0]?.id || "");
    } catch (reason) {
      setCategories([]);
      setPapers([]);
      setError(
        reason instanceof Error
          ? reason.message
          : "无法读取分类数据，请确认 API 服务已启动。",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCategories();
  }, [loadCategories]);

  const categoryCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const paper of papers) {
      counts.set(paper.categoryId, (counts.get(paper.categoryId) ?? 0) + 1);
    }
    return counts;
  }, [papers]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return categories.filter((category) => {
      const inGroup = group === "all" || category.group === group;
      const matches =
        !normalized ||
        category.nameZh.toLowerCase().includes(normalized) ||
        category.nameEn.toLowerCase().includes(normalized) ||
        category.description.toLowerCase().includes(normalized);
      return inGroup && matches;
    });
  }, [categories, group, query]);

  const selected =
    categories.find((category) => category.id === selectedId) ?? categories[0];
  const selectedCount = selected ? categoryCounts.get(selected.id) ?? 0 : 0;

  return (
    <section className="panel mt-5 overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-line p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {groups.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setGroup(item.id)}
              className={cn(
                "h-8 rounded-md px-3 text-xs text-muted transition-colors hover:text-ink",
                group === item.id && "bg-ink text-white hover:text-white",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted" />
            <input
              className="field h-9 w-full pl-8 text-xs sm:w-64"
              placeholder="搜索分类"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
          <button
            type="button"
            className="btn-secondary h-9 px-3 text-xs"
            onClick={() => void loadCategories()}
            disabled={loading}
          >
            <RefreshCw className="h-3.5 w-3.5" />
            刷新
          </button>
          <button
            type="button"
            className="btn-primary h-9 px-3 text-xs"
            disabled
            title="新建分类接口尚未接入"
          >
            <Plus className="h-3.5 w-3.5" />
            新建分类
          </button>
        </div>
      </div>

      {error ? (
        <p className="m-4 border border-danger/25 bg-danger-soft px-3 py-2 text-xs leading-5 text-danger">
          {error}
        </p>
      ) : null}

      <div className="grid min-h-[640px] lg:grid-cols-[minmax(0,1fr)_360px]">
        <div className="min-w-0 border-b border-line lg:border-b-0 lg:border-r">
          <div className="grid grid-cols-[42px_minmax(0,1fr)_90px_120px] border-b border-line bg-[#f7f8f6] px-4 py-3 text-[10px] uppercase tracking-[0.09em] text-muted">
            <span />
            <span className="font-medium">分类</span>
            <span className="font-medium">论文数</span>
            <span className="font-medium">目录</span>
          </div>

          {loading ? (
            <div className="flex flex-col items-center justify-center px-5 py-16 text-center">
              <LoaderCircle className="h-6 w-6 animate-spin text-muted" />
              <p className="mt-4 text-sm text-muted">正在读取分类…</p>
            </div>
          ) : (
            <div className="divide-y divide-line">
              {filtered.map((category) => (
                <button
                  type="button"
                  key={category.id}
                  onClick={() => setSelectedId(category.id)}
                  className={cn(
                    "grid w-full grid-cols-[42px_minmax(0,1fr)_90px_120px] items-center px-4 py-4 text-left transition-colors hover:bg-[#f8faf8]",
                    selectedId === category.id && "bg-accent-soft/55",
                  )}
                >
                  <span
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-md",
                      selectedId === category.id
                        ? "bg-accent text-white"
                        : "bg-[#f0f2ef] text-muted",
                    )}
                  >
                    <FolderTree className="h-4 w-4" />
                  </span>
                  <span className="min-w-0 px-3">
                    <span className="block truncate text-xs font-medium text-ink">
                      {category.nameZh}
                    </span>
                    <span className="mt-1 block truncate text-[10px] text-muted">
                      {category.nameEn}
                    </span>
                  </span>
                  <span className="text-xs text-muted">
                    {formatNumber(categoryCounts.get(category.id) ?? 0)}
                  </span>
                  <span className="truncate font-mono text-[10px] text-muted">
                    {category.slug}
                  </span>
                </button>
              ))}
              {!filtered.length ? (
                <p className="px-5 py-10 text-center text-xs text-muted">
                  没有符合当前筛选条件的分类。
                </p>
              ) : null}
            </div>
          )}
        </div>

        <aside className="bg-[#fafbf9] p-5">
          {selected ? (
            <>
              <p className="page-kicker">Category detail</p>
              <h2 className="mt-2 text-base font-semibold text-ink">
                {selected.nameZh}
              </h2>
              <p className="mt-1 text-xs text-muted">{selected.nameEn}</p>
              <p className="mt-3 text-[10px] text-muted">
                当前 {formatNumber(selectedCount)} 篇论文 · 目录{" "}
                <code className="font-mono">{selected.slug}</code>
              </p>

              <div className="mt-6 space-y-5">
                <label className="block">
                  <span className="mb-2 block text-[11px] font-medium text-muted">
                    中文名称
                  </span>
                  <input
                    className="field w-full disabled:cursor-not-allowed disabled:bg-[#f2f3f1]"
                    value={selected.nameZh}
                    readOnly
                    disabled
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-[11px] font-medium text-muted">
                    英文名称
                  </span>
                  <input
                    className="field w-full disabled:cursor-not-allowed disabled:bg-[#f2f3f1]"
                    value={selected.nameEn}
                    readOnly
                    disabled
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-[11px] font-medium text-muted">
                    分类边界
                  </span>
                  <textarea
                    className="min-h-28 w-full resize-none rounded-md border border-line bg-white px-3 py-2 text-xs leading-5 text-ink disabled:cursor-not-allowed disabled:bg-[#f2f3f1] disabled:text-muted"
                    value={selected.description}
                    readOnly
                    disabled
                  />
                </label>
              </div>

              <div className="mt-5 flex items-start gap-2 border border-signal/25 bg-signal-soft px-3 py-2.5 text-[10px] leading-4 text-signal">
                <CircleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                分类的增删改由后端分类定义维护，前端编辑接口尚未接入。
              </div>

              <div className="mt-6 flex items-center justify-end border-t border-line pt-5">
                <button
                  type="button"
                  className="btn-primary"
                  disabled
                  title="保存接口尚未接入"
                >
                  保存修改
                </button>
              </div>
            </>
          ) : (
            <p className="text-xs text-muted">请选择一个分类查看详情。</p>
          )}
        </aside>
      </div>
    </section>
  );
}
