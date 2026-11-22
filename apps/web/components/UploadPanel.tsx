"use client";

import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  FileText,
  FolderOpen,
  Link2,
  LoaderCircle,
  RefreshCw,
  RotateCcw,
  UploadCloud,
  X,
} from "lucide-react";
import Link from "next/link";
import {
  DragEvent,
  FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";

import {
  ApiError,
  createFileImport,
  createUrlImport,
  fetchJobs,
  fetchModelStatus,
  retryJob,
} from "@/lib/api";
import { cn } from "@/lib/cn";
import type { Job, ModelStatus } from "@/lib/types";

type Notice = {
  tone: "info" | "success" | "error";
  message: string;
};

const jobTypeLabels: Record<Job["jobType"], string> = {
  import: "完整导入",
  extract: "文本提取",
  classify: "自动分类",
  analyze: "结构化解读",
  translate: "中文翻译",
  embed: "向量索引",
  export: "导出",
};

const phaseLabels: Record<string, string> = {
  classified: "初分类完成",
  analyzed: "解读完成",
  organizing: "正在归档",
  completed: "处理完成",
};

function formatJobTime(value: string) {
  if (!value) return "刚刚";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function JobResultDetails({ job }: { job: Job }) {
  const result = job.result;
  if (!result || (!result.classification && !result.analysis)) return null;

  const classification = result.classification;
  const analysis = result.analysis;
  const innovation = analysis?.innovations[0];

  return (
    <div className="mt-3 border-l-2 border-accent/35 bg-accent-soft/45 px-3 py-2">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px]">
        {phaseLabels[result.phase] ? (
          <span className="font-medium text-accent">
            {phaseLabels[result.phase]}
          </span>
        ) : null}
        {result.categoryName || classification?.primaryCategoryName ? (
          <span className="text-ink">
            分类：{result.categoryName || classification?.primaryCategoryName}
          </span>
        ) : null}
        {classification ? (
          <span className="text-muted">
            置信度 {Math.round(classification.confidence * 100)}%
          </span>
        ) : null}
      </div>
      {classification?.titleZh ? (
        <p className="mt-1.5 line-clamp-1 text-[10px] text-ink">
          中文题名：{classification.titleZh}
        </p>
      ) : null}
      {classification?.rationale ? (
        <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-muted">
          分类依据：{classification.rationale}
        </p>
      ) : null}
      {analysis?.thesisZh ? (
        <p className="mt-1.5 line-clamp-2 text-[10px] leading-4 text-[#414b4d]">
          核心论点：{analysis.thesisZh}
        </p>
      ) : null}
      {analysis?.noveltyZh ? (
        <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-[#414b4d]">
          创新点：{analysis.noveltyZh}
        </p>
      ) : null}
      {innovation?.claim ? (
        <p className="mt-1 line-clamp-2 text-[10px] leading-4 text-muted">
          证据点：{innovation.claim}
        </p>
      ) : null}
    </div>
  );
}

export function UploadPanel() {
  const inputRef = useRef<HTMLInputElement>(null);
  const notifiedJobs = useRef(new Set<string>());
  const [dragging, setDragging] = useState(false);
  const [uploadingFiles, setUploadingFiles] = useState<File[]>([]);
  const [sourceUrl, setSourceUrl] = useState("");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [modelStatus, setModelStatus] = useState<ModelStatus | null>(null);
  const [modelStatusError, setModelStatusError] = useState("");
  const [modelStatusLoaded, setModelStatusLoaded] = useState(false);
  const [apiAvailable, setApiAvailable] = useState(false);
  const [statusLoaded, setStatusLoaded] = useState(false);
  const [loadError, setLoadError] = useState("");
  const [submittingUrl, setSubmittingUrl] = useState(false);
  const [retryingId, setRetryingId] = useState("");
  const [notice, setNotice] = useState<Notice | null>(null);

  const announceReadyJobs = useCallback((nextJobs: Job[]) => {
    let hasNewPaper = false;
    for (const job of nextJobs) {
      if (
        job.status === "succeeded" &&
        job.paperId &&
        !notifiedJobs.current.has(job.id)
      ) {
        notifiedJobs.current.add(job.id);
        hasNewPaper = true;
      }
    }
    if (hasNewPaper && typeof window !== "undefined") {
      window.dispatchEvent(new Event("paper-library-updated"));
    }
  }, []);

  const loadJobs = useCallback(async () => {
    try {
      const nextJobs = await fetchJobs();
      setJobs(nextJobs);
      announceReadyJobs(nextJobs);
      setApiAvailable(true);
      setLoadError("");
    } catch (error) {
      setApiAvailable(false);
      setLoadError(
        error instanceof Error
          ? error.message
          : "无法连接 API，队列未加载。",
      );
    } finally {
      setStatusLoaded(true);
    }
  }, [announceReadyJobs]);

  useEffect(() => {
    void loadJobs();
    fetchModelStatus()
      .then((status) => {
        setModelStatus(status);
        setModelStatusError("");
      })
      .catch((error) => {
        setModelStatus(null);
        setModelStatusError(
          error instanceof Error ? error.message : "模型状态不可用",
        );
      })
      .finally(() => {
        setModelStatusLoaded(true);
      });
  }, [loadJobs]);

  const hasActiveJobs = jobs.some(
    (job) => job.status === "queued" || job.status === "running",
  );

  useEffect(() => {
    if (!hasActiveJobs) return;
    const timer = window.setTimeout(() => {
      void loadJobs();
    }, 1500);
    return () => window.clearTimeout(timer);
  }, [hasActiveJobs, loadJobs]);

  function addJob(job: Job) {
    setJobs((current) => [
      job,
      ...current.filter((item) => item.id !== job.id),
    ]);
  }

  async function uploadFiles(files: FileList | File[]) {
    const pdfFiles = Array.from(files).filter(
      (file) =>
        file.name.toLowerCase().endsWith(".pdf") &&
        !uploadingFiles.some(
          (item) =>
            item.name === file.name && item.lastModified === file.lastModified,
        ),
    );
    if (!pdfFiles.length) return;

    setNotice(null);
    setUploadingFiles((current) => [...current, ...pdfFiles]);
    const uploadedJobs: Job[] = [];
    const errors: string[] = [];

    for (const file of pdfFiles) {
      try {
        uploadedJobs.push(await createFileImport(file));
      } catch (error) {
        errors.push(
          `${file.name}：${error instanceof Error ? error.message : "上传失败"}`,
        );
      } finally {
        setUploadingFiles((current) => current.filter((item) => item !== file));
      }
    }

    if (uploadedJobs.length) {
      setJobs((current) => [
        ...uploadedJobs,
        ...current.filter(
          (item) => !uploadedJobs.some((job) => job.id === item.id),
        ),
      ]);
      setApiAvailable(true);
      setNotice({
        tone: "success",
        message: `${uploadedJobs.length} 个 PDF 已进入 need_organization，正在自动分类和分析。`,
      });
    }
    if (errors.length) {
      setNotice({ tone: "error", message: errors.join("；") });
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    void uploadFiles(event.dataTransfer.files);
  }

  async function submitUrl(event: FormEvent) {
    event.preventDefault();
    const url = sourceUrl.trim();
    if (!/^https?:\/\//i.test(url)) {
      setNotice({ tone: "error", message: "请输入有效的 http 或 https 论文链接。" });
      return;
    }

    setSubmittingUrl(true);
    setNotice(null);
    try {
      const job = await createUrlImport(url);
      addJob(job);
      setApiAvailable(true);
      setSourceUrl("");
      setNotice({
        tone: "success",
        message: "链接已加入队列，PDF 下载后会自动分类、解读并写入知识库。",
      });
    } catch (error) {
      const message =
        error instanceof ApiError && error.status === 503
          ? "后端已接通，但模型尚未配置。请填写 apps/api/.env 后重启 API。"
          : error instanceof Error
            ? error.message
            : "链接提交失败。";
      setNotice({ tone: "error", message });
    } finally {
      setSubmittingUrl(false);
    }
  }

  async function handleRetry(job: Job) {
    if (!job.sourceUrl?.startsWith("http")) return;
    setRetryingId(job.id);
    setNotice(null);
    try {
      addJob(await retryJob(job.id));
      setNotice({ tone: "info", message: "任务已重新入队。" });
    } catch (error) {
      setNotice({
        tone: "error",
        message: error instanceof Error ? error.message : "重试失败。",
      });
    } finally {
      setRetryingId("");
    }
  }

  async function retryAllFailed() {
    const failed = jobs.filter(
      (job) => job.status === "failed" && job.sourceUrl?.startsWith("http"),
    );
    for (const job of failed) {
      await handleRetry(job);
    }
  }

  const completedCount = jobs.filter((job) => job.status === "succeeded").length;
  const failedCount = jobs.filter((job) => job.status === "failed").length;
  const runningCount = jobs.filter(
    (job) => job.status === "queued" || job.status === "running",
  ).length;
  const modelReady = modelStatus?.configured === true;

  return (
    <>
      <section className="panel mt-5 px-5 py-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-accent-soft text-accent">
              <Link2 className="h-4 w-4" />
            </span>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-ink">从论文链接导入</h2>
              <p className="mt-1 text-xs leading-5 text-muted">
                支持 arXiv、论文主页或可直接下载 PDF 的链接。
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 text-[11px]">
            {!statusLoaded || !modelStatusLoaded ? (
              <span className="inline-flex items-center gap-1.5 text-muted">
                <LoaderCircle className="h-3.5 w-3.5 animate-spin" />
                正在检查 API 和模型
              </span>
            ) : !apiAvailable ? (
              <span className="inline-flex items-center gap-1.5 text-danger">
                <AlertCircle className="h-3.5 w-3.5" />
                API 未连接，队列不可用
              </span>
            ) : modelStatusError ? (
              <span className="inline-flex items-center gap-1.5 text-danger">
                <AlertCircle className="h-3.5 w-3.5" />
                模型状态不可用
              </span>
            ) : modelStatus && !modelStatus.configured ? (
              <span className="inline-flex items-center gap-1.5 text-signal">
                <AlertCircle className="h-3.5 w-3.5" />
                模型未配置
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 text-accent">
                <CheckCircle2 className="h-3.5 w-3.5" />
                {modelStatus
                  ? `${modelStatus.provider}${modelStatus.model ? ` · ${modelStatus.model}` : ""}`
                  : "API 已连接"}
              </span>
            )}
          </div>
        </div>

        <form
          className="mt-5 flex flex-col gap-2 sm:flex-row"
          onSubmit={submitUrl}
        >
          <input
            type="url"
            value={sourceUrl}
            onChange={(event) => setSourceUrl(event.target.value)}
            className="field min-w-0 flex-1"
            placeholder="https://arxiv.org/abs/2501.00001"
            aria-label="论文链接"
          />
          <button
            type="submit"
            className="btn-primary sm:w-32"
            disabled={submittingUrl || !apiAvailable || !modelReady}
          >
            {submittingUrl ? (
              <LoaderCircle className="h-4 w-4 animate-spin" />
            ) : (
              <Link2 className="h-4 w-4" />
            )}
            开始导入
          </button>
        </form>

        {loadError ? (
          <p className="mt-3 border border-danger/25 bg-danger-soft px-3 py-2 text-xs leading-5 text-danger">
            {loadError}
          </p>
        ) : null}

        {modelStatusError ? (
          <p className="mt-3 border border-danger/25 bg-danger-soft px-3 py-2 text-xs leading-5 text-danger">
            {modelStatusError}
          </p>
        ) : null}

        {modelStatus && !modelStatus.configured ? (
          <p className="mt-3 border border-signal/25 bg-signal-soft px-3 py-2 text-xs leading-5 text-signal">
            模型未配置，链接和文件导入已停用。请在后端
            <code className="mx-1">apps/api/.env</code>
            填写模型配置，或设置 <code className="mx-1">LLM_PROVIDER=mock</code>
            进行离线测试。
          </p>
        ) : null}

        {notice ? (
          <p
            className={cn(
              "mt-3 border px-3 py-2 text-xs leading-5",
              notice.tone === "error" &&
                "border-danger/25 bg-danger-soft text-danger",
              notice.tone === "success" &&
                "border-accent/25 bg-accent-soft text-accent",
              notice.tone === "info" &&
                "border-line bg-[#f7f8f6] text-muted",
            )}
          >
            {notice.message}
          </p>
        ) : null}
      </section>

      <section
        className={cn(
          "panel mt-5 flex min-h-[250px] flex-col items-center justify-center border-dashed px-6 py-10 text-center transition-colors",
          dragging && "border-accent bg-accent-soft",
        )}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          multiple
          className="hidden"
          onChange={(event) => {
            if (event.target.files) void uploadFiles(event.target.files);
            event.target.value = "";
          }}
        />
        <span className="flex h-14 w-14 items-center justify-center rounded-md bg-ink text-white">
          {uploadingFiles.length ? (
            <LoaderCircle className="h-6 w-6 animate-spin" />
          ) : (
            <UploadCloud className="h-6 w-6" />
          )}
        </span>
        <h2 className="mt-5 text-base font-semibold text-ink">
          上传 PDF 到收件箱
        </h2>
        <p className="mt-2 max-w-md text-xs leading-5 text-muted">
          文件先进入 need_organization，再自动提取、分类、解读并归档。
        </p>
        <button
          type="button"
          className="btn-primary mt-6"
          onClick={() => inputRef.current?.click()}
          disabled={uploadingFiles.length > 0 || !apiAvailable || !modelReady}
        >
          <FolderOpen className="h-4 w-4" />
          选择 PDF
        </button>

        {uploadingFiles.length ? (
          <div className="mt-6 flex max-w-2xl flex-wrap justify-center gap-2">
            {uploadingFiles.map((file) => (
              <span
                key={`${file.name}-${file.lastModified}`}
                className="inline-flex h-8 items-center gap-2 rounded-full border border-line bg-white px-3 text-[10px] text-muted"
              >
                <LoaderCircle className="h-3 w-3 animate-spin" />
                <span className="max-w-44 truncate">{file.name}</span>
                <button
                  type="button"
                  aria-label={`移除 ${file.name}`}
                  onClick={() =>
                    setUploadingFiles((current) =>
                      current.filter((item) => item !== file),
                    )
                  }
                >
                  <X className="h-3 w-3 hover:text-ink" />
                </button>
              </span>
            ))}
          </div>
        ) : null}
      </section>

      <section className="panel mt-5">
        <div className="flex flex-col gap-3 border-b border-line px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-ink">处理队列</h2>
            <p className="mt-1 text-[11px] text-muted">
              页面会自动轮询，完成后论文库同步刷新
            </p>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              className="btn-secondary h-8 px-2.5 text-xs"
              onClick={() => void loadJobs()}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              刷新
            </button>
            <button
              type="button"
              className="btn-secondary h-8 px-2.5 text-xs"
              onClick={() => void retryAllFailed()}
              disabled={
                !jobs.some(
                  (job) =>
                    job.status === "failed" &&
                    job.sourceUrl?.startsWith("http"),
                ) || Boolean(retryingId)
              }
            >
              <RotateCcw className="h-3.5 w-3.5" />
              重试失败项
            </button>
          </div>
        </div>

        {jobs.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-left">
              <thead>
                <tr className="border-b border-line bg-[#f7f8f6] text-[10px] uppercase tracking-[0.09em] text-muted">
                  <th className="px-5 py-3 font-medium">文件</th>
                  <th className="w-[130px] px-3 py-3 font-medium">任务</th>
                  <th className="w-[120px] px-3 py-3 font-medium">状态</th>
                  <th className="w-[260px] px-3 py-3 font-medium">进度</th>
                  <th className="w-[150px] px-3 py-3 font-medium">更新时间</th>
                  <th className="w-16 px-3 py-3" />
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.id} className="border-b border-line last:border-0">
                    <td className="px-5 py-4">
                      <div className="flex items-start gap-3">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded bg-[#f0f2ef] text-muted">
                          <FileText className="h-4 w-4" />
                        </span>
                        <div className="min-w-0">
                          {job.paperId ? (
                            <Link
                              href={`/papers/${job.paperId}`}
                              className="block max-w-md truncate text-xs font-medium text-ink hover:text-accent"
                            >
                              {job.paperTitle}
                            </Link>
                          ) : (
                            <p className="max-w-md truncate text-xs font-medium text-ink">
                              {job.paperTitle}
                            </p>
                          )}
                          <p
                            className={cn(
                              "mt-1 max-w-lg text-[10px] leading-4",
                              job.status === "failed"
                                ? "text-danger"
                                : "text-muted",
                            )}
                          >
                            {job.error || job.message}
                          </p>
                          <JobResultDetails job={job} />
                        </div>
                      </div>
                    </td>
                    <td className="px-3 py-4 text-xs text-muted">
                      {jobTypeLabels[job.jobType]}
                    </td>
                    <td className="px-3 py-4">
                      {job.status === "succeeded" ? (
                        <span className="inline-flex items-center gap-1.5 text-xs text-accent">
                          <CheckCircle2 className="h-4 w-4" />
                          已完成
                        </span>
                      ) : job.status === "failed" ? (
                        <span className="inline-flex items-center gap-1.5 text-xs text-danger">
                          <AlertCircle className="h-4 w-4" />
                          失败
                        </span>
                      ) : (
                        <span
                          className={cn(
                            "inline-flex items-center gap-1.5 text-xs",
                            job.status === "running"
                              ? "text-signal"
                              : "text-muted",
                          )}
                        >
                          {job.status === "running" ? (
                            <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <span className="h-2 w-2 rounded-full bg-[#bdc4c1]" />
                          )}
                          {job.status === "running" ? "处理中" : "等待中"}
                        </span>
                      )}
                    </td>
                    <td className="px-3 py-4">
                      <div className="flex items-center gap-3">
                        <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-[#edf0ed]">
                          <div
                            className={cn(
                              "h-full rounded-full",
                              job.status === "failed" ? "bg-danger" : "bg-accent",
                            )}
                            style={{ width: `${job.progress}%` }}
                          />
                        </div>
                        <span className="w-8 text-right text-[10px] text-muted">
                          {job.progress}%
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-4 text-[10px] text-muted">
                      {formatJobTime(job.updatedAt)}
                    </td>
                    <td className="px-3 py-4">
                      {job.status === "failed" &&
                      job.sourceUrl?.startsWith("http") ? (
                        <button
                          type="button"
                          className="flex h-8 items-center gap-1.5 rounded px-2 text-[10px] font-medium text-accent hover:bg-accent-soft"
                          onClick={() => void handleRetry(job)}
                          disabled={retryingId === job.id}
                        >
                          <RotateCcw
                            className={cn(
                              "h-3.5 w-3.5",
                              retryingId === job.id && "animate-spin",
                            )}
                          />
                          重试
                        </button>
                      ) : job.paperId ? (
                        <Link
                          href={`/papers/${job.paperId}`}
                          className="flex h-8 w-8 items-center justify-center rounded text-muted hover:bg-[#f2f4f1] hover:text-ink"
                          aria-label="打开论文"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </Link>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="flex min-h-52 flex-col items-center justify-center px-5 text-center">
            <UploadCloud className="h-6 w-6 text-muted/60" />
            <p className="mt-3 text-sm font-medium text-ink">队列为空</p>
            <p className="mt-1 text-xs text-muted">
              提交论文链接或上传 PDF 后，任务会显示在这里。
            </p>
          </div>
        )}
      </section>

      <section className="mt-5 grid gap-3 sm:grid-cols-3">
        {[
          { label: "已完成", value: completedCount, icon: CheckCircle2 },
          { label: "处理中", value: runningCount, icon: RefreshCw },
          { label: "失败任务", value: failedCount, icon: RotateCcw },
        ].map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.label}
              className="panel flex items-center gap-4 px-5 py-4"
            >
              <span className="flex h-9 w-9 items-center justify-center rounded-md bg-[#f0f2ef] text-muted">
                <Icon className="h-4 w-4" />
              </span>
              <div>
                <strong className="block text-sm font-semibold text-ink">
                  {item.value}
                </strong>
                <span className="mt-0.5 block text-[10px] text-muted">
                  {item.label}
                </span>
              </div>
            </div>
          );
        })}
      </section>
    </>
  );
}
