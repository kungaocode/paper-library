from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .categories import CategoryDefinition
from .schemas import AnalysisResult, ClassificationResult


class KnowledgeBaseError(RuntimeError):
    pass


def organize_pdf_and_append(
    *,
    paper_root: Path,
    source_pdf: Path,
    category: CategoryDefinition,
    classification: ClassificationResult,
    analysis: AnalysisResult,
) -> Path:
    destination_dir = paper_root / "completed" / category.directory
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = unique_destination(destination_dir / source_pdf.name)

    source_pdf.replace(destination)
    try:
        append_entry(
            knowledge_base_path=paper_root / "KNOWLEDGE_BASE.md",
            category=category,
            classification=classification,
            analysis=analysis,
            destination=destination,
        )
    except Exception:
        destination.replace(source_pdf)
        raise
    return destination


def unique_destination(destination: Path) -> Path:
    if not destination.exists():
        return destination
    index = 2
    while True:
        candidate = destination.with_name(f"{destination.stem} ({index}){destination.suffix}")
        if not candidate.exists():
            return candidate
        index += 1


def append_entry(
    *,
    knowledge_base_path: Path,
    category: CategoryDefinition,
    classification: ClassificationResult,
    analysis: AnalysisResult,
    destination: Path,
) -> None:
    if not knowledge_base_path.exists():
        raise KnowledgeBaseError(f"知识库索引不存在：{knowledge_base_path}")

    original = knowledge_base_path.read_text(encoding="utf-8")
    lines = original.splitlines()
    section_start = find_section_start(lines, category.index)
    if section_start is None:
        raise KnowledgeBaseError(f"未找到分类章节：{category.name_zh}")

    section_end = len(lines)
    for index in range(section_start + 1, len(lines)):
        if lines[index].startswith("## "):
            section_end = index
            break

    insertion = section_end
    for index in range(section_start + 1, section_end):
        if lines[index].startswith("### 本节阅读顺序"):
            insertion = index
            break
    else:
        while insertion > section_start + 1 and (
            not lines[insertion - 1].strip() or lines[insertion - 1].strip() == "---"
        ):
            insertion -= 1

    entry_lines = format_entry(category, classification, analysis, destination)
    new_lines = [*lines[:insertion], "", *entry_lines, "", *lines[insertion:]]
    updated = "\n".join(new_lines).rstrip() + "\n"
    updated = update_header_counts(updated, category.index)
    atomic_write(knowledge_base_path, updated)


def find_section_start(lines: list[str], category_index: int) -> int | None:
    pattern = re.compile(rf"^##\s+{category_index}\.\s+")
    for index, line in enumerate(lines):
        if pattern.match(line):
            return index
    return None


def format_entry(
    category: CategoryDefinition,
    classification: ClassificationResult,
    analysis: AnalysisResult,
    destination: Path,
) -> list[str]:
    del category
    authors = classification.authors or ["Unknown authors"]
    author_label = ", ".join(authors[:3])
    if len(authors) > 3:
        author_label += " et al."
    publication = " ".join(
        part for part in (classification.venue.strip(), str(classification.year or "").strip()) if part
    )
    suffix = f"（{author_label}{', ' + publication if publication else ''}）"
    title = classification.canonical_title.strip() or classification.title_zh.strip() or "Untitled paper"
    relative_pdf = destination.relative_to(destination.parents[1])

    lines = [
        f"### {title}{suffix}",
        "",
        f"- **PDF**：[{relative_pdf.as_posix()}](<{destination.resolve()}>)",
        f"- **核心论点（中）**：{single_line(analysis.thesis_zh)}",
        f"- **创新点（中）**：{single_line(analysis.novelty_zh)}",
        f"- **Core thesis (EN)**: {single_line(analysis.thesis_en)}",
        f"- **Novelty (EN)**: {single_line(analysis.novelty_en)}",
    ]
    if analysis.relation_to_library.strip():
        lines.append(f"- **与我体系的关系**：{single_line(analysis.relation_to_library)}")
    lines.extend(
        [
            "- **导入来源**：模型自动分类与结构化解读；保留原始 PDF，人工摘要可在后续复核中覆盖。",
            f"- **分类依据**：{single_line(classification.rationale or '模型分类结果')}",
        ]
    )
    return lines


def single_line(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def update_header_counts(content: str, category_index: int) -> str:
    count_pattern = re.compile(r"(论文总数：\*\*)(\d+)(\*\*)")
    match = count_pattern.search(content)
    if match:
        count = int(match.group(2)) + 1
        content = count_pattern.sub(rf"\g<1>{count}\g<3>", content, count=1)

    content = re.sub(
        r"(最后更新：)(\d{4}-\d{2}-\d{2})",
        rf"\g<1>{date.today().isoformat()}",
        content,
        count=1,
    )

    index_pattern = re.compile(
        rf"^(\s*{category_index}\.\s+\[[^\]]+\]\([^)]+\)\s+\()(\d+)(\))$",
        re.MULTILINE,
    )

    def increment_index(match: re.Match[str]) -> str:
        return f"{match.group(1)}{int(match.group(2)) + 1}{match.group(3)}"

    return index_pattern.sub(increment_index, content, count=1)


def atomic_write(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
