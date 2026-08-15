# TrendScope

通用 AI 内容趋势研究 Agent。当前已完成 Version 1：页面化采集/分析配置、公开内容采集、互动排序、图文分析、趋势工作台、Creative Concept、图片 Prompt 与研究报告。

## 给普通使用者的免环境版本

发布者可按 [Windows 免环境发布说明](docs/WINDOWS_PORTABLE_RELEASE.md) 构建并交付 `release\\TrendScope` 文件夹。使用者只需双击其中的 `TrendScope.exe`，无需安装 Python、Node.js、uv 或浏览器运行时；个人数据会保存到 `%LOCALAPPDATA%\\TrendScope`，升级程序不会覆盖它。

## 启动教程

### 1. 准备环境

在 Windows PowerShell 中确认已安装：

- Python 3.12；
- [uv](https://docs.astral.sh/uv/)；
- Node.js（建议使用当前 LTS，包含 `npm`）。

以下命令均从项目根目录 `TrendScope` 执行。首次运行需要网络连接，以下载 Python、Node 依赖和 Chromium 浏览器运行时。

### 2. 安装后端依赖并初始化数据库

```powershell
cd backend
uv sync
uv run playwright install chromium
uv run alembic upgrade head
```

`uv sync` 会创建并管理后端虚拟环境；`playwright install chromium` 是实际采集公开网页所必需的浏览器运行时；迁移会创建或升级项目根目录的 SQLite 文件 `data/app.db`。

### 3. 启动后端

保持第一个 PowerShell 窗口打开，执行：

```powershell
cd backend
uv run uvicorn app.main:app --reload
```

服务默认地址为 `http://127.0.0.1:8000`。可在另一窗口检查健康状态和 API 文档：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

成功时返回 `status: ok`；交互式 API 文档位于 `http://127.0.0.1:8000/docs`。

### 4. 启动前端

另开第二个 PowerShell 窗口，在项目根目录执行：

```powershell
cd frontend
npm install
npm run dev
```

打开终端显示的地址（默认是 `http://127.0.0.1:5173`）。开发服务器会将 `/api` 和 `/health` 请求代理到 `http://127.0.0.1:8000`，因此后端必须保持运行。

### 5. 首次使用

1. 打开“系统配置”，确认 `generic-web` 平台已启用；可按目标公开页面调整搜索 URL、Selector、解析规则和采集默认值。
2. 在“创建研究任务”填写平台、主题、关键词、时间范围、最大采集数量和研究目标，提交任务。
3. 打开任务详情并执行任务。系统依次扩展查询、采集公开内容、排名、分析、汇总趋势、生成 Concept / 文本 Prompt / 报告。
4. 在详情页查看 Hot、Rising、分析、趋势、Creative Concepts、图片 Prompt 和报告；文件同时保存到 `reports/{task_id}/report.md`、`report.json`、`prompts.md`。

若目标网站要求登录、验证码或访问验证，系统会记录可解释的失败或部分结果，不会尝试绕过访问控制。

### 使用已登录的系统浏览器（可选）

默认的“隔离 Playwright”浏览器没有你的登录状态。若公开页面允许登录后访问，可在“系统配置 → 采集与浏览器”中选择“连接系统浏览器”，让 TrendScope 通过本机 CDP 连接到一个**你手动登录的专用 Chrome / Edge 窗口**。这不是绕过登录：验证码、登录和任何平台确认都必须由你在该窗口中自行完成。

先关闭所有 Chrome（或 Edge）窗口，然后在 PowerShell 中以独立配置目录启动 Chrome：

```powershell
$TrendScopeBrowserProfile = Join-Path $env:LOCALAPPDATA 'TrendScope\browser-profile'
Start-Process 'C:\Program Files\Google\Chrome\Application\chrome.exe' -ArgumentList '--remote-debugging-port=9222', "--user-data-dir=$TrendScopeBrowserProfile"
```

如使用 Edge，将可执行文件替换为 `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`。在新打开的窗口中手动登录目标平台，然后在 TrendScope 中填写 CDP 地址 `http://127.0.0.1:9222`、保存并点击“测试配置”。系统只连接 `localhost`，每次测试/采集仅新建并关闭自己的标签页，绝不关闭你的浏览器窗口，也不会读取、展示或导出 Cookie。

Chrome 136 起，远程调试必须使用非默认的 `--user-data-dir`；因此不能直接连接你日常 Chrome 的默认个人资料。专用目录首次登录一次后会保留会话。详见 [Chrome 官方说明](https://developer.chrome.google.cn/blog/remote-debugging-port?hl=zh-cn)。

### 常用验证与停止

```powershell
# 后端测试
cd backend
uv run pytest

# 前端生产构建
cd frontend
npm run build
```

在运行服务的终端按 `Ctrl+C` 即可停止。之后再次启动时，只需重复“启动后端”和“启动前端”；依赖安装和浏览器安装通常不需要重复执行。

## 数据与迁移

默认 SQLite 数据库是项目根目录的 `data/app.db`。应用启动和迁移都会自动创建 `data/` 目录。移动或备份 `data/` 即可迁移本地任务与业务配置。

模式变更使用 Alembic，不手工修改数据库：

```powershell
cd backend
uv run alembic upgrade head
uv run alembic revision --autogenerate -m "describe change"
```

## Git 建议

源码、文档、Alembic migrations 和空目录占位文件应纳入 Git。`.gitignore` 默认排除 `data/app.db`、任务下载数据、日志、报告运行产物、Python 虚拟环境和前端依赖。提交时请仅暂存本次阶段涉及的文件；建议每个 Stage 使用独立提交。

## 当前能力与运行边界

系统提供可配置的 `generic-web` 采集适配器：它从 SQLite 中读取搜索 URL、搜索/详情 Selector 和解析规则，通过隔离 Playwright 或本机系统浏览器 CDP 连接，仅处理正常浏览可见的公开 HTTP(S) 页面。默认会写入 `generic-web` 与可编辑的小红书示例配置；常用 Selector 可在表单中直接填写，复杂规则可在“高级配置”中维护。保存后可使用“测试配置”执行一次受限公开页面测试，查看搜索卡片数、第一条内容和详情解析结果。平台配置、Browser 参数、可选请求 Header（例如 Cookie 或 Authorization，留空即不发送）、下载图片开关、LLM Provider 基础配置及 Query Expansion Prompt 都可在“系统配置”页面维护。

浏览器页面操作默认超时为 120 秒，可在“系统配置 → 浏览器”调整；前端对“开始研究”保留 15 分钟请求预算，对显式模型分析保留 5 分钟，避免浏览器仍在滚动、提取或下载公开媒体时由界面提前中断。扩词会严格校验六个分类字段；模型返回不符合协议或只回显原词时会发起一次修复请求，仍失败才使用标明日志的本地兜底词，保证采集能覆盖补充关键词。

扩词结果会保存到当前 `ResearchTask.expanded_keywords`。同一任务再次执行采集时，只要结果仍包含补充词，就会直接复用而不调用模型；新建任务不会跨任务复用扩词结果。

下载的公开媒体会根据图片内容识别 JPEG、PNG、GIF 或 WebP，而不信任 URL 后缀；历史 `.bin` 文件同样会在送入视觉模型前识别真实 MIME。非图片或访问拦截页面不会发送给视觉模型。

LLM / Vision 业务服务统一通过 `ModelGateway` 调用模型；它不依赖 URL 格式、SDK 或厂商响应 JSON。每个 Provider 在“系统配置 → AI Provider”中声明协议（自动兼容探测、OpenAI Responses / Chat Completions、Anthropic Messages、Gemini 或 Ollama）、模型能力和路由优先级，再填写 Base URL、模型名和密钥。相同用途按优先级从小到大选择；仅在 `429`、超时、网络故障或 `5xx` 等可恢复异常时切换下一 Provider，参数错误、鉴权错误和能力不匹配会明确失败而不会被掩盖。`auto` 保持历史 URL 兼容行为，推荐新配置明确选择协议。SQLite 中的历史 UTC 时间在 API 输出和页面展示时统一转换为东八区（`Asia/Shanghai`）。

每个 Provider 保存后均可点击“测试模型配置”。LLM 使用最小 JSON 请求验证连接；Vision 使用内置的透明 1×1 PNG 验证视觉输入能力，不会上传采集到的平台图片。测试结果会显示实际调用地址及安全截断的响应摘要。

任务分析采用“证据工具 + 一份综合结论”模式：`POST /api/v1/research/tasks/{id}/analysis/run` 才会调用模型，模型只能在任务范围内读取榜单、指定内容详情、可用本地图片和任务约束，然后持久化一份文案、视觉、受众、热度和趋势总结。`GET /analysis` 与 `GET /trends` 只读取该结果，页面切换不会按内容逐条重跑模型。每次显式重新生成会使依赖旧结论的 Concepts、Prompts 和报告失效，并在下次读取时基于新结论重建。

执行 `POST /api/v1/research/tasks/{id}/run` 后，系统保留用户关键词、用 Mock LLM 扩展查询词、采集并规范化内容、写入 `ContentItem` 与每次观察的 `ContentMetricSnapshot`，并可选下载公开图片到 `data/tasks/{task_id}/media/{content_id}/`。详情页可查看阶段、进度、扩展关键词、公开指标、缩略图及错误信息。

Ranking 依据真实互动指标、发布时间与多个 `ContentMetricSnapshot` 计算 Hot / Rising / 指标榜单；无历史快照时增长分数保持为空。Text、Vision 和趋势输出均经过结构化 Schema 校验，并与客观指标分开保存。当前 Provider 配置从 SQLite 读取，但未接入的供应商会安全降级到 Mock Provider，因此不需要真实 API Key 即可测试。

任务采集完成后会串联分析、趋势、Creative Concept、Prompt 和报告流程。Concept 由多个趋势来源聚合生成，不复刻单一内容；图片 Prompt 仅输出文本，不调用图片模型。每个任务在 `reports/{task_id}/` 下持久化 `report.md`、`report.json` 和 `prompts.md`，详情页的 Creative Concepts、图片 Prompt、报告 Tabs 可以直接查看结果。Concept 数量、Prompt 语言/风格、报告默认参数，以及 Concept/Prompt 模板都可在“系统配置”页面维护。

遇到登录、验证码、访问验证或权限限制时，采集会停止并记录可解释的失败信息；系统不会尝试绕过任何平台访问控制。
