import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { PaperWorkspace } from "@/components/PaperWorkspace";
import { PaperWindowLink } from "@/components/PaperWindowLink";
import { StatusBadge } from "@/components/StatusBadge";
import {
  fetchCategories,
  fetchPaperById,
  paperFileUrl,
} from "@/lib/api";
import { formatAuthors, formatDateTime } from "@/lib/format";

export const dynamic = "force-dynamic";

export default async function PaperDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const [paper, categories] = await Promise.all([
    fetchPaperById(id).catch(() => null),
    fetchCategories().catch(() => []),
  ]);
  if (!paper) notFound();
  const category = categories.find((item) => item.id === paper.categoryId);
  const pdfHref = paperFileUrl(paper);

  return (
    <div className="-mx-4 -my-6 flex min-h-[calc(100dvh-3.5rem)] flex-col sm:-mx-6 lg:-mx-8 lg:-my-8">
      <div className="shrink-0 border-b border-line bg-canvas px-3 py-2.5 sm:px-4 lg:px-5">
        <div className="flex min-h-6 flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted">
          <Link
            href="/papers"
            className="flex items-center gap-1.5 transition-colors hover:text-ink"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            论文库
          </Link>
          <span>/</span>
          <span className="truncate">{category?.nameZh}</span>
          <StatusBadge status={paper.status} />
          <span className="rounded bg-white px-1.5 py-0.5 font-medium ring-1 ring-line">
            {paper.venue} {paper.year}
          </span>
          <span>
            {paper.fileSize} · {paper.pageCount} 页
          </span>
          <span className="hidden sm:inline">
            更新于 {formatDateTime(paper.updatedAt)}
          </span>
          <div className="ml-auto flex shrink-0 items-center gap-2">
            {pdfHref ? (
              <PaperWindowLink
                paperId={paper.id}
                label="在新窗口打开"
                className="inline-flex h-7 items-center gap-1.5 rounded border border-line bg-white px-2 text-[10px] font-medium text-ink transition-colors hover:border-[#aab3af]"
              />
            ) : null}
          </div>
        </div>

        <div className="mt-1.5 flex min-w-0 items-center gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-base font-semibold leading-6 tracking-[-0.01em] text-ink">
              {paper.title}
            </h1>
            <div className="mt-0.5 flex min-w-0 items-center gap-2 text-[10px] text-muted">
              {paper.titleZh ? (
                <>
                  <span className="min-w-0 truncate">{paper.titleZh}</span>
                  <span className="shrink-0">·</span>
                </>
              ) : null}
              <span className="min-w-0 truncate">
                {formatAuthors(paper.authors)}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 p-1.5 sm:p-2">
        <PaperWorkspace paper={paper} categories={categories} />
      </div>
    </div>
  );
}
