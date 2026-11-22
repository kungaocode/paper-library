# 前端质量门禁人工验收清单

日期：2026-10-13

本文件用于接手完成 `frontend-quality-gate` 中尚未完成的人工网页验收。自动化构建、类型检查和后端流程测试已经执行过；本文件主要覆盖真实模型、浏览器交互、响应式布局、下载链路和视觉证据。

## 当前状态

已经通过：

- `apps/web` 执行 `npm run typecheck`。
- `apps/web` 执行 `npm run build`，Next.js 页面构建成功。
- 后端测试：

```bash
cd /home/kun/Desktop/paper/apps/api
timeout 240s .venv/bin/python -m pytest \
  tests/test_auth_and_cors.py \
  tests/test_import_pipeline.py \
  tests/test_http_client.py \
  -q -p no:cacheprovider
```

当前结果：`12 passed, 1 warning`。

已经用 mock provider 验证：

- PDF 上传接口会先写入 `need_organization/`。
- 后台任务会提取 PDF 文本、执行分类和结构化解读。
- 成功任务最终写入 `completed/<分类>/`、`KNOWLEDGE_BASE.md` 和 SQLite。
- 任务结果中的 `result.phase` 最终为 `completed`，并包含 `classification` 和 `analysis`。
- `GET /api/papers/<paper_id>/file` 能返回 PDF。

尚未验证：

- 真实 OpenAI 兼容模型调用；2026-10-13 已到达上游，但当前 Key 返回 `401 invalid_api_key`。
- 真实公开论文链接的外部网络下载。
- Chrome、Firefox、Safari 等实际浏览器中的交互、响应式布局和视觉结果。
- 移动视口、键盘操作、焦点顺序和触控目标。
- 认证开启后的浏览器登录流程。

## 真实 API 连接记录

日期：2026-10-13

已确认：

- `api.txt` 第一行与 `apps/api/.env` 中的 `LLM_API_KEY` 完全一致；比较使用长度和 SHA-256 摘要完成，未输出完整密钥。
- 当前 Key 长度为 116，前后没有空白、换行或外层引号；格式检查不会输出密钥正文。
- `LLM_BASE_URL=https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`。
- `LLM_MODEL=qwen3.8-flash`。
- 请求通过当前 HTTPS 代理到达阿里云端点，响应服务头为 `server: istio-envoy`。
- 携带同一个 Key 请求以下三个兼容端点的 `/models` 均返回 HTTP `401` 和 `invalid_api_key`：
  - `https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`
  - `https://dashscope.aliyuncs.com/compatible-mode/v1`
  - `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`
- 示例请求 ID：`5848ad6c-d07f-44d4-b9f1-bc2e60626b70`、`f78e0af9-72ca-43a4-9770-25e2b402dd29`、`70c58135-a83e-9354-8cc4-226616078a75`。
- 项目连接诊断接口稳定返回 `ok: false`，并保留上游错误：

```json
{
  "ok": false,
  "message": "模型接口返回 401: invalid_api_key: Invalid API-key provided.",
  "latency_ms": 208,
  "provider": "openai-compatible",
  "model": "qwen3.8-flash"
}
```

当前结论：

- 网络、TLS、代理、Base URL、OpenAI 兼容请求格式和后端模型客户端均已验证可达。
- 当前阻塞不在项目读取、请求实现、域名选择或模型名；阿里云在鉴权阶段即拒绝请求，尚未进入模型校验。
- 需要替换为适用于该模型服务入口的有效 Key。无效 Key 无法通过修改项目代码解决。

连接诊断接口：

```bash
curl -sS -X POST http://127.0.0.1:8000/api/settings/models/test
```

成功时应返回 `ok: true` 和正整数 `latency_ms`。鉴权失败时仍返回 HTTP `200`，但 `ok` 为 `false`，`message` 保留经过截断的上游错误，便于前端直接展示。

更换 Key 后的复验顺序：

1. 只更新 `apps/api/.env` 中的 `LLM_API_KEY=<有效密钥>`；不要在命令输出、截图或文档中粘贴密钥正文。
2. 重启 API，使新的环境变量生效。
3. 调用上方连接诊断接口，确认返回 `ok: true`。
4. 再使用真实论文链接执行 FQ-04，确认模型分类、结构化解读、PDF 归档和网页同步全部成功。

若需要单独确认上游鉴权，可加载环境变量后只读请求模型列表；命令不会回显 Key：

```bash
cd /home/kun/Desktop/paper/apps/api
set -a
. .env
set +a
curl -sS -w '\nHTTP %{http_code}\n' \
  -H "Authorization: Bearer ${LLM_API_KEY}" \
  "${LLM_BASE_URL}/models"
```

