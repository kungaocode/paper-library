from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


class PdfExtractionError(RuntimeError):
    pass


@dataclass
class ExtractedPdf:
    page_count: int
    page_texts: list[str]
    metadata_title: str
    metadata_author: str
    metadata_year: int
    sha256: str
    size_bytes: int

    @property
    def full_text(self) -> str:
        return "\n\n".join(
            f"[PAGE {index}]\n{text}" for index, text in enumerate(self.page_texts, start=1)
        )

    def context(self, max_chars: int, page_limit: int) -> str:
        if not self.page_texts:
            return ""

        selected = select_page_indexes(len(self.page_texts), page_limit)
        chunks: list[str] = []
        used = 0
        for page_index in selected:
            text = self.page_texts[page_index].strip()
            if not text:
                continue
            chunk = f"[PAGE {page_index + 1}]\n{text}"
            remaining = max_chars - used
            if remaining <= 0:
                break
            chunks.append(chunk[:remaining])
            used += len(chunks[-1])
        return "\n\n".join(chunks)


def select_page_indexes(page_count: int, limit: int) -> list[int]:
    if page_count <= limit:
        return list(range(page_count))

    head_count = max(1, int(limit * 0.62))
    tail_count = max(1, int(limit * 0.28))
    middle_count = max(0, limit - head_count - tail_count)

    indexes = list(range(0, min(head_count, page_count)))
    tail_start = max(head_count, page_count - tail_count)
    if middle_count:
        candidates = list(range(head_count, tail_start))
        if candidates:
            step = max(1, len(candidates) // middle_count)
            indexes.extend(candidates[::step][:middle_count])
    indexes.extend(range(tail_start, page_count))
    return sorted(set(indexes))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def extract_pdf(path: Path) -> ExtractedPdf:
    if not path.exists():
        raise PdfExtractionError(f"PDF 不存在：{path}")
    if path.stat().st_size == 0:
        raise PdfExtractionError("PDF 文件为空。")

    try:
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as error:
                raise PdfExtractionError("PDF 已加密，无法提取文本。") from error

        page_texts: list[str] = []
        for page in reader.pages:
            try:
                text = page.extract_text() or ""
            except Exception:
                text = ""
            page_texts.append(clean_text(text))
    except PdfExtractionError:
        raise
    except Exception as error:
        raise PdfExtractionError(f"PDF 解析失败：{error}") from error

    if not any(text.strip() for text in page_texts):
        raise PdfExtractionError(
            "PDF 没有可提取文本，可能是扫描件。当前版本暂未启用 OCR。"
        )

    metadata = reader.metadata or {}
    metadata_title = str(getattr(metadata, "title", "") or "").strip()
    metadata_author = str(getattr(metadata, "author", "") or "").strip()
    metadata_year = extract_year(str(metadata))

    return ExtractedPdf(
        page_count=len(page_texts),
        page_texts=page_texts,
        metadata_title=metadata_title,
        metadata_author=metadata_author,
        metadata_year=metadata_year,
        sha256=sha256_file(path),
        size_bytes=path.stat().st_size,
    )


def clean_text(value: str) -> str:
    value = value.replace("\x00", " ")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def extract_year(value: str) -> int:
    match = re.search(r"\b(19|20)\d{2}\b", value)
    return int(match.group(0)) if match else 0


def format_file_size(size_bytes: int) -> str:
    value = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"
