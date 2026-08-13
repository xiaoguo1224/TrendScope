# TrendScope

通用 AI 内容趋势研究 Agent。当前已完成 Stage 02（Collection）：本地 SQLite、页面化采集配置、关键词扩展、公开内容采集及研究工作台。

## 本地运行

后端要求 Python 3.12 和 `uv`：

```powershell
cd backend
uv sync
uv run playwright install chromium
uv run alembic upgrade head
uv run uvicorn app.main:app --reload
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

后端默认监听 `http://127.0.0.1:8000`，前端开发服务器将 `/api` 和 `/health` 代理到后端。

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

系统提供 `generic-web` 平台适配器：它从 SQLite 中读取搜索 URL、DOM Selector 和解析规则，通过 Playwright 仅处理正常浏览可见的公开 HTTP(S) 页面。平台配置、Browser 参数、下载图片开关、LLM Provider 基础配置及 Query Expansion Prompt 都可在“系统配置”页面维护。

执行 `POST /api/v1/research/tasks/{id}/run` 后，系统保留用户关键词、用 Mock LLM 扩展查询词、采集并规范化内容、写入 `ContentItem` 与每次观察的 `ContentMetricSnapshot`，并可选下载公开图片到 `data/tasks/{task_id}/media/{content_id}/`。详情页可查看阶段、进度、扩展关键词、公开指标、缩略图及错误信息。

遇到登录、验证码、访问验证或权限限制时，采集会停止并记录可解释的失败信息；系统不会尝试绕过任何平台访问控制。Ranking、文本/视觉分析、趋势、Concept、图片 Prompt 与报告将在后续阶段实现。
