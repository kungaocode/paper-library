import { PageHeader } from "@/components/PageHeader";
import { UploadPanel } from "@/components/UploadPanel";

export default function InboxPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Processing"
        title="上传与处理"
        description="导入 PDF，并从同一队列跟踪提取、分类、解读和索引任务。"
      />
      <UploadPanel />
    </div>
  );
}
