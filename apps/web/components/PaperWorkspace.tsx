"use client";

import {
  Bot,
  Check,
  ChevronRight,
  CircleAlert,
  ClipboardCheck,
  Download,
  FileText,
  FolderTree,
  Languages,
  Layers3,
  LoaderCircle,
  MessageSquareText,
  Play,
  Quote,
  RefreshCw,
  Send,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { PaperReader } from "@/components/PaperReader";
import { StatusBadge } from "@/components/StatusBadge";
import {
  fetchJobs,
  fetchPaperTranslation,
  startPaperTranslation,
  translationFileUrl,
} from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/format";
import type { Category, Job, Paper, PaperTranslation } from "@/lib/types";

type PanelTab = "insight" | "translation" | "classification" | "qa" | "tasks";

const tabs: Array<{
  id: PanelTab;
  label: string;
  icon: typeof Sparkles;
}> = [
  { id: "insight", label: "AI 解读", icon: Sparkles },
  { id: "translation", label: "中文翻译", icon: Languages },
  { id: "classification", label: "分类", icon: FolderTree },
  { id: "qa", label: "问答", icon: MessageSquareText },
  { id: "tasks", label: "任务", icon: ClipboardCheck },
];

const jobTypeLabels: Record<Job["jobType"], string> = {
  import: "完整导入",
  extract: "文本提取",
  classify: "自动分类",
  analyze: "结构化解读",
  translate: "中文翻译",
  embed: "向量索引",
  export: "导出",
};

export function PaperWorkspace({
  paper,
  categories,
}: {
  paper: Paper;
  categories: Category[];
}) {
  const [tab, setTab] = useState<PanelTab>("insight");
  const categoryName =
    categories.find((item) => item.id === paper.categoryId)?.nameZh ??
    "未映射分类";

  return (
    <div className="h-full w-full min-w-0 overflow-hidden border border-line bg-white shadow-panel">
      <div className="flex min-h-[640px] w-full min-w-0 flex-col xl:h-full xl:min-h-0 xl:flex-row">
        <PaperReader paper={paper} />

        <aside
          className={cn(
            "flex w-full shrink-0 flex-col border-t border-line bg-white xl:border-l xl:border-t-0",
            tab === "translation"
              ? "xl:w-[48%] 2xl:w-[52%]"
              : "xl:w-[350px] 2xl:w-[370px]",
          )}
        >
          <div className="flex h-12 shrink-0 items-center border-b border-line px-2">
            {tabs.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => setTab(item.id)}
                  className={cn(
                    "relative flex h-12 items-center gap-1.5 px-2 text-xs font-medium text-muted transition-colors hover:text-ink 2xl:gap-2 2xl:px-3",
                    tab === item.id && "text-ink",
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                  {item.label}
                  {tab === item.id ? (
                    <span className="absolute inset-x-2 bottom-0 h-0.5 bg-accent" />
                  ) : null}
                </button>
              );
            })}
          </div>

          <div className="min-h-0 flex-1 overflow-y-auto">
            {tab === "insight" ? <InsightPanel paper={paper} /> : null}
            {tab === "translation" ? <TranslationPanel paper={paper} /> : null}
            {tab === "classification" ? (
              <ClassificationPanel paper={paper} categoryName={categoryName} />
            ) : null}
            {tab === "qa" ? <QaPanel /> : null}
            {tab === "tasks" ? <TasksPanel paper={paper} /> : null}
          </div>
        </aside>
      </div>
    </div>
  );
}

function PanelSection({
  title,
  icon: Icon,
  action,
  children,
}: {
  title: string;
  icon: typeof Sparkles;
  action?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="border-b border-line px-5 py-5 last:border-0">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xs font-semibold text-ink">
          <Icon className="h-4 w-4 text-muted" />
          {title}
        </h2>
        {action}
      </div>
      {children}
    </section>
  );
}

function EmptyValue({ children }: { children: React.ReactNode }) {
  return <p className="text-xs leading-6 text-muted">{children}</p>;
}

