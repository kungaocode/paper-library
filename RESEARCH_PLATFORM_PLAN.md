# 自动化科研平台（Research Studio）计划书

> 目标读者：项目所有者。本文件是 `project-development-workflow` 阶段 1 的产物，记录事实、方案、验收命令与风险。
> 状态：已评审，进入实现。所有"现状事实"均来自 2026-10-15 对 `/home/kun/Desktop/paper` 的实际检测。

## 1. 目标与非目标

### 目标

把"论文自助阅读平台"升级为"自动化科研平台"，新增一条独立于阅读平台的研究生产线：

1. 语料层：把已有 67 篇论文（含中文核心论点 / 创新点）转成结构化"证据卡片"。
2. 向量知识库：对证据卡片切片、嵌入、建索引，支持混合检索（关键词 + 向量）。
3. 创新点整合：调用强模型跨论文整合创新点，产出可追溯的新想法（每条想法必须引用来源论文）。
4. 方向演化：想法经批判、评分、聚类，演化为研究方向，并支持多代迭代。
5. 科研闭环：方向 -> 实验方案 -> "待补论文清单" -> 回流到阅读平台导入 -> 新语料 -> 新方向。

### 非目标（本轮明确不做）

- 不修改阅读平台的任何代码、数据库、PDF、`KNOWLEDGE_BASE.md`、`.env`。
- 不调用真实模型 API（`LLM_PROVIDER=mock` 跑通全链路；真实模型留空占位，由用户接通）。
- 不重写向量库。`/home/kun/Desktop/vector_library`（`knowledge_vector`）由用户持续推进，本平台只留适配器接口，缺席时自动降级到内置后端。
- 不做分布式 / 队列 / 多用户；单机单用户本地优先。

## 2. 现状事实（实测）

| 项 | 事实 | 证据 |
| --- | --- | --- |
| 阅读平台后端 | FastAPI，`apps/api/app/`，2006 行；17 个测试全绿 | `cd apps/api && .venv/bin/python -m pytest -q` -> `17 passed` |
| 论文库 | SQLite `storage/api/library.sqlite3`，67 篇，12 个分类 | 只读连接查询 `select count(*) from papers` -> 67 |
| 结构化字段填充率 | `thesis_zh` 66/67、`novelty_zh` 67/67、`thesis_en`/`novelty_en` 67/67；`problem`/`method`/`findings`/`innovations`/`limitations` 全为 0；`abstract` 0、`tags` 0 | 只读遍历 `summary_json` 统计 |
| 原因 | 67 篇 `source='migration'`，由 `legacy_import.py` 从 `KNOWLEDGE_BASE.md` 解析，该文件只有 4 个双语论点/创新点字段 | `legacy_import.py` 的 `ZH_THESIS_RE` 等 4 条正则 |
| 结论 | 创新点数据不能直接复用，需要一条"深度解析"回填链路（读 PDF -> 复用现有 analyze 提示词 -> 存入研究库） | `pdf_utils.extract_pdf` + `pipeline.analyze` 可直接复用 |
| PDF 正文 | 67 个 PDF 共 157 MB，路径在 `papers.file_path`，全部存在 | `du -sh completed` / `find completed -name '*.pdf' \| wc -l` -> 67 |
| SQLite 能力 | Python 3.13.13 + SQLite 3.51.2；FTS5、`tokenize='trigram'`、`unicode61` 均可用 | 内存库建表实测通过 |
| 只读保护 | `mode=ro` 连接读 67 行成功，写入被 `OperationalError: attempt to write a readonly database` 拒绝 | 实测 |
| 向量库项目 | `knowledge_vector` v0.1.0，`IngestionPipeline` / `SearchEngine` / `SearchResult` 已具备；依赖 numpy | `/home/kun/Desktop/vector_library/src` |
| 研究 API 依赖缺口 | `apps/api/.venv` 没有 numpy；系统 python3.10 有 numpy 2.5.1 但没有 fastapi | `import numpy` 实测 |
| 模型配置 | `apps/api/.env` 有真实 `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY`（属阅读平台，本轮不读取、不复用、不改动） | 仅读变量名，值未回显 |
| 端口 | 3000（web）/ 8000（api）为阅读平台；3100 / 8100 空闲 | `ss -ltn` |
| 磁盘 | 94 GB 可用 | `df -h /home/kun` |
| Git | `.git` 为空目录，非有效仓库；用文件校验和做回归基线 | `git status` 失败 |
| 基线快照 | 146 个受保护文件的 md5 已存 `/tmp/paper_baseline/protected.md5` | 收尾阶段逐字节比对 |

