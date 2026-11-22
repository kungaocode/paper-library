# Paper Atlas 内网测试与接通清单

本文档面向只在内网运行的 Paper Atlas。测试顺序建议固定为：先做不写数据的构建和接口检查，再做一次真实 URL 导入，最后检查 PDF、分类目录、`KNOWLEDGE_BASE.md` 和前端详情页。

## 1. 测试前准备

### 1.1 记录内网地址

先确定运行本项目机器在内网中的地址，后续统一替换本文里的 `<SERVER_IP>`：

```bash
hostname -I
```

示例：

```text
SERVER_IP=192.168.1.20
前端地址=http://192.168.1.20:3000
API 地址=http://192.168.1.20:8000
```

如果前端和后端运行在不同机器上，还需要分别记录前端机器地址和 API 机器地址。

### 1.2 保护现有论文库

第一次做真实导入前，至少备份以下内容：

```bash
cd /home/kun/Desktop/paper
cp KNOWLEDGE_BASE.md KNOWLEDGE_BASE.md.before-internal-test
```

`completed/`、`need_organization/` 和 `storage/api/library.sqlite3` 也建议做一次备份。测试时优先使用一篇新论文，不要反复导入同一篇已有论文。

### 1.3 运行环境

项目当前已使用以下本地环境完成过验证：

```text
Python 虚拟环境：/home/kun/Desktop/paper/apps/api/.venv
Node 依赖：/home/kun/Desktop/paper/apps/web/node_modules
后端：FastAPI
前端：Next.js 15
数据库：SQLite
```

## 2. 内网运行拓扑

```text
内网浏览器
    |
    | http://<SERVER_IP>:3000
    v
Next.js 前端
    |
    | http://<SERVER_IP>:8000
    v
FastAPI
    |
    +--> 内网或外网论文 URL
    +--> OpenAI-compatible 模型接口
    +--> /home/kun/Desktop/paper/need_organization/
    +--> /home/kun/Desktop/paper/completed/<分类>/
    +--> /home/kun/Desktop/paper/KNOWLEDGE_BASE.md
    +--> /home/kun/Desktop/paper/storage/api/library.sqlite3
```

## 3. 模型接口接通

### 3.1 后端配置

在以下位置创建或修改 `apps/api/.env`：

```text
/home/kun/Desktop/paper/apps/api/.env
```

配置示例：

```env
PAPER_ROOT=/home/kun/Desktop/paper
LLM_PROVIDER=openai-compatible
LLM_BASE_URL=http://<MODEL_SERVER_IP>:<MODEL_PORT>/v1
LLM_MODEL=<MODEL_ID>
LLM_API_KEY=
LLM_TIMEOUT_SECONDS=900
LLM_MAX_OUTPUT_TOKENS=6000
LLM_JSON_MODE=true
```

如果模型服务不校验密钥，`LLM_API_KEY` 可以留空。如果模型服务要求 Bearer Token，填写实际密钥。

### 3.2 内网访问与登录配置

同一份 `apps/api/.env` 还控制浏览器 CORS 白名单和可选登录：

```env
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://<SERVER_IP>:3000

AUTH_USERNAME=admin
AUTH_PASSWORD=
AUTH_SESSION_SECRET=
AUTH_SESSION_TTL_HOURS=24
AUTH_COOKIE_SECURE=false
```

说明：

- `CORS_ORIGINS` 使用英文逗号分隔，填写浏览器实际访问前端的完整 origin，不包含末尾斜杠。
- `AUTH_PASSWORD` 为空时，后端登录保护关闭，适合可信内网的预览模式。
- `AUTH_PASSWORD` 非空时，除 `/health`、文档和 `/api/auth/*` 外的 API 都要求登录。
- `AUTH_SESSION_SECRET` 建议设为随机值。可以用 `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` 生成；留空时会退化为使用 `AUTH_PASSWORD` 签名。
- `AUTH_COOKIE_SECURE=true` 只应在浏览器通过 HTTPS 访问 API 时启用。
- 前端和 API 应使用相同的主机名或 IP。例如前端为 `http://192.168.1.20:3000`、API 为 `http://192.168.1.20:8000`，登录 Cookie 才能被前端页面携带。

