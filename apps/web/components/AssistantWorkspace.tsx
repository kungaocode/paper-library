"use client";

import {
  BookOpenText,
  Bot,
  CircleAlert,
  Layers3,
  LoaderCircle,
  MessagesSquare,
  RefreshCw,
  Send,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchCategories, fetchPapers } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatNumber } from "@/lib/format";
import type { Category, Paper } from "@/lib/types";

const scopes = [
  { id: "library", label: "整个知识库", icon: Layers3 },
  { id: "category", label: "当前分类", icon: BookOpenText },
] as const;

type ScopeId = (typeof scopes)[number]["id"];

export function AssistantWorkspace() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [scope, setScope] = useState<ScopeId>("library");
  const [question, setQuestion] = useState("");

  const loadLibrary = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextPapers, nextCategories] = await Promise.all([
        fetchPapers(),
        fetchCategories(),
      ]);
      setPapers(nextPapers);
      setCategories(nextCategories);
    } catch (reason) {
      setPapers([]);
      setCategories([]);
      setError(
        reason instanceof Error
          ? reason.message
          : "无法读取知识库，请确认 API 服务已启动。",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadLibrary();
  }, [loadLibrary]);

  const activeCategories = useMemo(
    () =>
      categories
        .map((category) => ({
          category,
          count: papers.filter((paper) => paper.categoryId === category.id)
            .length,
        }))
        .filter((item) => item.count > 0)
        .sort((left, right) => right.count - left.count),
    [categories, papers],
  );

  const readyCount = papers.filter((paper) => paper.status === "ready").length;

  return (
    <div className="mt-5 grid min-h-[560px] gap-5 xl:grid-cols-[320px_minmax(0,1fr)]">
      <aside className="space-y-5">
        <section className="panel p-5">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-md bg-ink text-white">
              <Bot className="h-5 w-5" />
            </span>
            <div>
              <h2 className="text-sm font-semibold text-ink">知识库范围</h2>
              <p className="mt-1 text-[10px] text-muted">来自本地 API 索引</p>
            </div>
          </div>

          <div className="mt-5 grid grid-cols-2 gap-3">
            <div className="border border-line bg-[#f8faf8] px-3 py-3">
              <strong className="block text-lg font-semibold text-ink">
                {formatNumber(papers.length)}
              </strong>
              <span className="mt-1 block text-[10px] text-muted">论文</span>
            </div>
            <div className="border border-line bg-[#f8faf8] px-3 py-3">
              <strong className="block text-lg font-semibold text-ink">
                {formatNumber(categories.length)}
              </strong>
              <span className="mt-1 block text-[10px] text-muted">分类</span>
            </div>
          </div>

          <div className="mt-5 space-y-2">
            {scopes.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setScope(item.id)}
                  className={cn(
                    "flex h-10 w-full items-center gap-2.5 rounded-md border px-3 text-xs transition-colors",
                    scope === item.id
                      ? "border-accent/35 bg-accent-soft text-accent"
                      : "border-line bg-white text-muted hover:text-ink",
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </button>
              );
            })}
          </div>

          <p className="mt-3 text-[10px] leading-5 text-muted">
            范围选择只影响后续检索请求，当前不会发起问答调用。
          </p>
        </section>

        <section className="panel">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <h2 className="text-sm font-semibold text-ink">分类分布</h2>
            <button
              type="button"
              className="rounded p-1 text-muted hover:text-ink"
              onClick={() => void loadLibrary()}
              aria-label="刷新知识库统计"
            >
              <RefreshCw className="h-3.5 w-3.5" />
            </button>
          </div>
          <div className="divide-y divide-line">
            {activeCategories.length ? (
              activeCategories.map(({ category, count }) => (
                <div
                  key={category.id}
                  className="flex items-center justify-between gap-3 px-5 py-3"
                >
                  <span className="min-w-0 truncate text-xs text-ink">
                    {category.nameZh}
                  </span>
                  <span className="shrink-0 text-[10px] text-muted">
                    {count} 篇
                  </span>
                </div>
              ))
            ) : (
              <p className="px-5 py-6 text-center text-[11px] leading-5 text-muted">
                {loading ? "正在读取分类分布…" : "暂无已归档论文。"}
              </p>
            )}
          </div>
        </section>
      </aside>

      <div className="flex min-w-0 flex-col gap-5">
        <section className="panel flex min-h-0 flex-1 flex-col">
          <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
            <div className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-md bg-accent-soft text-accent">
                <MessagesSquare className="h-4 w-4" />
              </span>
              <div>
                <h2 className="text-sm font-semibold text-ink">知识库问答</h2>
                <p className="mt-1 text-[10px] text-muted">
                  引用定位与页码校验依赖后端问答接口
                </p>
              </div>
            </div>
            <span className="inline-flex h-7 items-center gap-1.5 rounded-full border border-signal/30 bg-signal-soft px-2.5 text-[10px] font-medium text-signal">
              <CircleAlert className="h-3 w-3" />
              接口未接入
            </span>
          </div>

          {error ? (
            <p className="m-5 border border-danger/25 bg-danger-soft px-3 py-2 text-xs leading-5 text-danger">
              {error}
            </p>
          ) : null}

          <div className="flex flex-1 flex-col items-center justify-center px-6 py-14 text-center">
            {loading ? (
              <>
                <LoaderCircle className="h-6 w-6 animate-spin text-muted" />
                <p className="mt-4 text-sm text-muted">正在读取知识库…</p>
              </>
            ) : (
              <>
                <span className="flex h-12 w-12 items-center justify-center rounded-md bg-[#f0f2ef] text-muted">
                  <Sparkles className="h-5 w-5" />
                </span>
                <h3 className="mt-5 text-base font-semibold text-ink">
                  问答功能尚未接入
                </h3>
                <p className="mt-2 max-w-md text-xs leading-5 text-muted">
                  知识库索引已经可用（{formatNumber(papers.length)} 篇论文，
                  {formatNumber(readyCount)} 篇可阅读）。输入框会在后端检索与引用接口
                  上线后开放，避免出现没有来源的自动回答。
                </p>
                <Link
                  href="/papers"
                  className="btn-secondary mt-6 h-9 px-3 text-xs"
                >
                  <BookOpenText className="h-3.5 w-3.5" />
                  浏览论文库
                </Link>
              </>
            )}
          </div>

          <form
            className="flex flex-col gap-2 border-t border-line bg-[#fafbf9] px-5 py-4 sm:flex-row"
            onSubmit={(event) => event.preventDefault()}
          >
            <input
              className="field min-w-0 flex-1 disabled:cursor-not-allowed disabled:bg-[#f4f5f3] disabled:text-muted"
              placeholder="后端问答接口接入后可在此提问"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              disabled
              aria-label="知识库问题（暂不可用）"
            />
            <button
              type="submit"
              className="btn-primary sm:w-28"
              disabled
            >
              <Send className="h-4 w-4" />
              提问
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}