## 3. 隔离设计（最重要的约束）

用户正在使用阅读平台，隔离必须可验证，不能只靠"我没改"。

| 维度 | 阅读平台 | 研究平台（新增） |
| --- | --- | --- |
| 目录 | `apps/api`、`apps/web` | `apps/research-api`、`apps/research-web` |
| 端口 | 8000 / 3000 | 8100 / 3100 |
| 数据库 | `storage/api/library.sqlite3`（读写） | `storage/research/research.sqlite3`（读写）；对论文库只读（`mode=ro`） |
| 环境变量 | `apps/api/.env` | `apps/research-api/.env`（独立文件，模型字段留空） |
| Python 环境 | `apps/api/.venv` | `apps/research-api/.venv`（独立） |
| 代码引用 | 无 | 只 `import` 阅读平台的纯函数模块（`pdf_utils`、`categories`、`legacy_import` 的解析器），不导入 `main`/`pipeline` 的副作用部分，不写回 |
| 产物 | `completed/`、`KNOWLEDGE_BASE.md`、`translete/` | 只写 `storage/research/`，不触碰任何论文目录 |
| 验证 | 17 个测试 | 收尾时重跑阅读平台测试 + 比对 146 个 md5 |

只读访问用 URI `file:...?mode=ro` 打开，SQLite 层面拒绝写入；即使代码有 bug 也污染不了论文库。

## 4. 阶段拆解

### 阶段 A：环境与脚手架

| 字段 | 内容 |
| --- | --- |
| 阶段目标 | 独立 venv + FastAPI 骨架在 8100 起来，`/health` 返回 ok，阅读平台测试仍全绿 |
| 前置条件 | Python 3.13、pip 可用（已实测 pypi 200） |
| 方案 | `apps/research-api/`：`requirements.txt`（fastapi/uvicorn/httpx/pydantic/dotenv/pypdf + numpy）、`.env.example`（模型字段留空）、`app/config.py`（独立 Settings，`paper_db_path` 只读、`storage_dir=storage/research`） |
| 工具 | `python3 -m venv .venv`、`pip install -r requirements.txt`、`uvicorn app.main:app --port 8100` |
| 验收 | `curl :8100/health` -> `{"status":"ok"}`；`cd apps/api && pytest -q` -> 17 passed |
| 风险 / 回退 | numpy 装不上 -> 内置向量后端改为纯 Python 余弦（无 numpy 依赖）；整体回退只需删除 `apps/research-*` 与 `storage/research/` |

### 阶段 B：语料层 + 只读适配器

| 字段 | 内容 |
| --- | --- |
| 阶段目标 | 从论文库只读拉取 67 篇，生成结构化证据卡片，缺字段可检测 |
| 方案 | `app/corpus.py`：`PaperLibraryReader`（只读连接）-> `EvidenceCard`（paper_id/title/title_zh/category/thesis_zh/novelty_zh/thesis_en/novelty_en/problem/method/innovations/limitations/pdf_path/page_count）；`app/store.py` 建 `corpus_papers` 表并记录 `fingerprint`（内容哈希）用于增量 |
| 验收 | 单元测试：67 张卡片、卡片含分类中文名、`innovations` 为空的论文被标记 `needs_deep_analysis=True` |
| 风险 / 回退 | 论文库 schema 变更 -> 用 `PRAGMA table_info` 做能力探测，缺列降级为空串而不是崩溃 |