### 3.3 接口格式要求

后端调用的是 OpenAI-compatible Chat Completions：

```text
POST <LLM_BASE_URL>/chat/completions
```

请求中会使用：

```json
{
  "model": "<LLM_MODEL>",
  "messages": [],
  "temperature": 0.1,
  "max_tokens": 6000,
  "response_format": {
    "type": "json_object"
  }
}
```

如果模型服务不支持 `response_format`，在 `apps/api/.env` 中设置：

```env
LLM_JSON_MODE=false
```

模型适配器位置：

```text
/home/kun/Desktop/paper/apps/api/app/model_provider.py
```

如果使用 vLLM，`LLM_BASE_URL` 通常类似：

```env
LLM_BASE_URL=http://10.0.0.50:8001/v1
```

如果使用 Ollama 的 OpenAI-compatible 接口，通常类似：

```env
LLM_BASE_URL=http://10.0.0.50:11434/v1
LLM_MODEL=qwen2.5:14b
```

实际模型名必须以模型服务端的可用模型列表为准。

## 4. 前端接通 API

### 4.1 使用环境变量

在以下位置创建或修改 `apps/web/.env.local`：

```text
/home/kun/Desktop/paper/apps/web/.env.local
```

内容：

```env
NEXT_PUBLIC_API_URL=http://<SERVER_IP>:8000
```

前端读取位置：

```text
/home/kun/Desktop/paper/apps/web/lib/api.ts
```

注意：`NEXT_PUBLIC_*` 会在构建时写入前端产物。修改 `/apps/web/.env.local` 后必须重新启动开发服务；如果是生产构建，必须重新执行 `npm run build` 后再启动。

### 4.2 内网 CORS

后端从 `apps/api/.env` 的 `CORS_ORIGINS` 读取白名单。默认允许：

```env
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001
```

从另一台内网机器访问 `http://<SERVER_IP>:3000` 时，在 `apps/api/.env` 中追加该 origin：

```env
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000,http://192.168.1.20:3000
```

修改后必须重启 FastAPI。

如果前端和后端通过同一个反向代理提供，并保持浏览器侧的 scheme、host、port 完全一致，则可以避免跨域配置。

## 5. 启动服务

### 5.1 启动后端

```bash
cd /home/kun/Desktop/paper/apps/api
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

开发阶段也可以加 `--reload`：

```bash
cd /home/kun/Desktop/paper/apps/api
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5.2 启动开发前端

```bash
cd /home/kun/Desktop/paper/apps/web
npm run dev -- --hostname 0.0.0.0 --port 3000
```

浏览器访问：

```text
http://<SERVER_IP>:3000
```

登录方式取决于 `apps/api/.env`：

- `AUTH_PASSWORD` 为空：登录页处于可信内网预览模式，提交任意非空账号和密码即可进入。
- `AUTH_PASSWORD` 已配置：使用 `AUTH_USERNAME` 和 `AUTH_PASSWORD` 登录。

### 5.3 启动生产前端

```bash
cd /home/kun/Desktop/paper/apps/web
npm run build
npm run start -- --hostname 0.0.0.0 --port 3000
```

执行 `npm run build` 时，当前 shell 必须已经加载正确的 `NEXT_PUBLIC_API_URL`。

## 6. 不写数据的验收步骤

### 6.1 后端测试

```bash
cd /home/kun/Desktop/paper/apps/api
.venv/bin/pytest -q
```

当前预期：

```text
7 passed
```

测试使用隔离的临时论文根目录，不应修改真实 `KNOWLEDGE_BASE.md`。

### 6.2 前端类型检查和生产构建

```bash
cd /home/kun/Desktop/paper/apps/web
npm run typecheck
npm run build
```

两项都应成功退出。

### 6.3 后端健康检查

在 API 所在机器执行：

```bash
curl http://127.0.0.1:8000/health
```