function InsightPanel({ paper }: { paper: Paper }) {
  const hasStructuredSummary =
    Boolean(
      paper.summary.problem ||
        paper.summary.method ||
        paper.summary.thesisZh ||
        paper.summary.noveltyZh,
    ) ||
    paper.summary.findings.length > 0 ||
    paper.summary.innovations.length > 0;
  const sourceLabel =
    paper.source === "model"
      ? "Model assisted"
      : paper.source === "migration"
        ? "Migrated notes"
        : "Manual notes";

  return (
    <div>
      <div className="border-b border-line bg-[#fafbf9] px-5 py-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <span className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.1em] text-signal">
              <Sparkles className="h-3 w-3" />
              {sourceLabel}
            </span>
            <p className="mt-1 text-[11px] text-muted">
              置信度 {Math.round(paper.confidence * 100)}%
            </p>
          </div>
          <button
            type="button"
            className="icon-btn h-8 w-8"
            aria-label="重新分析"
            title="重新分析接口尚未接入"
            disabled
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {!hasStructuredSummary ? (
        <PanelSection title="模型解读" icon={Sparkles}>
          <EmptyValue>
            当前论文只有迁移元数据和 PDF，尚未生成结构化模型解读。可在导入队列中查看新任务，或等待重分析接口接入。
          </EmptyValue>
        </PanelSection>
      ) : null}

      {paper.titleZh ? (
        <PanelSection title="中文题名" icon={FileText}>
          <p className="text-xs font-medium leading-6 text-ink">
            {paper.titleZh}
          </p>
        </PanelSection>
      ) : null}

      {paper.summary.thesisZh || paper.summary.thesisEn ? (
        <PanelSection title="核心论点" icon={Sparkles}>
          <div className="space-y-4">
            {paper.summary.thesisZh ? (
              <p className="text-xs leading-6 text-[#414b4d]">
                {paper.summary.thesisZh}
              </p>
            ) : null}
            {paper.summary.thesisEn ? (
              <p className="border-l-2 border-line pl-3 text-[11px] leading-6 text-muted">
                {paper.summary.thesisEn}
              </p>
            ) : null}
          </div>
        </PanelSection>
      ) : null}

      {paper.summary.noveltyZh || paper.summary.noveltyEn ? (
        <PanelSection title="创新点摘要" icon={Quote}>
          <div className="space-y-4">
            {paper.summary.noveltyZh ? (
              <p className="text-xs leading-6 text-[#414b4d]">
                {paper.summary.noveltyZh}
              </p>
            ) : null}
            {paper.summary.noveltyEn ? (
              <p className="border-l-2 border-line pl-3 text-[11px] leading-6 text-muted">
                {paper.summary.noveltyEn}
              </p>
            ) : null}
          </div>
        </PanelSection>
      ) : null}

      {paper.summary.problem ? (
        <PanelSection title="研究问题" icon={CircleAlert}>
          <p className="text-xs leading-6 text-[#414b4d]">
            {paper.summary.problem}
          </p>
        </PanelSection>
      ) : null}

      {paper.summary.method ? (
        <PanelSection title="方法" icon={Layers3}>
          <p className="text-xs leading-6 text-[#414b4d]">
            {paper.summary.method}
          </p>
        </PanelSection>
      ) : null}

      {paper.summary.findings.length ? (
        <PanelSection title="主要发现" icon={Check}>
          <ul className="space-y-3">
            {paper.summary.findings.map((finding, index) => (
              <li
                key={`${finding}-${index}`}
                className="flex items-start gap-3 text-xs leading-5 text-[#414b4d]"
              >
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                {finding}
              </li>
            ))}
          </ul>
        </PanelSection>
      ) : null}

      {paper.summary.innovations.length ? (
        <PanelSection title="创新点与证据" icon={Quote}>
          <div className="space-y-5">
            {paper.summary.innovations.map((innovation, index) => (
              <div key={`${innovation.claim}-${index}`}>
                <div className="flex gap-3">
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-accent-soft text-[10px] font-semibold text-accent">
                    {index + 1}
                  </span>
                  <p className="text-xs font-medium leading-5 text-ink">
                    {innovation.claim}
                  </p>
                </div>
                {innovation.evidenceQuotes.map((quote, quoteIndex) => (
                  <div
                    key={`${quote}-${quoteIndex}`}
                    className="mt-3 border-l-2 border-signal/55 bg-[#fffaf2] px-3 py-2"
                  >
                    <span className="block text-[10px] leading-5 text-[#62543c]">
                      “{quote}”
                    </span>
                    <span className="mt-1 block text-[9px] font-medium uppercase tracking-[0.08em] text-signal">
                      证据页码：
                      {innovation.evidencePages[quoteIndex] ??
                        innovation.evidencePages[0] ??
                        "未标注"}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </PanelSection>
      ) : null}

      {paper.summary.limitations.length ? (
        <PanelSection title="局限性" icon={CircleAlert}>
          <ul className="space-y-3">
            {paper.summary.limitations.map((limitation, index) => (
              <li
                key={`${limitation}-${index}`}
                className="flex items-start gap-3 text-xs leading-5 text-[#414b4d]"
              >
                <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-[#a5aeaa]" />
                {limitation}
              </li>
            ))}
          </ul>
        </PanelSection>
      ) : null}
    </div>
  );
}

const translationStatusLabels: Record<PaperTranslation["status"], string> = {
  not_started: "未翻译",
  queued: "等待翻译",
  running: "翻译中",
  ready: "译文已就绪",
  failed: "翻译失败",
};

function TranslationPanel({ paper }: { paper: Paper }) {
  const [translation, setTranslation] = useState<PaperTranslation>(() => ({
    paperId: paper.id,
    status: paper.translationStatus,
    progress: paper.translationProgress,
    pageCount: paper.translationPageCount || paper.pageCount,
    completedPages: paper.translationCompletedPages,
    error: paper.translationError ?? "",
    model: paper.translationModel ?? "",
    updatedAt: paper.translationUpdatedAt ?? "",
    downloadUrl: paper.translationUrl ?? "",
  }));
  const [loading, setLoading] = useState(true);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState("");

  const loadTranslation = useCallback(async () => {
    try {
      setTranslation(await fetchPaperTranslation(paper.id));
      setError("");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "无法读取翻译状态。",
      );
    } finally {
      setLoading(false);
    }
  }, [paper.id]);

  useEffect(() => {
    void loadTranslation();
  }, [loadTranslation]);

  const isActive =
    translation.status === "queued" || translation.status === "running";

  useEffect(() => {
    if (!isActive) return;
    const timer = window.setTimeout(() => {
      void loadTranslation();
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [isActive, loadTranslation, translation.progress, translation.status]);

  async function beginTranslation() {
    setStarting(true);
    setError("");
    try {
      setTranslation(await startPaperTranslation(paper.id));
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "无法启动中文翻译。",
      );
    } finally {
      setStarting(false);
    }
  }

  const downloadUrl = translationFileUrl(translation);
  const pageCount = translation.pageCount || paper.pageCount;

  return (
    <div className="min-h-full">
      <div className="border-b border-line bg-[#fafbf9] px-5 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Languages className="h-4 w-4 text-accent" />
              <p className="text-xs font-semibold text-ink">
                {translationStatusLabels[translation.status]}
              </p>
            </div>
            <p className="mt-1.5 truncate text-[10px] text-muted">
              {translation.model || paper.translationModel || "模型待配置"}
              {translation.updatedAt
                ? ` · 更新于 ${formatDateTime(translation.updatedAt)}`
                : ""}
            </p>
          </div>

          {translation.status === "ready" && downloadUrl ? (
            <a
              href={downloadUrl}
              download
              className="btn-primary h-8 px-3 text-xs"
            >
              <Download className="h-3.5 w-3.5" />
              下载译文
            </a>
          ) : null}
        </div>

        {pageCount ? (
          <div className="mt-4">
            <div className="mb-1.5 flex items-center justify-between text-[10px] text-muted">
              <span>
                已完成 {translation.completedPages}/{pageCount} 页
              </span>
              <span>{translation.progress}%</span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-[#e7eae7]">
              <div
                className={cn(
                  "h-full rounded-full transition-[width]",
                  translation.status === "failed" ? "bg-danger" : "bg-accent",
                )}
                style={{
                  width: `${Math.max(
                    0,
                    Math.min(100, translation.progress),
                  )}%`,
                }}
              />
            </div>
          </div>
        ) : null}
      </div>

      {error ? (
        <div className="border-b border-danger/20 bg-danger-soft px-5 py-3 text-xs leading-5 text-danger">
          {error}
        </div>
      ) : null}

      {loading && translation.status === "not_started" ? (
        <div className="flex min-h-[520px] items-center justify-center text-xs text-muted">
          <LoaderCircle className="mr-2 h-4 w-4 animate-spin" />
          正在读取翻译状态
        </div>
      ) : translation.status === "not_started" ? (
        <div className="flex min-h-[520px] flex-col items-center justify-center px-8 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-md bg-accent-soft text-accent">
            <Languages className="h-5 w-5" />
          </span>
          <h2 className="mt-4 text-sm font-semibold text-ink">尚无中文译文</h2>
          <p className="mt-2 max-w-sm text-xs leading-5 text-muted">
            将按 PDF 页面生成简体中文译文，并保留论文原有的章节与段落结构。
          </p>
          <button
            type="button"
            onClick={() => void beginTranslation()}
            disabled={starting}
            className="btn-primary mt-5"
          >
            {starting ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            开始翻译
          </button>
        </div>
      ) : isActive ? (
        <div className="flex min-h-[520px] flex-col items-center justify-center px-8 text-center">
          <LoaderCircle className="h-7 w-7 animate-spin text-accent" />
          <h2 className="mt-4 text-sm font-semibold text-ink">
            正在生成中文译文
          </h2>
          <p className="mt-2 text-xs leading-5 text-muted">
            已完成 {translation.completedPages}/{pageCount || "未知"} 页，可继续浏览原始 PDF。
          </p>
        </div>
      ) : translation.status === "failed" ? (
        <div className="flex min-h-[520px] flex-col items-center justify-center px-8 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-md bg-danger-soft text-danger">
            <CircleAlert className="h-5 w-5" />
          </span>
          <h2 className="mt-4 text-sm font-semibold text-ink">翻译未完成</h2>
          <p className="mt-2 max-w-sm break-words text-xs leading-5 text-muted">
            {translation.error || "模型接口没有返回可用的翻译结果。"}
          </p>
          <button
            type="button"
            onClick={() => void beginTranslation()}
            disabled={starting}
            className="btn-secondary mt-5"
          >
            {starting ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            重新翻译
          </button>
        </div>
      ) : translation.text ? (
        <article className="px-6 py-6 lg:px-10 lg:py-8">
          <TranslationText text={translation.text} />
        </article>
      ) : (
        <div className="flex min-h-[520px] items-center justify-center px-8 text-center text-xs leading-5 text-muted">
          译文文件暂时无法读取，请重新翻译。
        </div>
      )}
    </div>
  );
}

function TranslationText({ text }: { text: string }) {
  const blocks = text
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean);

  return (
    <div className="mx-auto max-w-4xl space-y-5">
      {blocks.map((block, index) => {
        const heading = block.match(
          /^(#{1,3})[ \t]+([^\n]+)(?:\n+([\s\S]*))?$/,
        );
        if (heading) {
          const level = heading[1].length;
          const headingClass =
            level === 1
              ? "text-xl font-semibold text-ink"
              : level === 2
                ? "text-base font-semibold text-ink"
                : "text-sm font-semibold text-ink";
          return (
            <section key={`${index}-${heading[2]}`}>
              <h2 className={headingClass}>{heading[2]}</h2>
              {heading[3] ? (
                <p className="mt-3 whitespace-pre-wrap break-words text-[13px] leading-7 text-[#354043]">
                  {heading[3]}
                </p>
              ) : null}
            </section>
          );
        }

        if (block.startsWith("> ")) {
          return (
            <blockquote
              key={`${index}-${block.slice(0, 24)}`}
              className="border-l-2 border-signal bg-[#fffaf2] px-4 py-3 text-xs leading-6 text-[#62543c]"
            >
              {block.slice(2)}
            </blockquote>
          );
        }

        return (
          <p
            key={`${index}-${block.slice(0, 24)}`}
            className="whitespace-pre-wrap break-words text-[13px] leading-7 text-[#354043]"
          >
            {block}
          </p>
        );
      })}
    </div>
  );
}

function ClassificationPanel({
  paper,
  categoryName,
}: {
  paper: Paper;
  categoryName: string;
}) {
  const candidates = paper.candidateCategories?.length
    ? paper.candidateCategories
    : [
        {
          categoryId: paper.categoryId,
          categoryName,
          confidence: paper.confidence,
          rationale: paper.aiRationale ?? "",
        },
      ];

  return (
    <div>
      <PanelSection title="当前分类" icon={FolderTree}>
        <div className="border border-line bg-[#fafbf9] p-4">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-ink">{categoryName}</p>
              <p className="mt-1 text-[10px] text-muted">
                来源：
                {paper.source === "model" ? "模型自动分类" : "人工整理或迁移"}
              </p>
            </div>
            <span className="inline-flex h-6 items-center rounded-full bg-accent-soft px-2 text-[10px] font-medium text-accent">
              主分类
            </span>
          </div>
          <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-[#e7eae7]">
            <div
              className="h-full rounded-full bg-accent"
              style={{ width: `${paper.confidence * 100}%` }}
            />
          </div>
        </div>
      </PanelSection>

      <PanelSection
        title="候选分类"
        icon={Sparkles}
        action={
          <button
            type="button"
            className="text-[10px] font-medium text-muted"
            disabled
            title="重新分类接口尚未接入"
          >
            重新分类
          </button>
        }
      >
        <div className="space-y-3">
          {candidates.map((candidate, index) => (
            <div
              key={`${candidate.categoryId}-${index}`}
              className="flex items-center gap-3 border border-line px-3 py-3"
              title={candidate.rationale}
            >
              <span
                className={cn(
                  "flex h-6 w-6 items-center justify-center rounded text-[10px] font-semibold",
                  index === 0
                    ? "bg-accent text-white"
                    : "bg-[#f0f2ef] text-muted",
                )}
              >
                {index + 1}
              </span>
              <span className="min-w-0 flex-1 truncate text-xs text-ink">
                {candidate.categoryName}
              </span>
              <span className="text-[10px] text-muted">
                {Math.round(candidate.confidence * 100)}%
              </span>
              <ChevronRight className="h-3.5 w-3.5 text-muted" />
            </div>
          ))}
        </div>
      </PanelSection>

      <PanelSection title="分类依据" icon={Quote}>
        <p className="text-xs leading-6 text-[#414b4d]">
          {paper.aiRationale || "当前记录没有分类依据。"}
        </p>
      </PanelSection>
    </div>
  );
}

function QaPanel() {
  return (
    <div className="flex min-h-[640px] flex-col">
      <div className="flex flex-1 flex-col items-center justify-center px-6 text-center">
        <span className="flex h-11 w-11 items-center justify-center rounded-md bg-[#f0f2ef] text-muted">
          <Bot className="h-5 w-5" />
        </span>
        <h2 className="mt-4 text-sm font-semibold text-ink">
          知识库问答接口尚未接入
        </h2>
        <p className="mt-2 max-w-xs text-xs leading-5 text-muted">
          当前版本不会生成或拼接答案。接入检索、证据校验和页码引用接口后，问答会在真实论文文本上运行。
        </p>
      </div>

      <div className="sticky bottom-0 border-t border-line bg-white p-4">
        <div className="border border-line bg-[#fafbf9] p-2">
          <textarea
            disabled
            className="min-h-20 w-full resize-none border-0 bg-transparent px-1 py-1 text-xs leading-5 text-muted outline-none"
            placeholder="问答功能尚未接入"
          />
          <div className="flex items-center justify-between border-t border-line pt-2">
            <span className="text-[9px] text-muted">不会返回演示答案</span>
            <button
              type="button"
              disabled
              className="flex h-8 items-center gap-1.5 rounded bg-accent px-3 text-[11px] font-medium text-white opacity-50"
            >
              <Send className="h-3.5 w-3.5" />
              提问
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function TasksPanel({ paper }: { paper: Paper }) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadJobs = useCallback(async () => {
    try {
      setJobs(await fetchJobs(200));
      setError("");
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "无法读取任务记录。",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadJobs();
  }, [loadJobs]);

  const paperJobs = jobs.filter((job) => job.paperId === paper.id);
  const hasRunningJob = paperJobs.some(
    (job) => job.status === "queued" || job.status === "running",
  );

  useEffect(() => {
    if (!hasRunningJob) return;
    const timer = window.setTimeout(() => {
      void loadJobs();
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [hasRunningJob, loadJobs]);

  return (
    <div>
      <div className="border-b border-line bg-[#fafbf9] px-5 py-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-semibold text-ink">处理状态</p>
            <p className="mt-1 text-[10px] text-muted">
              最近更新 {formatDateTime(paper.updatedAt)}
            </p>
          </div>
          <StatusBadge status={paper.status} />
        </div>
      </div>

      <PanelSection title="任务记录" icon={ClipboardCheck}>
        {loading ? (
          <div className="flex items-center gap-2 text-xs text-muted">
            <LoaderCircle className="h-4 w-4 animate-spin" />
            正在读取任务记录
          </div>
        ) : error ? (
          <p className="border-l-2 border-danger bg-danger-soft px-3 py-2 text-xs leading-5 text-danger">
            {error}
          </p>
        ) : paperJobs.length ? (
          <div className="space-y-4">
            {paperJobs.map((job) => (
              <div key={job.id}>
                <div className="mb-2 flex items-center justify-between gap-3 text-xs">
                  <span className="flex min-w-0 items-center gap-2 text-ink">
                    {job.status === "succeeded" ? (
                      <Check className="h-3.5 w-3.5 shrink-0 text-accent" />
                    ) : job.status === "failed" ? (
                      <CircleAlert className="h-3.5 w-3.5 shrink-0 text-danger" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5 shrink-0 animate-spin text-signal" />
                    )}
                    <span className="truncate">
                      {jobTypeLabels[job.jobType]}
                    </span>
                  </span>
                  <span className="shrink-0 text-[10px] text-muted">
                    {job.progress}%
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-[#edf0ed]">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      job.status === "failed" ? "bg-danger" : "bg-accent",
                    )}
                    style={{ width: `${job.progress}%` }}
                  />
                </div>
                <p className="mt-1.5 line-clamp-2 text-[10px] leading-4 text-muted">
                  {job.error || job.message}
                </p>
              </div>
            ))}
          </div>
        ) : (
          <EmptyValue>
            没有与该论文关联的任务记录。迁移导入的论文不会生成新的处理任务。
          </EmptyValue>
        )}
      </PanelSection>

      <PanelSection title="文件版本" icon={FileText}>
        <div className="border border-line p-3">
          <div className="flex items-start gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded bg-[#f0f2ef] text-muted">
              <FileText className="h-4 w-4" />
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-medium text-ink">
                {paper.title}.pdf
              </p>
              <p className="mt-1 text-[10px] text-muted">
                {paper.fileSize || "大小未知"} · {paper.pageCount || "未知"} 页
              </p>
            </div>
          </div>
        </div>
      </PanelSection>

      <div className="px-5 py-5">
        <Link href="/review" className="btn-secondary w-full">
          <ClipboardCheck className="h-4 w-4" />
          查看复核队列
        </Link>
      </div>
    </div>
  );
}