### 阶段 C：向量知识库（可插拔后端）

| 字段 | 内容 |
| --- | --- |
| 阶段目标 | 卡片切片入库，混合检索可用；`knowledge_vector` 缺席时自动降级，存在时可切换 |
| 方案 | `app/retrieval.py`：`Retriever` 协议 + `SqliteHybridRetriever`（内置：FTS5 trigram 词法分 + 确定性哈希向量 `hashing-v1` 余弦分 + 归一化融合，权重可配）+ `KnowledgeVectorRetriever`（适配器：`import knowledge_vector` 成功且配了 `KNOWLEDGE_VECTOR_ROOT` 才启用，委托 `IngestionPipeline.ingest` / `SearchEngine.search`） |
| 切片单元 | `paper.thesis`、`paper.novelty`、`paper.innovation[i]`、`paper.method`、`paper.limitation[i]`、`category.positioning`（来自 `KNOWLEDGE_BASE.md` 的"主题定位"，给分类级语境） |
| 验收 | 检索"微调导致安全退化"能召回 cat-01/cat-02 卡片；`mode=lexical`/`vector`/`hybrid` 三种模式均返回结果；适配器在依赖缺失时报可读错误而不是崩溃 |
| 风险 / 回退 | 哈希向量语义弱 -> 明确标注为"占位嵌入"，真实语义嵌入由 `knowledge_vector` 接管；回退为纯词法检索 |

### 阶段 D：创新点深度提取（回填）

| 字段 | 内容 |
| --- | --- |
| 阶段目标 | 对缺 `innovations` 的论文，读 PDF 正文，复用阅读平台的 analyze 提示词，把结果写进研究库 |
| 方案 | `app/analysis.py`：复用 `pdf_utils.extract_pdf`（`[PAGE n]` 页码标记）+ 与 `pipeline.analyze` 同构的提示词与 `normalize_analysis` 校验（页码必须在 `1..page_count`，创新点必须带引文）；结果存 `deep_analyses` 表，不回写论文库 |
| 并发/成本控制 | `RESEARCH_ANALYSIS_CONCURRENCY`（默认 2）、`RESEARCH_ANALYSIS_PAGE_LIMIT`（默认 45）、按 `paper_id+sha256+prompt_version` 幂等跳过 |
| 验收 | mock provider 下跑 3 篇，`deep_analyses` 有 3 行、`innovations` 非空、页码合法；重复运行 0 次新调用（幂等） |
| 风险 / 回退 | 真实模型成本高（67 篇 x 长上下文）-> 提供 `limit`/`category` 过滤与预算估算端点，先小批量试跑；PDF 无文本层 -> 标记 `failed` 并跳过，不中断批次 |

### 阶段 E：创新整合 -> 新想法

| 字段 | 内容 |
| --- | --- |
| 阶段目标 | 跨论文整合创新点，产出带引用、可追溯的想法 |
| 方案 | `app/synthesis.py`：按分类分组 + 对每篇用混合检索找跨分类近邻 -> 组装"证据包" -> 强模型产出 `Idea`（title/hypothesis/motivation/method_sketch/expected_contribution/novelty_claim/risks/required_resources/source_paper_ids/evidence_refs/confidence）；强约束：`source_paper_ids` 必须非空且全部存在于语料，否则丢弃并记 `rejected_reason` |
| 验收 | mock 下产出想法，每条 `source_paper_ids` 可解析回真实论文标题；伪造引用被拒；`idea_index` 里可检索到想法本身 |
| 风险 / 回退 | 模型幻觉引用 -> 后置校验器逐条核对 paper_id 与关键论断；想法质量差 -> 保留 `critique` 分数供人工筛 |

### 阶段 F：批判、评分、去重、方向演化