预期：

```json
{"status":"ok"}
```

从另一台内网机器执行：

```bash
curl http://<SERVER_IP>:8000/health
```

### 6.4 模型状态检查

如果已设置 `AUTH_PASSWORD`，先登录并保存 Cookie：

```bash
curl -c /tmp/paper-atlas-cookie.txt \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"<AUTH_PASSWORD>"}' \
  http://127.0.0.1:8000/api/auth/login
```

```bash
curl -b /tmp/paper-atlas-cookie.txt http://127.0.0.1:8000/api/settings/models
```

配置正确时应有：

```json
{
  "provider": "openai-compatible",
  "model": "<MODEL_ID>",
  "base_url": "http://<MODEL_SERVER_IP>:<MODEL_PORT>/v1",
  "configured": true
}
```

如果 `configured` 是 `false`，先不要测试 URL 导入。检查 `apps/api/.env` 中的 `LLM_MODEL` 是否为空，并确认修改后已经重启 API。

### 6.5 前端连接检查

打开浏览器页面后确认：

```text
页面顶部显示模型名，而不是“API 未连接”或“模型未配置”。
```

如果浏览器控制台出现 CORS 错误，回到第 4.2 节，把内网前端地址加入 `CORS_ORIGINS` 并重启 API。

## 7. 真实 URL 导入测试

建议使用一篇之前未收录的 arXiv 论文链接，例如：

```text
https://arxiv.org/abs/<ARXIV_ID>
```

测试步骤：

1. 打开 `http://<SERVER_IP>:3000`。
2. 进入工作台。
3. 在“从论文链接导入”输入框粘贴论文链接。
4. 点击“开始导入”。
5. 观察任务状态依次经过下载、提取、分类、分析、归档和成功。
6. 等待页面顶部任务显示成功。
7. 在论文列表中打开新论文。
8. 检查论文详情中的分类、置信度、中文核心论点、创新点、英文论点、英文创新点和分类依据。
9. 打开 PDF 阅读器，确认能加载刚才导入的文件。

过程中可以用以下命令观察文件：

```bash
ls -lah /home/kun/Desktop/paper/need_organization
ls -lah /home/kun/Desktop/paper/completed
```

导入成功后，原文件应从 `need_organization/` 消失，并进入 `completed/<分类目录>/`。

## 8. 可追踪结果检查

如果已设置 `AUTH_PASSWORD`，先按第 6.4 节生成 `/tmp/paper-atlas-cookie.txt`。下面所有 `/api/*` 命令均可加 `-b /tmp/paper-atlas-cookie.txt`。

### 8.1 任务接口

```bash
curl -b /tmp/paper-atlas-cookie.txt http://127.0.0.1:8000/api/jobs
```

成功任务应包含：

```text
status: succeeded
paper_id: 非空
progress: 100
stage: succeeded
```

### 8.2 论文接口

```bash
curl -b /tmp/paper-atlas-cookie.txt http://127.0.0.1:8000/api/papers
```

新论文应包含：

```text
title
category_id
file_url
original_url
candidate_categories
summary.thesis_zh
summary.novelty_zh
summary.thesis_en
summary.novelty_en
```

### 8.3 PDF 接口

先从上一步拿到 `id`，再执行：

```bash
curl -I -b /tmp/paper-atlas-cookie.txt http://127.0.0.1:8000/api/papers/<PAPER_ID>/file
```

预期：

```text
HTTP 200
content-type: application/pdf
```

### 8.4 知识库和目录

```bash
rg -n "<论文标题或标题关键词>" /home/kun/Desktop/paper/KNOWLEDGE_BASE.md
find /home/kun/Desktop/paper/completed -type f -name '*.pdf' -printf '%p\n'
```

确认：

- `KNOWLEDGE_BASE.md` 出现新论文条目。
- 论文总数增加。
- PDF 位于模型分类对应的 `completed/<分类>/` 中。
- `need_organization/` 中没有遗留该论文。

## 9. 其他功能测试

### 9.1 本地 PDF 上传

