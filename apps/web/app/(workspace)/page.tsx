import {
  ArrowUpRight,
  BookOpenCheck,
  CircleAlert,
  Clock3,
  FileClock,
  Layers3,
  Library,
  Plus,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import Link from "next/link";

import { PageHeader } from "@/components/PageHeader";
import { PaperMiniList } from "@/components/PaperTable";
import { fetchCategories, fetchJobs, fetchPapers } from "@/lib/api";
import { formatDateTime, formatNumber } from "@/lib/format";
import type { Category, Job, Paper } from "@/lib/types";

export const dynamic = "force-dynamic";

function recentPapers(papers: Paper[]) {
  return [...papers]
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))
    .slice(0, 4);
}

const jobTypeLabels: Record<Job["jobType"], string> = {
  import: "完整导入",
  extract: "文本提取",
  classify: "自动分类",
  analyze: "结构化解读",
  translate: "中文翻译",
  embed: "向量索引",
  export: "Markdown 导出",
};

export default async function DashboardPage() {
  const [papersResult, categoriesResult, jobsResult] = await Promise.allSettled([
    fetchPapers(),
    fetchCategories(),
    fetchJobs(8),
  ]);

  const papers: Paper[] =
    papersResult.status === "fulfilled" ? papersResult.value : [];
  const categories: Category[] =
    categoriesResult.status === "fulfilled" ? categoriesResult.value : [];
  const jobs: Job[] = jobsResult.status === "fulfilled" ? jobsResult.value : [];
  const apiError =
    papersResult.status === "rejected" ||
    categoriesResult.status === "rejected" ||
    jobsResult.status === "rejected";

  const readyCount = papers.filter((paper) => paper.status === "ready").length;
  const reviewCount = papers.filter(
    (paper) => paper.status === "needs_review",
  ).length;
  const runningCount = jobs.filter(
    (job) => job.status === "queued" || job.status === "running",
  ).length;

  const categoryDistribution = categories
    .map((category) => {
      const count = papers.filter(
        (paper) => paper.categoryId === category.id,
      ).length;
      return {
        category,
        count,
        percent: papers.length ? (count / papers.length) * 100 : 0,
      };
    })
    .filter((item) => item.count > 0)
    .sort((left, right) => right.count - left.count);

  const metrics = [
    {
      label: "论文总数",
      value: papers.length,
      note: "来自本地 API 索引",
      icon: Library,
      tone: "text-ink",
    },
    {
      label: "可阅读",
      value: readyCount,
      note: `完整索引率 ${papers.length ? Math.round((readyCount / papers.length) * 100) : 0}%`,
      icon: BookOpenCheck,
      tone: "text-accent",
    },
    {
      label: "待复核",
      value: reviewCount,
      note: "分类或解读置信度偏低",
      icon: CircleAlert,
      tone: "text-signal",
    },
    {
      label: "处理中",
      value: runningCount,
      note: runningCount ? "队列正在运行" : "当前没有运行任务",
      icon: FileClock,
      tone: "text-ink",
    },
  ];

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Research workspace"
        title="研究总览"
        description="跟踪真实知识库规模、处理队列和最近更新记录。"
        actions={
          <Link className="btn-primary" href="/inbox">
            <Plus className="h-4 w-4" />
            添加论文
          </Link>
        }
      />

      {apiError ? (
        <section className="panel flex flex-col gap-3 border-danger/25 bg-danger-soft px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="flex items-start gap-2 text-xs leading-5 text-danger">
            <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
            部分数据无法从 API 读取。当前页面只展示已成功获取的记录。
          </p>
          <Link className="btn-secondary h-8 px-3 text-xs" href="/inbox">
            检查 API 状态
          </Link>
        </section>
      ) : null}

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <div key={metric.label} className="panel px-5 py-5">
              <div className="flex items-start justify-between">
                <span className="text-xs font-medium text-muted">
                  {metric.label}
                </span>
                <span className="flex h-8 w-8 items-center justify-center rounded-md bg-[#f1f3f0]">
                  <Icon className={`h-4 w-4 ${metric.tone}`} />
                </span>
              </div>
              <strong className="mt-4 block text-[31px] font-semibold leading-none tracking-[-0.035em] text-ink">
                {formatNumber(metric.value)}
              </strong>
              <div className="mt-4 flex items-center gap-2 text-[11px] text-muted">
                <span className="h-1.5 w-1.5 rounded-full bg-line" />
                {metric.note}
              </div>
            </div>
          );
        })}
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(420px,0.8fr)]">
        <div className="panel min-w-0">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-ink">最近论文</h2>
              <p className="mt-1 text-[11px] text-muted">
                按知识库更新时间排序
              </p>
            </div>
            <Link
              href="/papers"
              className="flex items-center gap-1.5 text-xs font-medium text-accent"
            >
              查看全部
              <ArrowUpRight className="h-3.5 w-3.5" />
            </Link>
          </div>
          {papers.length ? (
            <PaperMiniList papers={recentPapers(papers)} />
          ) : (
            <div className="flex min-h-52 flex-col items-center justify-center px-5 text-center">
              <Library className="h-6 w-6 text-muted/60" />
              <p className="mt-3 text-sm font-medium text-ink">
                暂无已索引进论文
              </p>
              <p className="mt-1 text-xs text-muted">
                导入链接或上传 PDF 后会出现在这里。
              </p>
            </div>
          )}
        </div>

        <div className="panel min-w-0">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-ink">分类分布</h2>
              <p className="mt-1 text-[11px] text-muted">
                {categoryDistribution.length} 个主题 · 共 {papers.length} 篇
              </p>
            </div>
            <Layers3 className="h-4 w-4 text-muted" />
          </div>
          {categoryDistribution.length ? (
            <div className="space-y-4 px-5 py-5">
              {categoryDistribution.slice(0, 7).map((item) => (
                <div key={item.category.id}>
                  <div className="mb-2 flex items-center justify-between gap-4 text-xs">
                    <span className="truncate text-ink">
                      {item.category.nameZh}
                    </span>
                    <span className="font-medium text-muted">{item.count}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-[#edf0ed]">
                    <div
                      className="h-full rounded-full bg-accent"
                      style={{ width: `${Math.max(item.percent, 2)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="flex min-h-52 items-center justify-center px-5 text-center text-xs text-muted">
              暂无可统计的分类记录
            </div>
          )}
          <Link
            href="/categories"
            className="flex h-11 items-center justify-between border-t border-line px-5 text-xs font-medium text-muted hover:text-ink"
          >
            查看分类
            <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </section>

      <section className="panel">
        <div className="flex flex-col gap-3 border-b border-line px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-ink">处理队列</h2>
            <p className="mt-1 text-[11px] text-muted">
              下载、提取、分类、分析和归档任务
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span className="inline-flex h-8 items-center gap-1.5 rounded-md border border-line px-2.5 text-[11px] text-muted">
              <RefreshCw className="h-3 w-3" />
              打开页面读取实时队列
            </span>
            <Link className="btn-secondary h-8 px-2.5 text-xs" href="/inbox">
              打开队列
            </Link>
          </div>
        </div>

        {jobs.length ? (
          <div className="divide-y divide-line">
            {jobs.slice(0, 5).map((job) => (
              <div
                key={job.id}
                className="grid gap-4 px-5 py-4 md:grid-cols-[minmax(0,1fr)_160px_180px_40px] md:items-center"
              >
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-ink">
                    {job.paperTitle}
                  </p>
                  <p className="mt-1 line-clamp-2 text-[11px] leading-4 text-muted">
                    {job.error || job.message}
                  </p>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-muted">
                  <Clock3 className="h-3.5 w-3.5" />
                  {formatDateTime(job.updatedAt)}
                </div>
                <div>
                  <div className="mb-2 flex items-center justify-between text-[10px] text-muted">
                    <span>{jobTypeLabels[job.jobType]}</span>
                    <span>{job.progress}%</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-[#edf0ed]">
                    <div
                      className={`h-full rounded-full ${
                        job.status === "failed" ? "bg-danger" : "bg-accent"
                      }`}
                      style={{ width: `${job.progress}%` }}
                    />
                  </div>
                </div>
                <Link
                  href={job.paperId ? `/papers/${job.paperId}` : "/inbox"}
                  className="flex h-8 w-8 items-center justify-center rounded text-muted hover:bg-[#f2f4f1] hover:text-ink"
                  aria-label={job.paperId ? "打开论文" : "打开处理队列"}
                >
                  <ArrowUpRight className="h-4 w-4" />
                </Link>
              </div>
            ))}
          </div>
        ) : (
          <div className="flex min-h-40 items-center justify-center px-5 text-center text-xs text-muted">
            当前没有导入或处理任务
          </div>
        )}
      </section>

      <section className="panel flex flex-col gap-5 border-accent/25 bg-[#f7fbfa] px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-start gap-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-accent-soft text-accent">
            <ShieldCheck className="h-5 w-5" />
          </span>
          <div>
            <h2 className="text-sm font-semibold text-ink">知识库健康检查</h2>
            <p className="mt-1 max-w-2xl text-xs leading-5 text-muted">
              当前索引 {papers.length} 份论文，其中 {reviewCount}{" "}
              篇需要确认分类或模型解读结果。
            </p>
          </div>
        </div>
        <Link className="btn-secondary" href="/review">
          查看复核队列
          <ArrowUpRight className="h-4 w-4" />
        </Link>
      </section>
    </div>
  );
}
