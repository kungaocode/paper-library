import type {
  AnalysisResult,
  CategoryCandidate,
  Category,
  ClassificationResult,
  Innovation,
  Job,
  JobResult,
  ModelConnectionTest,
  ModelStatus,
  Paper,
  PaperStatus,
  PaperTranslation,
  ReadingStatus,
  TranslationStatus,
} from "@/lib/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";

type ApiPaper = {
  id: string;
  title: string;
  title_zh?: string;
  authors?: string[];
  venue?: string;
  year?: number;
  abstract?: string;
  category_id: string;
  status: string;
  reading_status?: string;
  source?: string;
  confidence?: number;
  updated_at: string;
  file_size?: string;
  page_count?: number;
  tags?: string[];
  file_url?: string;
  original_url?: string;
  ai_rationale?: string;
  translation_status?: string;
  translation_progress?: number;
  translation_page_count?: number;
  translation_completed_pages?: number;
  translation_updated_at?: string;
  translation_model?: string;
  translation_error?: string;
  translation_url?: string;
  candidate_categories?: Array<{
    category_id: string;
    category_name: string;
    confidence?: number;
    rationale?: string;
  }>;
  summary?: {
    problem?: string;
    method?: string;
    findings?: string[];
    innovations?: Array<{
      claim?: string;
      evidence_pages?: number[];
      evidence_quotes?: string[];
    }>;
    limitations?: string[];
    thesis_zh?: string;
    novelty_zh?: string;
    thesis_en?: string;
    novelty_en?: string;
    relation_to_library?: string;
    evidence_pages?: number[];
  };
};

type ApiInnovation = {
  claim?: string;
  evidence_pages?: number[];
  evidence_quotes?: string[];
};

type ApiJob = {
  id: string;
  paper_id?: string;
  paper_title: string;
  job_type?: string;
  status: string;
  progress?: number;
  message?: string;
  stage?: string;
  updated_at?: string;
  source_url?: string;
  error?: string;
  created_at?: string;
  result?: {
    phase?: string;
    classification?: {
      canonical_title?: string;
      title_zh?: string;
      authors?: string[];
      venue?: string;
      year?: number;
      abstract?: string;
      language?: string;
      keywords?: string[];
      primary_category_id?: string;
      primary_category_name?: string;
      confidence?: number;
      rationale?: string;
      candidate_categories?: ApiPaper["candidate_categories"];
      needs_review?: boolean;
    } | null;
    analysis?: {
      problem?: string;
      method?: string;
      findings?: string[];
      innovations?: ApiInnovation[];
      limitations?: string[];
      thesis_zh?: string;
      novelty_zh?: string;
      thesis_en?: string;
      novelty_en?: string;
      relation_to_library?: string;
      confidence?: number;
      needs_review?: boolean;
    } | null;
    category_id?: string;
    category_name?: string;
    destination?: string;
  } | null;
};

