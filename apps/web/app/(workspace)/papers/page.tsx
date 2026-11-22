import { Suspense } from "react";

import { PageHeader } from "@/components/PageHeader";
import { PapersBrowser } from "@/components/PapersBrowser";

export default function PapersPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Library"
        title="论文库"
        description="按主题、状态和阅读进度浏览个人论文索引。"
      />
      <Suspense
        fallback={
          <section className="panel mt-5 flex min-h-64 items-center justify-center px-5 text-center">
            <p className="text-xs text-muted">正在准备论文库筛选器</p>
          </section>
        }
      >
        <PapersBrowser />
      </Suspense>
    </div>
  );
}