## 测试前准备

### 1. 配置真实模型

不要提交或输出真实 API Key。复制示例文件后只在本地填写：

```bash
cd /home/kun/Desktop/paper/apps/api
cp .env.example .env
```

`apps/api/.env` 至少需要：

```dotenv
PAPER_ROOT=/home/kun/Desktop/paper
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=<你的 OpenAI 兼容接口地址>
LLM_API_KEY=<你的密钥>
LLM_MODEL=<你的模型 ID>
LLM_TIMEOUT_SECONDS=900
LLM_MAX_OUTPUT_TOKENS=6000
LLM_JSON_MODE=true
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
AUTH_PASSWORD=
ALLOW_PRIVATE_URLS=false
```

说明：

- `AUTH_PASSWORD` 留空时，API 不启用登录。
- 如果要验证登录，再填写 `AUTH_USERNAME`、`AUTH_PASSWORD` 和随机 `AUTH_SESSION_SECRET`。
- `PAPER_STORAGE_DIR` 是数据库目录变量；不要在测试命令中误写成 `STORAGE_DIR`。
- 若只验证网页和流水线，不验证真实模型质量，可以临时使用：

```dotenv
LLM_PROVIDER=mock
LLM_MODEL=mock-structured-v1
```

### 2. 启动 API

打开一个终端：

```bash
cd /home/kun/Desktop/paper/apps/api
.venv/bin/uvicorn app.main:app \
  --host 127.0.0.1 \
  --port 8000 \
  --log-level warning
```

检查：

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/api/settings/models
curl -sS 'http://127.0.0.1:8000/api/papers?limit=500'
curl -sS http://127.0.0.1:8000/api/categories
```

预期：

- `/health` 返回 `{"status":"ok"}`。
- `/api/settings/models` 返回 `configured: true`，且 `provider`、`model` 与 `.env` 一致。
- `/api/papers?limit=500` 返回当前数据库中的真实论文，不应再出现静态 mock 数量或假统计。
- `/api/categories` 返回 12 个分类。

### 3. 启动网页

打开第二个终端：

```bash
cd /home/kun/Desktop/paper/apps/web
npm run dev
```

默认地址：

```text
http://localhost:3000
```

如果 API 不在 `http://localhost:8000`，启动网页前设置：

```bash
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000 npm run dev
```

生产构建验证：

```bash
cd /home/kun/Desktop/paper/apps/web
npm run typecheck
npm run build
```

注意：`next dev` 和 `next build` 会共用 `apps/web/.next`。不要在同一个开发服务运行时并行执行 `npm run build`；如果已经执行过，先停止 `npm run dev`，再重新启动开发服务，避免出现类似 `Cannot find module './571.js'` 的陈旧缓存错误。

重启后可用以下命令逐页确认路由不是依赖偶然重编译：

```bash
for path in / /papers /inbox /settings; do
  code=$(curl -sS -o /dev/null -w '%{http_code}' "http://127.0.0.1:3000${path}")
  printf '%s %s\n' "$path" "$code"
done
```

预期四行均为 HTTP `200`。

## 浏览器矩阵

至少记录以下环境：

| 浏览器 | 版本 | 视口 | 结果 |
| --- | --- | --- | --- |
| Chrome 或 Chromium | 待填写 | 1440 x 900 | 待填写 |
| Chrome 或 Chromium | 待填写 | 390 x 844 | 待填写 |
| Firefox | 待填写 | 1440 x 900 | 待填写 |
| Firefox | 待填写 | 390 x 844 | 待填写 |

桌面检查：

- 页面无横向滚动条。
- 侧栏、主工作区、顶部状态不重叠。
- 当前导航项有明确选中状态。
- 中文标题、按钮文字和表格列不溢出容器。

移动检查：

- 导航可打开、关闭和切换页面。
- 搜索框、筛选器、上传按钮和任务表格可操作。
- 重要按钮的触控区域不小于约 40 x 40 CSS 像素。
- 表格允许横向滚动，或自动转换为可读的移动布局。

## 人工测试用例

### FQ-01 首页真实数据

步骤：

1. 打开 `http://localhost:3000/`。
2. 查看论文总数、待复核数、分类数和最近论文。
3. 与 `curl 'http://127.0.0.1:8000/api/papers?limit=500'` 和 `/api/categories` 的真实结果对照。
4. 点击最近论文，进入详情页。

预期：

- 数字来自 API 数据库，不是写死的演示统计。
- 没配置后端时显示错误或空状态，不显示假成功。
- 最近论文可打开，详情页显示真实标题、分类、摘要和总结字段。

