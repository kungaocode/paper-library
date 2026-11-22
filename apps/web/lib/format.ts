import type { PaperStatus, ReadingStatus } from "@/lib/types";

export const paperStatusLabel: Record<PaperStatus, string> = {
  uploaded: "已上传",
  extracting: "提取中",
  text_extracted: "已提取",
  classifying: "分类中",
  analyzing: "分析中",
  ready: "可阅读",
  needs_review: "待复核",
  failed: "失败",
  archived: "已归档",
};

export const readingStatusLabel: Record<ReadingStatus, string> = {
  unread: "未读",
  reading: "阅读中",
  finished: "已读",
};

export function formatNumber(value: number) {
  return new Intl.NumberFormat("zh-CN").format(value);
}

export function formatDateTime(value: string) {
  if (!value) return "未知";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatAuthors(authors: string[]) {
  if (authors.length <= 2) return authors.join(" / ");
  return `${authors.slice(0, 2).join(" / ")} 等 ${authors.length} 人`;
}
