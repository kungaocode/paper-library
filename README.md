# 论文文库 / Paper Library

大模型安全方向的个人论文库。**唯一索引文件是 [KNOWLEDGE_BASE.md](KNOWLEDGE_BASE.md)**，每篇论文在其中有一条中英双语记录（核心论点 + 创新点 + PDF 链接）。

## 目录约定

```
paper/
├── KNOWLEDGE_BASE.md      # 主索引：67 篇论文的双语总结，按 12 个主题分组
├── README.md              # 本文件：目录契约与工作流
├── completed/             # 已整理：PDF 已按论文真实标题重命名，并归入主题子目录
│   ├── 01_微调安全_机理与测量/        (3)
│   ├── 02_微调安全_防御方法/          (5)
│   ├── 03_越狱攻击与防御/             (7)
│   ├── 04_智能体安全与提示注入/        (3)
│   ├── 05_评测基准与工具/             (5)
│   ├── 06_对齐_数据与偏好优化/         (10)
│   ├── 07_参数高效微调/               (3)
│   ├── 08_推理与思维链/               (10)
│   ├── 09_规划与LLM-Modulo/           (6)
│   ├── 10_智能体与工具使用/            (8)
│   ├── 11_检索增强生成/               (4)
│   └── 12_安全范式与综述/              (3)
├── need_organization/     # 收件箱：新下载的 PDF 一律先放这里
├── _archive/
│   ├── duplicates/        # 与 completed 内容完全相同的副本（未删除，便于回退）
│   └── versions/          # 同一论文的旧版本 / 审稿版
├── _templates/
│   └── PAPER_TEMPLATE.md  # 新增条目的空白双语模板
└── _work/                 # rename_manifest.json：原始文件名 → 现路径的对照表；build_manifest.py
```

## 工作流

1. **下载**：把新论文直接丢进 `need_organization/`，不用重命名、不用建子目录。
2. **整理**：让 Codex「整理 need_organization」，它会执行：
   - 读取 PDF 确认真实标题，用标题重命名文件；
   - 判断归属主题，必要时新建 `completed/13_xxx/`；
   - 按 `_templates/PAPER_TEMPLATE.md` 写双语条目，插入 `KNOWLEDGE_BASE.md` 对应分组；
   - 与已有标题查重：完全重复进 `_archive/duplicates/`，旧版本或审稿版进 `_archive/versions/`；
   - 更新 `KNOWLEDGE_BASE.md` 顶部的论文总数与日期。
3. **扩充**：想扩展某个方向时直接说「按 <主题> 补充相关论文」，论文到位后重复第 2 步。

## 约定细节

- 条目排序：同一主题内按「机理/攻击 → 防御/方法 → 评测」排列，便于横向对比。
- PDF 链接：用绝对路径；文件名含空格时用 `<>` 包裹目标，例如 `[name.pdf](</home/kun/Desktop/paper/completed/01_x/name x.pdf>)`。
- 数字与结论：只写论文原文中出现过的数据，不从记忆里补。
- `_archive/` 只归档不删除，确认无误后可自行清理。
- `need_organization/` 里的文件不会被 `KNOWLEDGE_BASE.md` 收录，整理完成才进索引。

## 公开仓库说明

本仓库是公开版本，只包含平台代码与文档。以下内容已通过 `.gitignore` 排除，不在仓库中：

- 论文 PDF 文库（`completed/`、`_archive/`），版权归原作者所有；
- 本地运行时数据（`storage/` 下的 SQLite 数据库与质量门禁截图）；
- 密钥与本地配置（`api.txt`、`apps/api/.env`，可参考 `apps/api/.env.example`）；
- 依赖与构建产物（`node_modules/`、`.venv/`、`.next/`）。

因此 `KNOWLEDGE_BASE.md` 中的 PDF 链接指向本地绝对路径，在 GitHub 上无法直接打开，仅作索引与摘要参考。

## 平台代码

- `apps/web` — Next.js 前端
- `apps/api` — FastAPI 论文库 API
- `apps/research-api` — FastAPI 研究分析 API

许可证：[MIT](LICENSE)