证据：

- 首页截图：
- 详情页截图：

### FQ-02 论文浏览与搜索

步骤：

1. 打开 `/papers`。
2. 输入论文标题关键词。
3. 切换分类筛选和状态筛选。
4. 清空筛选，确认列表恢复。
5. 刷新页面，确认 URL 查询参数和筛选条件保持一致。

预期：

- 搜索命中真实论文。
- 无结果时显示明确的空状态。
- 筛选组合不会返回不匹配的论文。
- 页面刷新后状态不丢失。

证据：

- 搜索前截图：
- 搜索结果截图：
- 空状态截图：

### FQ-03 PDF 浏览和下载

步骤：

1. 打开一篇状态为 `ready` 的论文详情。
2. 点击“查看 PDF”或打开 PDF 链接。
3. 在浏览器中翻页。
4. 直接请求文件接口：

```bash
curl -I http://127.0.0.1:8000/api/papers/<paper_id>/file
```

预期：

- 返回 `200` 和 `Content-Type: application/pdf`。
- 浏览器能够内嵌打开或正常下载 PDF。
- 文件内容对应该论文，不是默认页或错误文件。
- 路径越权请求被拒绝。

证据：

- PDF 页面截图：
- 请求头输出：

### FQ-04 链接导入完整链路

准备一个可直接下载 PDF 的公开链接，优先使用 arXiv 的 `abs` 或 `pdf` 页面。不要在公开报告中填写 API Key。

步骤：

1. 打开 `/inbox`。
2. 确认模型状态显示为已配置。
3. 输入公开论文链接并提交。
4. 记录任务 ID。
5. 立即轮询任务：

```bash
curl -sS http://127.0.0.1:8000/api/jobs/<job_id>
```

6. 持续轮询到状态为 `succeeded` 或 `failed`。
7. 检查 `need_organization/` 是否出现临时 PDF。
8. 查询任务结果和论文详情：

```bash
curl -sS http://127.0.0.1:8000/api/jobs/<job_id>
curl -sS http://127.0.0.1:8000/api/papers/<paper_id>
curl -I http://127.0.0.1:8000/api/papers/<paper_id>/file
```

9. 检查 `completed/<分类>/` 和 `KNOWLEDGE_BASE.md`。

预期：

- 提交接口返回 `202` 和 `queued` 任务。
- 处理中阶段按顺序经过下载、提取、分类、分析和归档。
- 成功后 `status == "succeeded"`。
- `result.phase == "completed"`。
- `result.classification` 和 `result.analysis` 均存在。
- 前端任务队列显示分类、置信度、中文题名、核心论点或创新点。
- 新论文出现在 `/papers`。
- 正式 PDF 位于 `completed/<分类>/`。
- `KNOWLEDGE_BASE.md` 新增对应条目。

失败时记录：

- 目标链接：
- HTTP 状态：
- 任务错误信息：
- 是否发生重定向：
- 站点是否要求登录、Cookie 或验证码：

### FQ-05 本地上传完整链路

如果需要避免外部网络变量，先生成一个与库内文件哈希不同的测试 PDF：

```bash
cd /home/kun/Desktop/paper/apps/api
.venv/bin/python - <<'PY'
from pathlib import Path
from pypdf import PdfReader, PdfWriter

source = next(iter(sorted(Path("/home/kun/Desktop/paper/completed").rglob("*.pdf"))))
destination = Path("/home/kun/Desktop/paper/storage/quality-gate/upload.pdf")
destination.parent.mkdir(parents=True, exist_ok=True)

writer = PdfWriter()
for page in PdfReader(str(source)).pages:
    writer.add_page(page)
writer.add_blank_page(
    width=float(writer.pages[0].mediabox.width),
    height=float(writer.pages[0].mediabox.height),
)

with destination.open("wb") as handle:
    writer.write(handle)
print(destination)
PY
```

上传：

```bash
curl -sS -X POST http://127.0.0.1:8000/api/imports/file \
  -F 'file=@/home/kun/Desktop/paper/storage/quality-gate/upload.pdf;type=application/pdf'
```

预期与 FQ-04 相同。测试完成后自行删除 `storage/quality-gate/upload.pdf`，以及测试产生的论文和临时数据库记录。

注意：当前隔离烟测留下的文件位于 `storage/quality-gate/upload.pdf`。它不应作为正式论文保留。

### FQ-06 错误与边界状态

逐项验证：

