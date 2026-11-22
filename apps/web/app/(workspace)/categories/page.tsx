import { PageHeader } from "@/components/PageHeader";
import { CategoriesEditor } from "@/components/CategoriesEditor";

export default function CategoriesPage() {
  return (
    <div>
      <PageHeader
        eyebrow="Taxonomy"
        title="分类管理"
        description="维护主题树、分类边界和排序，自动分类会使用这里的描述作为判断依据。"
      />
      <CategoriesEditor />
    </div>
  );
}