| 字段 | 内容 |
| --- | --- |
| 阶段目标 | 想法经二次模型批判后聚类成研究方向，支持多代演化 |
| 方案 | 第二次模型调用产出 `Critique`（novelty/feasibility/evidence_support/risk/verdict/unsupported_claims/suggested_fix）；按想法文本向量余弦去重（阈值可配）；聚类成 `Direction`（name/question/rationale/gap_analysis/member_idea_ids/roadmap/success_metrics/generation/parent_direction_id） |
| 演化 | `generation=N+1` 的输入 = 第 N 代方向 + 本轮新检索到的语料 + 用户反馈；`parent_direction_id` 形成谱系树，可看方向如何分裂/合并/淘汰 |
| 验收 | mock 下产出至少 1 个方向、成员想法可追溯、`generation` 与 `parent_direction_id` 正确；重复想法被合并 |
| 风险 / 回退 | 聚类靠模型不稳 -> 同时落一份确定性分组（按分类 + 想法向量）作为兜底 |

### 阶段 G：科研闭环（实验方案 + 回流）

| 字段 | 内容 |
| --- | --- |
| 阶段目标 | 方向可落地为实验方案，并产出"待补论文/待办"清单回流阅读平台 |
| 方案 | `ExperimentPlan`（objective/hypothesis/datasets/baselines/metrics/protocol_steps/ablations/compute_estimate/falsification_criteria/timeline/risks）；`FollowupItem`（kind: paper_to_read/dataset/tool/experiment, query, reason, suggested_action）；`kind=paper_to_read` 的条目可一键复制检索式，交给阅读平台的 URL 导入（不自动写入，由用户在自己的平台点确认） |
| 闭环 | 实验结果由用户登记 `ExperimentResult`（status/metrics/notes）-> 更新方向置信度 -> 下一代演化读取该反馈 |
| 验收 | mock 下方向 -> 实验方案 -> 待补清单三件套齐全；闭环第二轮 generation 递增且引用了上一轮反馈 |
| 风险 / 回退 | 自动回流可能污染阅读平台 -> 设计上只产出建议，写入动作留给用户在阅读平台完成 |

### 阶段 H：API + 前端 + 验证

| 字段 | 内容 |
| --- | --- |
| 阶段目标 | 研究平台有独立 Web 界面，全链路可在浏览器跑通并截图验证 |
| 方案 | `apps/research-api/app/main.py` 路由：`/health`、`/api/research/status`、`POST /api/research/corpus/sync`、`POST /api/research/index/rebuild`、`GET /api/research/search`、`POST /api/research/analyze`、`POST /api/research/ideate`（触发 E->F->G 全链）、`GET /api/research/ideas`、`/directions`、`/experiments`、`/followups`、`/api/research/jobs`；`apps/research-web`（Next.js 15 + React 19，沿用阅读平台的 tailwind 色板与组件风格，端口 3100） |
| 验收 | 端到端：sync -> index -> ideate(mock) -> 前端看到想法/方向/实验方案；`pytest` 全绿；浏览器截图确认非空、无重叠 |
| 风险 / 回退 | `npm install` 受代理限制 -> 已实测 `HTTPS_PROXY=http://127.0.0.1:7897 npm view next version` 返回 16.4.1，可用；若仍失败则前端降级为纯静态报告页并记为 blocked |

## 5. 端到端数据流

```text
阅读平台（只读，绝不写入）
  library.sqlite3  ┐
  completed/*.pdf  ┼──> [B 语料层] EvidenceCard x 67
  KNOWLEDGE_BASE.md┘              |
                                  v
   [C 向量知识库] 切片 -> FTS5 + 向量 -> 混合检索
        ^                       |
        | knowledge_vector 适配器（用户后续接入）
        |                       v
   [D 深度提取] PDF -> analyze -> innovations（写研究库）
                                  |
                                  v
            [E 创新整合] 证据包 -> 强模型 -> Idea（强制引用校验）
                                  |
                                  v
            [F 批判/去重/聚类] -> Direction（多代演化谱系）
                                  |
                                  v
            [G 闭环] ExperimentPlan + FollowupItem
                                  |
                                  v
      "待补论文"建议 ->（用户手动）-> 阅读平台 URL 导入 -> 新语料 -> 下一代
```

