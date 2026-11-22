import { PageHeader } from "@/components/PageHeader";
import { AssistantWorkspace } from "@/components/AssistantWorkspace";

export default function AssistantPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Knowledge assistant"
        title="AI 解读"
        description="在单篇论文、当前分类或整个知识库范围内检索，并返回可定位到原文页码的答案。"
      />
      <AssistantWorkspace />
    </div>
  );
}
