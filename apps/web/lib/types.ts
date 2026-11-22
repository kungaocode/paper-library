export type PaperStatus =
  | "uploaded"
  | "extracting"
  | "text_extracted"
  | "classifying"
  | "analyzing"
  | "ready"
  | "needs_review"
  | "failed"
  | "archived";

export type ReadingStatus = "unread" | "reading" | "finished";
export type TranslationStatus =
  | "not_started"
  | "queued"
  | "running"
  | "ready"
  | "failed";

export interface Category {
  id: string;
  slug: string;
  nameZh: string;
  nameEn: string;
  description: string;
  count: number;
  group: "security" | "alignment" | "reasoning" | "systems";
}

export interface Paper {
  id: string;
  title: string;
  titleZh?: string;
  authors: string[];
  venue: string;
  year: number;
  abstract: string;
  categoryId: string;
  status: PaperStatus;
  readingStatus: ReadingStatus;
  source: "manual" | "model" | "migration";
  confidence: number;
  updatedAt: string;
  fileSize: string;
  pageCount: number;
  tags: string[];
  fileUrl?: string;
  originalUrl?: string;
  aiRationale?: string;
  translationStatus: TranslationStatus;
  translationProgress: number;
  translationPageCount: number;
  translationCompletedPages: number;
  translationUpdatedAt?: string;
  translationModel?: string;
  translationError?: string;
  translationUrl?: string;
  candidateCategories?: CategoryCandidate[];
  summary: {
    problem: string;
    method: string;
    findings: string[];
    innovations: Innovation[];
    limitations: string[];
    thesisZh?: string;
    noveltyZh?: string;
    thesisEn?: string;
    noveltyEn?: string;
    relationToLibrary?: string;
    evidencePages?: number[];
  };
}

export interface Innovation {
  claim: string;
  evidencePages: number[];
  evidenceQuotes: string[];
}

export interface CategoryCandidate {
  categoryId: string;
  categoryName: string;
  confidence: number;
  rationale: string;
}

export interface Job {
  id: string;
  paperId: string;
  paperTitle: string;
  jobType:
    | "import"
    | "extract"
    | "classify"
    | "analyze"
    | "translate"
    | "embed"
    | "export";
  status: "queued" | "running" | "succeeded" | "failed";
  progress: number;
  message: string;
  updatedAt: string;
  stage?: string;
  sourceUrl?: string;
  error?: string;
  createdAt?: string;
  result?: JobResult;
}

export interface PaperTranslation {
  paperId: string;
  status: TranslationStatus;
  progress: number;
  pageCount: number;
  completedPages: number;
  text?: string;
  error: string;
  model: string;
  updatedAt: string;
  downloadUrl: string;
}

export interface ClassificationResult {
  canonicalTitle: string;
  titleZh: string;
  authors: string[];
  venue: string;
  year: number;
  abstract: string;
  language: string;
  keywords: string[];
  primaryCategoryId: string;
  primaryCategoryName: string;
  confidence: number;
  rationale: string;
  candidateCategories: CategoryCandidate[];
  needsReview: boolean;
}

export interface AnalysisResult {
  problem: string;
  method: string;
  findings: string[];
  innovations: Innovation[];
  limitations: string[];
  thesisZh: string;
  noveltyZh: string;
  thesisEn: string;
  noveltyEn: string;
  relationToLibrary: string;
  confidence: number;
  needsReview: boolean;
}

export interface JobResult {
  phase: string;
  classification?: ClassificationResult;
  analysis?: AnalysisResult;
  categoryId: string;
  categoryName: string;
  destination: string;
}

export interface ModelStatus {
  provider: string;
  model: string;
  baseUrl: string;
  configured: boolean;
}

export interface ModelConnectionTest {
  ok: boolean;
  message: string;
  latencyMs: number;
  provider: string;
  model: string;
}

export interface Citation {
  paperId: string;
  paperTitle: string;
  page: number;
  quote: string;
}

export interface QaMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  insufficientEvidence?: boolean;
}

export interface DashboardData {
  paperCount: number;
  readyCount: number;
  reviewCount: number;
  runningCount: number;
  categoryCount: number;
  recentPapers: Paper[];
  categoryDistribution: Array<{
    category: Category;
    count: number;
    percent: number;
  }>;
  jobs: Job[];
}