## 6. 假设与待确认

1. 假设：研究平台与阅读平台同仓不同目录（`apps/research-*`）即满足"分离"。若要求物理独立仓库，迁移成本为一次目录移动（无跨目录写依赖）。
2. 假设：本轮用 mock provider 跑通链路，真实强模型由用户填 `RESEARCH_LLM_*` 后自行试跑。
3. 待确认：深度提取默认对全部 67 篇还是先跑一个分类（成本敏感，默认 `limit` 可配）。
4. 待确认：`knowledge_vector` 接入时机。适配器已就位，等用户提供稳定 API 后只需设 `KNOWLEDGE_VECTOR_ROOT` + `KNOWLEDGE_VECTOR_DB`。

## 7. 阶段检查点记录

| 阶段 | 状态 | 证据 | 未决 |
| --- | --- | --- | --- |
| 0 现状审阅 | pass | 17 passed；67 篇；字段填充率实测；FTS5/只读/端口/磁盘实测 | 无 |
| A 脚手架 | pass（离线） | `apps/research-api/.venv`（Python 3.13 + fastapi 0.143.2 + numpy）；`.env.example` 模型字段留空、`RESEARCH_LLM_PROVIDER=mock`；`pytest.ini`；222 项测试可收集 | 未常驻 8100（本轮按要求只跑测试，不起服务） |
| B 语料层 | pass（离线） | `tests/test_corpus_isolation.py`：只读 URI 拉卡片、`fingerprint` 增量、写论文库被 SQLite 拒绝、schema 缺列降级；`test_api.py`：sync 任务 `created=3`、`GET /corpus/papers?category_id=` 过滤 | 真实 67 篇只在 09:51 手工冒烟过一次（`storage/research/research.sqlite3`），未纳入自动化测试 |
| C 向量库 | pass（内置后端） | `test_retrieval.py`/`test_chunking.py`：FTS5 trigram 词法分 + `hashing-v1-384` 余弦 + 归一化融合；`mode=lexical/vector/hybrid` 三模式均返回；切片 kind 覆盖 `paper.*`、`category.positioning`、`idea.*` | `knowledge_vector` 适配器未接（按用户要求推迟）；哈希向量只是占位语义 |
| D 深度提取 | pass（mock） | `test_pipeline_e2e.py::test_deep_analysis_caches_and_force_recomputes`：3 篇 `analyzed=3/failed=0`、二次运行 `cached=3`、`force` 重算；并发 2 下整批不再失败（`app/interop.py` 加锁回归） | 真实模型未接（提示词与页码校验已就位，成本估算端点已可用） |
| E 想法生成 | pass（mock） | `test_synthesis.py`/`test_api.py`：引用门禁生效——伪造 `paper_id` 被拒，通过的想法均引用 >=2 篇真实论文 + 真实 `chunk_id`；`idea.claim` 切片可被检索 | 同上 |
| F 方向演化 | pass（mock） | 1 个方向、`member_idea_ids` 可追溯、`generation` 递增；第 2 代 2/2 判为"与已有想法重复，已合并到 idea-…"（去重阈值 0.92） | 聚类仍依赖模型输出，兜底分组已有但未用真实模型验证 |
| G 科研闭环 | pass（mock） | 方向 -> 1 份实验方案（datasets/baselines/metrics/ablations/falsification_criteria 齐全）-> 3 条待办（含 `paper_to_read` 回流建议）；`PATCH /followups/{id}/status` 可流转 | 回流仍是"只给建议"，写入动作留给用户在阅读平台完成（设计如此） |
| H API | pass（离线） | `tests/test_api.py` 57 项：全路由、202 + 后台任务落地、409/404/422/503 分支、CORS 预检、重启中断任务恢复、`_translate_failure` 映射、全链路后论文库逐字节未变 | 前端 `apps/research-web` 未创建（本轮范围是"把测试跑通"） |