在工作台上传一个未收录的 PDF，确认它先进入 `need_organization/`，随后完成分类、分析和归档。

### 9.2 重复导入

重复提交同一链接或同一 PDF。预期：

```text
识别 SHA-256 重复
不新增 KNOWLEDGE_BASE.md 条目
重复文件进入 _archive/duplicates/
原论文任务显示成功并复用已有 paper_id
```

### 9.3 失败任务重试

使用一个暂时不可访问的论文链接创建任务。预期任务失败并保留错误信息。恢复网络后，在前端点击重试，任务应重新进入队列。

## 10. URL 访问内网资源

默认配置：

```env
ALLOW_PRIVATE_URLS=false
```

这表示论文 URL 不允许指向 `10.x`、`172.16-31.x`、`192.168.x`、`127.x` 等内网或本机地址。

只有当你确实需要从内网论文服务器下载 PDF 时，才设置：

```env
ALLOW_PRIVATE_URLS=true
```

不要为了让普通 arXiv 链接工作而开启这个开关。普通公网论文链接应保持默认关闭。

## 11. API 与代码接通位置

| 功能 | 位置 | 说明 |
| --- | --- | --- |
| 前端 API 基地址 | `apps/web/lib/api.ts` | 读取 `NEXT_PUBLIC_API_URL`，默认 `http://localhost:8000` |
| URL 提交和任务轮询 | `apps/web/components/UploadPanel.tsx` | 调用 `/api/imports/url`、`/api/jobs`、重试接口 |
| 论文列表刷新 | `apps/web/components/PapersBrowser.tsx` | 加载 `/api/papers` 并监听导入完成事件 |
| 论文详情加载 | `apps/web/app/(workspace)/papers/[id]/page.tsx` | 调用 `/api/papers/{id}` |
| API 路由 | `apps/api/app/main.py` | 健康、模型状态、论文、任务、导入和 PDF 接口 |
| 可选登录鉴权 | `apps/api/app/auth.py` | 签名会话 Cookie、凭据和过期校验 |
| URL 导入流水线 | `apps/api/app/pipeline.py` | 下载、提取、查重、分类、分析、归档 |
| 模型适配器 | `apps/api/app/model_provider.py` | OpenAI-compatible `/chat/completions` 调用 |
| 知识库写入 | `apps/api/app/knowledge_base.py` | 移动 PDF 并追加 `KNOWLEDGE_BASE.md` |
| 环境变量解析 | `apps/api/app/config.py` | 读取模型、目录、下载限制等配置 |

## 12. 当前已接通的接口

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| GET | `/health` | 服务健康检查 |
| GET | `/api/auth/status` | 查询是否启用登录及当前会话状态 |
| POST | `/api/auth/login` | 校验账号并签发 HttpOnly Cookie |
| POST | `/api/auth/logout` | 清除登录 Cookie |
| GET | `/api/settings/models` | 查询模型与配置状态 |
| GET | `/api/categories` | 获取分类体系 |
| GET | `/api/papers` | 获取论文列表 |
| GET | `/api/papers/{id}` | 获取论文详情 |
| GET | `/api/papers/{id}/file` | 读取论文 PDF |
| GET | `/api/jobs` | 获取任务列表 |
| GET | `/api/jobs/{id}` | 获取单个任务 |
| POST | `/api/imports/url` | 创建 URL 导入任务 |
| POST | `/api/imports/file` | 创建本地 PDF 导入任务 |
| POST | `/api/jobs/{id}/retry` | 重试失败的 URL 任务 |

## 13. 仍需关注的配置和缺口

### 13.1 登录鉴权

后端现已提供 `/api/auth/login`、`/api/auth/logout` 和 `/api/auth/status`。

- `AUTH_PASSWORD` 为空：登录保护关闭，前端预览 Cookie 仍用于页面门禁。
- `AUTH_PASSWORD` 非空：后端校验账号密码并签发带过期时间和 HMAC 签名的 HttpOnly Cookie。
- 受保护范围：除 `/health`、`/docs`、`/openapi.json` 和 `/api/auth/*` 外的 `/api/*` 路由。
- 默认有效期为 24 小时，可通过 `AUTH_SESSION_TTL_HOURS` 调整。

