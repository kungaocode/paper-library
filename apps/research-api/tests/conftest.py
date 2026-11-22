"""Shared fixtures.

Every test runs against a throwaway paper repository: a synthetic reading
platform library is generated in a temp dir, so the real `storage/api/
library.sqlite3` (which the user is actively using) is never opened.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from app.chunking import stable_id
from app.config import ResearchSettings
from app.pipeline import ResearchPipeline
from app.provider import MockResearchProvider
from app.store import ResearchStore


PAPERS = [
    {
        "id": "paper-aaa111000000",
        "title": "Fine-Grained Alignment Makes Safety a Sparse Token Property",
        "title_zh": "细粒度对齐使安全性成为稀疏token属性",
        "authors": ["Wei Chen", "Lin Zhao"],
        "venue": "NeurIPS",
        "year": 2024,
        "category_id": "cat-01",
        "thesis_zh": "安全能力集中在少量关键 token 上，对其做锚定正则即可显著降低越狱成功率。",
        "novelty_zh": "提出 token 级安全置信度约束，训练开销低于全量对齐。",
        "summary": {
            "problem": "全量对齐训练代价高且损害通用能力。",
            "method": "在关键 token 上加入参考模型锚定正则项。",
            "findings": ["越狱成功率下降 41%", "通用基准损失小于 2%"],
            "innovations": [
                {
                    "claim": "把安全性建模为稀疏 token 属性",
                    "evidence_pages": [3],
                    "evidence_quotes": ["Safety concentrates on a few tokens."],
                }
            ],
            "limitations": ["依赖标注器质量"],
        },
    },
    {
        "id": "paper-bbb222000000",
        "title": "Indirect Prompt Injection Breaks Agent Tool Calls",
        "title_zh": "间接提示注入破坏智能体工具调用",
        "authors": ["Mira Patel"],
        "venue": "ACL",
        "year": 2024,
        "category_id": "cat-04",
        "thesis_zh": "注入通过数据通道进入智能体决策点，运行时检测只能部分缓解。",
        "novelty_zh": "构造多轮工具调用注入基准，量化决策点污染路径。",
        "summary": {
            "problem": "智能体把不可信数据当作指令执行。",
            "method": "多轮工具调用基准 + 决策点标注。",
            "findings": ["注入成功率在多轮场景升至 68%"],
            "innovations": [
                {
                    "claim": "把注入建模为决策点污染问题",
                    "evidence_pages": [5],
                    "evidence_quotes": ["Injection enters at decision points."],
                }
            ],
            "limitations": ["基准规模有限"],
        },
    },
    {
        "id": "paper-ccc333000000",
        "title": "Loss Landscape Geometry Predicts Jailbreak Transferability",
        "title_zh": "损失景观几何可预测越狱迁移性",
        "authors": ["Jonas Weber"],
        "venue": "ICML",
        "year": 2023,
        "category_id": "cat-02",
        "thesis_zh": "对抗后缀能否跨模型迁移，取决于扰动是否越过安全盆地边界。",
        "novelty_zh": "提出盆地边界度量 VISAGE，把迁移性变成几何预测问题。",
        "summary": {
            "problem": "越狱迁移性缺乏可计算判据。",
            "method": "估计安全盆地边界并与迁移率拟合。",
            "findings": ["几何距离与迁移率相关系数 0.71"],
            "innovations": [
                {
                    "claim": "盆地边界度量 VISAGE",
                    "evidence_pages": [4],
                    "evidence_quotes": ["Boundary distance predicts transfer."],
                }
            ],
            "limitations": ["边界估计成本高"],
        },
    },
]

KNOWLEDGE_BASE = """# 知识库

## 1. 模型安全微调

**主题定位**：聚焦训练期安全约束，研究如何在保持通用能力的前提下降低越狱成功率。

## 2. 安全评估与攻击

**主题定位**：聚焦攻击面与可迁移性，研究对抗样本如何跨模型扩散。

## 4. 智能体安全

