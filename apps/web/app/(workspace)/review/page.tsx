"use client";

import {
  Check,
  ChevronRight,
  CircleAlert,
  FileQuestion,
  Filter,
  LoaderCircle,
  PencilLine,
  RefreshCw,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { fetchCategories, fetchPapers } from "@/lib/api";
import { formatNumber } from "@/lib/format";
import type { Category, Paper } from "@/lib/types";

export default function ReviewPage() {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadReviewQueue = useCallback(async () => {
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
          : "无法读取复核队列，请确认 API 服务已启动。",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadReviewQueue();
  }, [loadReviewQueue]);

  const categoryNames = useMemo(
    () =>
      Object.fromEntries(
        categories.map((category) => [category.id, category.nameZh]),
      ) as Record<string, string>,
    [categories],
  );

  const reviewPapers = useMemo(
    () => papers.filter((paper) => paper.status === "needs_review"),
    [papers],
  );
  const readyCount = papers.filter((paper) => paper.status === "ready").length;
  const failedCount = papers.filter((paper) => paper.status === "failed").length;

  const metrics = [
    { label: "待复核", value: reviewPapers.length, icon: CircleAlert },
    { label: "可阅读", value: readyCount, icon: Check },
    { label: "处理失败", value: failedCount, icon: FileQuestion },
  ];

  return (
    <div>
      <PageHeader
        eyebrow="Human review"
        title="复核队列"
        description="集中展示模型中低置信度分类和可阅读状态，人工写回接口尚未接入。"
        actions={
          <button
            type="button"
            className="btn-secondary"
            onClick={() => void loadReviewQueue()}
            disabled={loading}
          >
            <RefreshCw className="h-4 w-4" />
            刷新队列
          </button>
        }
      />

      <div className="mt-5 grid gap-3 sm:grid-cols-3">
        {metrics.map((item) => {
          const Icon = item.icon;
          return (
            <div key={item.label} className="panel flex items-center gap-4 px-5 py-4">
              <span className="flex h-9 w-9 items-center justify-center rounded-md bg-[#f0f2ef] text-muted">
                <Icon className="h-4 w-4" />
              </span>
              <div>
                <strong className="block text-lg font-semibold text-ink">
                  {formatNumber(item.value)}
                </strong>
                <span className="mt-0.5 block text-[10px] text-muted">
                  {item.label}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <section className="panel mt-5">
        <div className="flex flex-col gap-3 border-b border-line px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-ink">需要确认的条目</h2>
            <p className="mt-1 text-[11px] text-muted">
              只展示后端标记为 needs_review 的论文
            </p>
          </div>
          <button
            type="button"
            className="btn-secondary h-8 px-2.5 text-xs"
            disabled
            title="筛选接口尚未接入"
          >
            <Filter className="h-3.5 w-3.5" />
            筛选
          </button>
        </div>

        {loading ? (
          <div className="flex flex-col items-center justify-center px-5 py-16 text-center">
            <LoaderCircle className="h-6 w-6 animate-spin text-muted" />
            <p className="mt-4 text-sm text-muted">正在刷新复核队列…</p>
          </div>
        ) : error ? (
          <p className="m-5 border border-danger/25 bg-danger-soft px-3 py-2 text-xs leading-5 text-danger">
            {error}
          </p>
        ) : reviewPapers.length ? (
          <div className="divide-y divide-line">
            {reviewPapers.map((paper) => {
              const categoryName =
                categoryNames[paper.categoryId] ?? "未归类";
              return (
                <article
                  key={paper.id}
                  className="grid gap-5 px-5 py-5 transition-colors lg:grid-cols-[minmax(0,1fr)_230px_190px] lg:items-center"
                >
                  <div className="min-w-0">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <StatusBadge status={paper.status} />
                      <span className="inline-flex items-center gap-1.5 text-[10px] font-medium text-signal">
                        <Sparkles className="h-3 w-3" />
                        模型置信度 {Math.round(paper.confidence * 100)}%
                      </span>
                    </div>
                    <h3 className="line-clamp-2 text-sm font-semibold leading-5 text-ink">
                      {paper.title}
                    </h3>
                    <p className="mt-2 line-clamp-2 text-[11px] leading-5 text-muted">
                      {paper.aiRationale ||
                        paper.abstract ||
                        "后端未提供分类依据或摘要。"}
                    </p>
                  </div>

                  <div className="border-l-2 border-signal/45 bg-[#fffaf2] px-3 py-3">
                    <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-signal">
                      当前分类
                    </p>
                    <p className="mt-1.5 text-[11px] leading-5 text-[#62543c]">
                      {categoryName}
                    </p>
                  </div>

                  <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                    <button
                      type="button"
                      className="btn-secondary h-8 px-2.5 text-xs"
                      disabled
                      title="分类修改接口尚未接入"
                    >
                      <PencilLine className="h-3.5 w-3.5" />
                      修改
                    </button>
                    <button
                      type="button"
                      className="btn h-8 px-2.5 text-xs"
                      disabled
                      title="人工确认接口尚未接入"
                    >
                      <Check className="h-3.5 w-3.5" />
                      确认
                    </button>
                    <Link
                      href={`/papers/${paper.id}`}
                      className="flex h-8 w-8 items-center justify-center rounded text-muted transition-colors hover:bg-[#f0f2ef] hover:text-ink"
                      aria-label={`打开论文：${paper.title}`}
                    >
                      <ChevronRight className="h-4 w-4" />
                    </Link>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center px-5 py-16 text-center">
            <Check className="h-6 w-6 text-accent" />
            <p className="mt-4 text-sm font-medium text-ink">当前没有待复核论文</p>
            <p className="mt-1 text-xs text-muted">
              后端索引中的论文都被标记为可阅读或处理中。
            </p>
          </div>
        )}
      </section>

      <section className="panel mt-5 flex flex-col gap-4 border-accent/25 bg-[#f7fbfa] px-5 py-5 sm:flex-row sm:items-center">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-accent-soft text-accent">
          <ShieldCheck className="h-5 w-5" />
        </span>
        <div>
          <h2 className="text-sm font-semibold text-ink">
            人工确认写回尚未接入
          </h2>
          <p className="mt-1 text-xs leading-5 text-muted">
            当前的“修改”“确认”按钮已停用，避免在没有后端持久化接口时产生假成功。
            分类与解读结果仍可通过论文详情页查看。
          </p>
        </div>
      </section>
    </div>
  );
}