type ApiPaperTranslation = {
  paper_id: string;
  status: string;
  progress?: number;
  page_count?: number;
  completed_pages?: number;
  text?: string | null;
  error?: string;
  model?: string;
  updated_at?: string;
  download_url?: string;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
    credentials: "include",
    cache: init.cache ?? "no-store",
  });

  if (!response.ok) {
    if (
      response.status === 401 &&
      path !== "/api/auth/login" &&
      typeof window !== "undefined"
    ) {
      await fetch(`${API_BASE_URL}/api/auth/logout`, {
        method: "POST",
        credentials: "include",
        cache: "no-store",
      }).catch(() => undefined);
      window.location.assign("/login");
    }

    const detail = await response
      .json()
      .then((payload) => payload?.detail)
      .catch(() => null);
    const message =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item?.msg).filter(Boolean).join("；")
          : `请求失败：${response.status}`;
    throw new ApiError(message || `请求失败：${response.status}`, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

const paperStatuses = new Set<PaperStatus>([
  "uploaded",
  "extracting",
  "text_extracted",
  "classifying",
  "analyzing",
  "ready",
  "needs_review",
  "failed",
  "archived",
]);

function toPaperStatus(value: string): PaperStatus {
  return paperStatuses.has(value as PaperStatus)
    ? (value as PaperStatus)
    : "needs_review";
}

function toReadingStatus(value?: string): ReadingStatus {
  return value === "reading" || value === "finished" ? value : "unread";
}

function toSource(value?: string): Paper["source"] {
  return value === "manual" || value === "migration" ? value : "model";
}

const translationStatuses = new Set<TranslationStatus>([
  "not_started",
  "queued",
  "running",
  "ready",
  "failed",
]);

function toTranslationStatus(value?: string): TranslationStatus {
  return translationStatuses.has(value as TranslationStatus)
    ? (value as TranslationStatus)
    : "not_started";
}

function mapInnovation(
  innovation: ApiInnovation,
): Innovation {
  return {
    claim: innovation?.claim ?? "",
    evidencePages: innovation?.evidence_pages ?? [],
    evidenceQuotes: innovation?.evidence_quotes ?? [],
  };
}

function mapCandidate(
  candidate: NonNullable<ApiPaper["candidate_categories"]>[number],
): CategoryCandidate {
  return {
    categoryId: candidate.category_id,
    categoryName: candidate.category_name,
    confidence: candidate.confidence ?? 0,
    rationale: candidate.rationale ?? "",
  };
}

function mapClassification(
  value: NonNullable<NonNullable<ApiJob["result"]>["classification"]>,
): ClassificationResult {
  return {
    canonicalTitle: value.canonical_title ?? "",
    titleZh: value.title_zh ?? "",
    authors: value.authors ?? [],
    venue: value.venue ?? "",
    year: value.year ?? 0,
    abstract: value.abstract ?? "",
    language: value.language ?? "",
    keywords: value.keywords ?? [],
    primaryCategoryId: value.primary_category_id ?? "",
    primaryCategoryName: value.primary_category_name ?? "",
    confidence: value.confidence ?? 0,
    rationale: value.rationale ?? "",
    candidateCategories: (value.candidate_categories ?? []).map(mapCandidate),
    needsReview: value.needs_review ?? false,
  };
}

function mapAnalysis(
  value: NonNullable<NonNullable<ApiJob["result"]>["analysis"]>,
): AnalysisResult {
  return {
    problem: value.problem ?? "",
    method: value.method ?? "",
    findings: value.findings ?? [],
    innovations: (value.innovations ?? []).map(mapInnovation),
    limitations: value.limitations ?? [],
    thesisZh: value.thesis_zh ?? "",
    noveltyZh: value.novelty_zh ?? "",
    thesisEn: value.thesis_en ?? "",
    noveltyEn: value.novelty_en ?? "",
    relationToLibrary: value.relation_to_library ?? "",
    confidence: value.confidence ?? 0,
    needsReview: value.needs_review ?? false,
  };
}

function mapJobResult(
  result: ApiJob["result"],
): JobResult | undefined {
  if (!result) return undefined;
  return {
    phase: result.phase ?? "",
    classification: result.classification
      ? mapClassification(result.classification)
      : undefined,
    analysis: result.analysis ? mapAnalysis(result.analysis) : undefined,
    categoryId: result.category_id ?? "",
    categoryName: result.category_name ?? "",
    destination: result.destination ?? "",
  };
}

export function mapApiPaper(paper: ApiPaper): Paper {
  const summary = paper.summary ?? {};
  return {
    id: paper.id,
    title: paper.title,
    titleZh: paper.title_zh,
    authors: paper.authors ?? [],
    venue: paper.venue ?? "",
    year: paper.year ?? 0,
    abstract: paper.abstract ?? "",
    categoryId: paper.category_id,
    status: toPaperStatus(paper.status),
    readingStatus: toReadingStatus(paper.reading_status),
    source: toSource(paper.source),
    confidence: paper.confidence ?? 0,
    updatedAt: paper.updated_at,
    fileSize: paper.file_size ?? "",
    pageCount: paper.page_count ?? 0,
    tags: paper.tags ?? [],
    fileUrl: paper.file_url,
    originalUrl: paper.original_url,
    aiRationale: paper.ai_rationale,
    translationStatus: toTranslationStatus(paper.translation_status),
    translationProgress: paper.translation_progress ?? 0,
    translationPageCount: paper.translation_page_count ?? 0,
    translationCompletedPages: paper.translation_completed_pages ?? 0,
    translationUpdatedAt: paper.translation_updated_at,
    translationModel: paper.translation_model,
    translationError: paper.translation_error,
    translationUrl: paper.translation_url,
    candidateCategories: (paper.candidate_categories ?? []).map(mapCandidate),
    summary: {
      problem: summary.problem ?? "",
      method: summary.method ?? "",
      findings: summary.findings ?? [],
      innovations: (summary.innovations ?? []).map(mapInnovation),
      limitations: summary.limitations ?? [],
      thesisZh: summary.thesis_zh,
      noveltyZh: summary.novelty_zh,
      thesisEn: summary.thesis_en,
      noveltyEn: summary.novelty_en,
      relationToLibrary: summary.relation_to_library,
      evidencePages: summary.evidence_pages,
    },
  };
}

export function mapApiJob(job: ApiJob): Job {
  const jobTypes = new Set<Job["jobType"]>([
    "import",
    "extract",
    "classify",
    "analyze",
    "translate",
    "embed",
    "export",
  ]);
  const statuses = new Set<Job["status"]>([
    "queued",
    "running",
    "succeeded",
    "failed",
  ]);
  return {
    id: job.id,
    paperId: job.paper_id ?? "",
    paperTitle: job.paper_title,
    jobType: jobTypes.has(job.job_type as Job["jobType"])
      ? (job.job_type as Job["jobType"])
      : "import",
    status: statuses.has(job.status as Job["status"])
      ? (job.status as Job["status"])
      : "failed",
    progress: job.progress ?? 0,
    message: job.message ?? "",
    updatedAt: job.updated_at ?? "",
    stage: job.stage,
    sourceUrl: job.source_url,
    error: job.error,
    createdAt: job.created_at,
    result: mapJobResult(job.result),
  };
}

type ApiCategory = {
  id: string;
  directory?: string;
  nameZh: string;
  nameEn: string;
  description?: string;
};

const categoryGroups: Record<string, Category["group"]> = {
  "cat-01": "security",
  "cat-02": "security",
  "cat-03": "security",
  "cat-04": "security",
  "cat-05": "systems",
  "cat-06": "alignment",
  "cat-07": "alignment",
  "cat-08": "reasoning",
  "cat-09": "reasoning",
  "cat-10": "systems",
  "cat-11": "systems",
  "cat-12": "security",
};

export function mapApiCategory(category: ApiCategory): Category {
  const fallbackSlug = category.id.replace(/^cat-/, "category-");
  return {
    id: category.id,
    slug: category.directory ?? fallbackSlug,
    nameZh: category.nameZh,
    nameEn: category.nameEn,
    description: category.description ?? "",
    count: 0,
    group: categoryGroups[category.id] ?? "systems",
  };
}

export async function fetchCategories(): Promise<Category[]> {
  const payload = await apiFetch<ApiCategory[]>("/api/categories");
  return payload.map(mapApiCategory);
}

export async function fetchPapers(limit = 500): Promise<Paper[]> {
  const payload = await apiFetch<ApiPaper[]>(`/api/papers?limit=${limit}`);
  return payload.map(mapApiPaper);
}

export async function fetchPaperById(id: string): Promise<Paper> {
  const payload = await apiFetch<ApiPaper>(`/api/papers/${encodeURIComponent(id)}`);
  return mapApiPaper(payload);
}

export function mapApiTranslation(
  payload: ApiPaperTranslation,
): PaperTranslation {
  return {
    paperId: payload.paper_id,
    status: toTranslationStatus(payload.status),
    progress: payload.progress ?? 0,
    pageCount: payload.page_count ?? 0,
    completedPages: payload.completed_pages ?? 0,
    text: payload.text ?? undefined,
    error: payload.error ?? "",
    model: payload.model ?? "",
    updatedAt: payload.updated_at ?? "",
    downloadUrl: payload.download_url ?? "",
  };
}

export async function fetchPaperTranslation(
  paperId: string,
): Promise<PaperTranslation> {
  const payload = await apiFetch<ApiPaperTranslation>(
    `/api/papers/${encodeURIComponent(paperId)}/translation`,
  );
  return mapApiTranslation(payload);
}

export async function startPaperTranslation(
  paperId: string,
): Promise<PaperTranslation> {
  const payload = await apiFetch<ApiPaperTranslation>(
    `/api/papers/${encodeURIComponent(paperId)}/translation`,
    { method: "POST" },
  );
  return mapApiTranslation(payload);
}

export async function createUrlImport(url: string): Promise<Job> {
  const payload = await apiFetch<ApiJob>("/api/imports/url", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
  return mapApiJob(payload);
}

export async function createFileImport(file: File): Promise<Job> {
  const body = new FormData();
  body.append("file", file);
  const payload = await apiFetch<ApiJob>("/api/imports/file", {
    method: "POST",
    body,
  });
  return mapApiJob(payload);
}

export async function fetchJobs(limit = 50): Promise<Job[]> {
  const payload = await apiFetch<ApiJob[]>(`/api/jobs?limit=${limit}`);
  return payload.map(mapApiJob);
}

export async function fetchJob(id: string): Promise<Job> {
  return mapApiJob(await apiFetch<ApiJob>(`/api/jobs/${encodeURIComponent(id)}`));
}

export async function retryJob(id: string): Promise<Job> {
  const payload = await apiFetch<ApiJob>(
    `/api/jobs/${encodeURIComponent(id)}/retry`,
    { method: "POST" },
  );
  return mapApiJob(payload);
}

export async function fetchModelStatus(): Promise<ModelStatus> {
  const payload = await apiFetch<{
    provider: string;
    model: string;
    base_url: string;
    configured: boolean;
  }>("/api/settings/models");
  return {
    provider: payload.provider,
    model: payload.model,
    baseUrl: payload.base_url,
    configured: payload.configured,
  };
}

export async function testModelConnection(): Promise<ModelConnectionTest> {
  const payload = await apiFetch<{
    ok: boolean;
    message: string;
    latency_ms: number;
    provider: string;
    model: string;
  }>("/api/settings/models/test", { method: "POST" });
  return {
    ok: payload.ok,
    message: payload.message,
    latencyMs: payload.latency_ms,
    provider: payload.provider,
    model: payload.model,
  };
}

export function paperFileUrl(paper: Pick<Paper, "fileUrl">): string | null {
  const value = paper.fileUrl?.trim();
  if (!value) return null;

  try {
    const url = new URL(value, `${API_BASE_URL}/`);
    if (url.protocol !== "http:" && url.protocol !== "https:") {
      return null;
    }
    return url.toString();
  } catch {
    return null;
  }
}

export function translationFileUrl(
  translation: Pick<PaperTranslation, "downloadUrl">,
): string | null {
  if (!translation.downloadUrl) return null;
  return new URL(translation.downloadUrl, `${API_BASE_URL}/`).toString();
}

export { API_BASE_URL };