## 8. 本轮验证记录（2026-10-15，离线）

命令与结果（均为实测）：

```bash
cd /home/kun/Desktop/paper/apps/research-api && .venv/bin/python -m pytest -q   # 222 passed
cd /home/kun/Desktop/paper/apps/api && .venv/bin/python -m pytest -q            # 17 passed（阅读平台回归）
cd /home/kun/Desktop/paper && md5sum -c /tmp/paper_baseline/protected.md5       # 145 OK
```

md5 基线说明：145 个文件逐字节一致；剩余 2 项 `storage/api/library.sqlite3-shm` / `-wal`
报 `FAILED open or read`，原因是这两个 SQLite 边车文件在服务干净关闭后被删除（基线里
`-wal` 的 md5 就是空文件的 `d41d8cd9...`），不是内容变化。主库 `storage/api/library.sqlite3`
为 `OK`（md5 `c033c87cd3bd72bb22e7e14b9c2d0d17`，mtime 仍是 2026-10-13 09:36），阅读平台数据未被触碰。

本轮修复的缺陷：

1. `app/provider.py`：mock 想法不带 `evidence_refs`，导致引用门禁把本应通过的想法全部拒掉（现从提示词里回读 `chunk_id=`）。
2. `app/synthesis.py`：`diversify_by_paper` 的桶键对生成内容失效，想法/方向切片会挤掉论文证据（现回退到 `kind` 前缀分桶）。
3. `app/pipeline.py::run_ideation`：去重被引用门禁短路，第 2 代不再报"已探索过"（现结构性失败之外的想法一律先去重）。
4. `app/pipeline.py::analysis_estimate` + `app/main.py`：`force=true` 时任务预告"计划处理 0 篇论文"却仍会真实调用模型（估算只数 pending）。现在 force 按范围内论文计数，`GET /api/research/estimate-analysis` 新增 `force` 查询参数、响应新增 `force` 字段。

已实测 / 未验证：

- 已实测（离线 mock）：语料同步 -> 索引 -> 深度解析 -> 想法 -> 方向 -> 实验方案 -> 待办 -> 第 2 代去重；222 项单元 + 端到端 + HTTP 测试；隔离（只读连接、临时目录、md5 基线）。
- 未验证：真实强模型 API（按要求不接）、`knowledge_vector` 真实向量库（按要求不接）、`apps/research-web` 前端（未创建）、8100/3100 常驻服务与浏览器验收（未启动，避免影响正在使用的阅读平台）。

## 9. 接入清单（等子项目推进后）

1. 真实强模型：在 `apps/research-api/.env` 填 `RESEARCH_LLM_PROVIDER=openai-compatible`、`RESEARCH_LLM_BASE_URL`、`RESEARCH_LLM_API_KEY`、`RESEARCH_LLM_MODEL`；先 `GET /api/research/estimate-analysis?limit=3` 看预算，再 `POST /api/research/analyze {"limit":1,"category_id":"cat-01"}` 小批量试跑，确认无误后放开 `limit`。密钥只留在服务端。
2. 真实向量库：设 `RESEARCH_RETRIEVAL_BACKEND=knowledge_vector` + `KNOWLEDGE_VECTOR_ROOT` + `KNOWLEDGE_VECTOR_DB`。依赖或路径缺失时自动降级到内置后端，`/health` 的 `notice` 与 `/api/research/status` 的 `knowledge_vector_available` 会说明当前用的是哪一个。
3. 起服务：`cd apps/research-api && .venv/bin/uvicorn app.main:app --port 8100`（与阅读平台的 8000 完全隔离）。