| 场景 | 操作 | 预期 |
| --- | --- | --- |
| API 未启动 | 关闭 API 后打开 `/inbox` | 显示 API 未连接，提交按钮禁用 |
| 模型未配置 | 清空 `LLM_MODEL` 后重启 API | 显示模型未配置，导入按钮禁用 |
| 非 PDF 上传 | 上传 `.txt` 或伪造扩展名 | 返回错误，不创建成功任务 |
| 无文本 PDF | 上传扫描件 | 明确提示暂未启用 OCR，不伪造总结 |
| 非法 URL | 输入 `not-a-url` | 前端阻止提交或后端返回明确错误 |
| 私网 URL | 输入 `http://127.0.0.1:...` | 默认 SSRF 防护拒绝 |
| 超大文件 | 超过 `MAX_DOWNLOAD_MB` | 返回大小限制错误 |
| 重复论文 | 再次上传相同文件 | 应识别重复并给出明确结果；检查前端是否仍展示“处理完成”和原因 |
| 任务失败重试 | 让链接先失败，再点击重试 | 只有带 HTTP 来源链接的失败任务可以重试 |

### FQ-07 页面功能边界

逐页检查并记录：

| 页面 | 期望 |
| --- | --- |
| `/` | 显示真实统计和最近论文，不出现假数据 |
| `/papers` | 浏览、搜索、筛选、打开详情正常 |
| `/papers/<id>` | 总结、分类、证据页和 PDF 入口来自真实 API |
| `/inbox` | 链接和文件导入可用；轮询可见真实任务 |
| `/review` | 仅展示 `needs_review` 论文；写回操作禁用并说明未接入 |
| `/categories` | 分类与数量来自真实论文；编辑/新建禁用并说明未接入 |
| `/assistant` | 问答输入和发送禁用；不得返回 mock 答案 |
| `/settings` | 显示真实 provider、model、base URL 和 configured；测试连接必须调用真实后端接口且不得回显密钥 |
| `/login` | 开启认证后可登录、登出；API 401 时跳转登录 |

当前明确未接入的后端能力：

- 基于论文库的问答 API。
- 复核结论写回。
- 分类编辑与新建。
- 设置保存和导出。
- 向量索引与语义检索。

这些按钮应保持禁用或明确标注未接入，不能显示成功提示。

### FQ-08 响应式与可访问性

在每个目标视口执行：

1. 使用键盘 `Tab` 遍历顶部导航、搜索、筛选、表格操作和表单。
2. 确认焦点可见，顺序符合视觉顺序。
3. 确认图标按钮有可访问名称，悬停有提示。
4. 放大到 200% 后检查文字和按钮不重叠。
5. 检查长论文标题、长作者名、长错误信息和长分类名。

预期：

- 文本不遮住其他内容，不溢出按钮或卡片。
- 移动端导航可操作，不依赖悬停。
- 颜色对比度足够，状态不能只依靠颜色区分。
- 加载、空、错误、成功状态都有明确反馈。

证据：

- 桌面全页截图：
- 移动全页截图：
- 键盘焦点截图：

### FQ-09 安全与网络

检查：

1. 在 URL 输入框输入 `javascript:`、`file:`、`data:` 和私网地址。
2. 在论文标题或错误文本中测试 `<script>alert(1)</script>`，确认页面按文本显示。
3. 检查浏览器网络面板，确认 API Key 不出现在网页源码、请求体或日志中。
4. 开启 `AUTH_PASSWORD` 后，确认未登录访问受保护 API 返回 `401`。
5. 检查 CORS 只允许配置的来源。

预期：

- 不执行注入内容。
- 不允许非 HTTP(S) 和私网下载目标。
- 前端不保存 API Key。
- 未认证请求不能读取论文或创建任务。

## 证据记录

建议将截图和日志放到：

```text
/home/kun/Desktop/paper/storage/quality-gate/evidence/
```

每个用例记录：

| 字段 | 内容 |
| --- | --- |
| 用例 ID | 例如 FQ-04 |
| 浏览器/版本 |  |
| 视口 |  |
| API provider/model |  |
| 测试链接 |  |
| 观察结果 |  |
| 是否通过 |  |
| 截图或日志路径 |  |
| 备注 |  |

## 最终门禁结论模板

```text
构建：通过 / 失败
类型检查：通过 / 失败
后端测试：通过 / 失败
桌面浏览器：通过 / 失败 / 未验证
移动浏览器：通过 / 失败 / 未验证
真实模型：通过 / 失败 / 未验证
公开链接下载：通过 / 失败 / 未验证
PDF 浏览：通过 / 失败 / 未验证
待修复问题：
阻塞原因：
证据目录：
```
