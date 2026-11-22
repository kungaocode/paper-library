import { Suspense } from "react";

import { PaperWindowViewer } from "@/components/PaperWindowViewer";

export const dynamic = "force-dynamic";

export default async function PaperWindowPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <Suspense
      fallback={
        <main className="flex min-h-dvh items-center justify-center bg-[#e7e9e5] text-sm text-muted">
          正在准备论文阅读器
        </main>
      }
    >
      <PaperWindowViewer paperId={id} />
    </Suspense>
  );
}