这适合可信内网的单账号保护。若需要多用户、审计、统一身份认证或公网访问，仍应接入正式身份系统或反向代理鉴权。

### 13.2 CORS

CORS 白名单已改为 `apps/api/.env` 中的 `CORS_ORIGINS` 配置：

```env
CORS_ORIGINS=http://localhost:3000,http://192.168.1.20:3000
```

修改后重启 FastAPI 生效，不再需要修改源码。

### 13.3 下载限制和文本范围

可在 `apps/api/.env` 调整：

```env
MAX_DOWNLOAD_MB=120
MAX_TEXT_CHARS=120000
ANALYSIS_PAGE_LIMIT=45
```

说明：

- `MAX_DOWNLOAD_MB`：单篇 PDF 下载和上传上限。
- `MAX_TEXT_CHARS`：单次送入模型的最大文本字符数。
- `ANALYSIS_PAGE_LIMIT`：结构化分析最多读取的页数。

## 14. 常见问题

### 模型未配置

现象：

```text
导入接口返回 503
前端显示“模型未配置”
```

检查：

```bash
cat /home/kun/Desktop/paper/apps/api/.env
curl http://127.0.0.1:8000/api/settings/models
```

确认 `LLM_MODEL` 非空，并重启 API。

### API 未连接

检查：

```bash
curl http://<SERVER_IP>:8000/health
```

同时检查 `apps/web/.env.local`、浏览器控制台和 API 终端日志。

### CORS 报错

现象：

```text
Access to fetch at 'http://<SERVER_IP>:8000/...' from origin
'http://<SERVER_IP>:3000' has been blocked by CORS policy
```

处理：在 `apps/api/.env` 的 `CORS_ORIGINS` 中加入完整的前端 origin，并重启 API。

### 登录后仍返回 401

检查：

```bash
curl http://<SERVER_IP>:8000/api/auth/status
```

确认：

- 前端和 API 使用相同的主机名或 IP。
- `NEXT_PUBLIC_API_URL` 指向浏览器可访问的 API 地址。
- `AUTH_USERNAME`、`AUTH_PASSWORD` 与登录时输入一致。
- 修改 `apps/api/.env` 后已经重启 API。

### 链接页面找不到 PDF

处理：使用 arXiv PDF 地址，或直接提供站点返回 `application/pdf` 的下载链接。

### 私有地址被拒绝

现象：

```text
出于 SSRF 防护，默认不允许访问内网或本机地址。
```

如果论文链接确实位于内网服务器，按第 10 节开启 `ALLOW_PRIVATE_URLS=true`。

### 模型返回格式异常

检查模型是否支持 OpenAI-compatible JSON object。如果不支持，设置 `LLM_JSON_MODE=false`，并确保模型仍能按提示词返回 JSON。

## 15. 最短验收清单

```text
[ ] apps/api/.env 已填写真实内网模型地址和模型名
[ ] apps/api/.env 修改后已重启 FastAPI
[ ] apps/web/.env.local 已填写内网 API 地址
[ ] apps/api/.env 的 CORS_ORIGINS 已加入内网前端 origin
[ ] 已决定是否启用 AUTH_PASSWORD，并配置一致的 AUTH_SESSION_SECRET
[ ] pytest 通过
[ ] npm run typecheck 通过
[ ] npm run build 通过
[ ] /health 返回 ok
[ ] /api/auth/status 返回预期登录状态
[ ] /api/settings/models 返回 configured: true
[ ] 前端顶部不再显示 API 未连接或模型未配置
[ ] 一篇真实 URL 导入成功
[ ] 新论文出现在 papers 列表和详情页
[ ] PDF 阅读器能打开导入文件
[ ] PDF 已进入 completed/<分类>/
[ ] KNOWLEDGE_BASE.md 已有新条目且总数增加
[ ] need_organization/ 没有遗留该论文
```