**主题定位**：聚焦运行期安全，研究工具调用链中的不可信数据污染。
"""


def _write_library(root: Path) -> Path:
    """Create a minimal reading-platform library.sqlite3 (same columns we read)."""
    db_path = root / "storage" / "api" / "library.sqlite3"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE papers (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                title_zh TEXT NOT NULL DEFAULT '',
                authors_json TEXT NOT NULL DEFAULT '[]',
                venue TEXT NOT NULL DEFAULT '',
                year INTEGER NOT NULL DEFAULT 0,
                category_id TEXT NOT NULL DEFAULT '',
                page_count INTEGER NOT NULL DEFAULT 0,
                sha256 TEXT NOT NULL DEFAULT '',
                file_path TEXT NOT NULL DEFAULT '',
                summary_json TEXT NOT NULL DEFAULT '{}'
            )
            """
        )
        for paper in PAPERS:
            summary = dict(paper["summary"])
            # Mirror the real library: the Chinese thesis/novelty live inside
            # summary_json, not in their own columns.
            summary["thesis_zh"] = paper["thesis_zh"]
            summary["novelty_zh"] = paper["novelty_zh"]
            connection.execute(
                "INSERT INTO papers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    paper["id"],
                    paper["title"],
                    paper["title_zh"],
                    json.dumps(paper["authors"], ensure_ascii=False),
                    paper["venue"],
                    paper["year"],
                    paper["category_id"],
                    12,
                    stable_id(paper["id"], "sha256"),
                    f"papers/{paper['id']}.pdf",
                    json.dumps(summary, ensure_ascii=False),
                ),
            )
        connection.commit()
    finally:
        connection.close()
    return db_path


def minimal_pdf(page_texts: list[str]) -> bytes:
    """Build a small, valid, uncompressed PDF (no external generator needed)."""
    # Objects 1-3 are reserved for catalog / pages / font; content and page
    # objects are appended after them.
    objects: list[bytes] = [b"<< >>", b"<< >>", b"<< >>"]
    page_object_numbers: list[int] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)  # 1-based object number

    for text in page_texts:
        safe = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
        stream = f"BT /F1 12 Tf 50 750 Td ({safe}) Tj ET".encode("latin-1", "replace")
        contents_number = add(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
        page_number = add(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents "
            + str(contents_number).encode()
            + b" 0 R >>"
        )
        page_object_numbers.append(page_number)

    kids = b" ".join(str(n).encode() + b" 0 R" for n in page_object_numbers)
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[1] = (
        b"<< /Type /Pages /Kids [" + kids + b"] /Count "
        + str(len(page_object_numbers)).encode() + b" >>"
    )
    objects[2] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(index).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_offset = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size " + str(len(objects) + 1).encode() +
        b" /Root 1 0 R >>\nstartxref\n" + str(xref_offset).encode() + b"\n%%EOF\n"
    )
    return bytes(out)


def _write_pdfs(root: Path) -> None:
    """Generate tiny but genuinely parseable PDFs for the deep-analysis stage."""
    pdf_dir = root / "papers"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    for paper in PAPERS:
        pages = [
            f"{paper['title']} page 1. Evidence sentence for the innovation claim.",
            "Method section page 2: we constrain key decision tokens.",
            "Results page 3: attack success rate drops while utility holds.",
        ]
        text = minimal_pdf(pages)
        (pdf_dir / f"{paper['id']}.pdf").write_bytes(text)


@pytest.fixture(scope="session")
def tmp_paper_root(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("paper-repo")
    _write_library(root)
    _write_pdfs(root)
    (root / "KNOWLEDGE_BASE.md").write_text(KNOWLEDGE_BASE, encoding="utf-8")
    # The research service reuses two *pure* modules from the reading platform
    # (categories, pdf_utils). Link the real package so tests exercise the same
    # code path; nothing is written through it.
    real_api = Path(__file__).resolve().parents[2] / "api"
    if real_api.is_dir():
        (root / "apps").mkdir(exist_ok=True)
        link = root / "apps" / "api"
        if not link.exists():
            link.symlink_to(real_api, target_is_directory=True)
    return root


def make_settings(root: Path, workdir: Path) -> ResearchSettings:
    return ResearchSettings(
        paper_root=root,
        storage_dir=workdir,
        llm_provider="mock",
        llm_base_url="",
        llm_api_key="",
        llm_model="",
        llm_timeout_seconds=5,
        llm_max_output_tokens=2000,
        llm_json_mode=True,
        analysis_concurrency=2,
        analysis_page_limit=6,
        analysis_max_chars=20000,
        retrieval_top_k=6,
        retrieval_candidate_k=20,
        lexical_weight=0.45,
        dedupe_threshold=0.92,
        knowledge_vector_root="",
        knowledge_vector_db="",
        retrieval_backend="builtin",
        cors_origins=("http://localhost:3100",),
    )


@pytest.fixture()
def settings(tmp_paper_root: Path, tmp_path: Path) -> ResearchSettings:
    return make_settings(tmp_paper_root, tmp_path / "research")


@pytest.fixture()
def store(settings: ResearchSettings) -> ResearchStore:
    settings.ensure_directories()
    return ResearchStore(settings.database_path)


@pytest.fixture()
def pipeline(settings: ResearchSettings) -> ResearchPipeline:
    return ResearchPipeline(settings=settings, provider=MockResearchProvider())


@pytest.fixture()
def synced_pipeline(pipeline: ResearchPipeline) -> ResearchPipeline:
    pipeline.sync_corpus()
    pipeline.rebuild_index()
    return pipeline
