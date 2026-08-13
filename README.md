# TrendScope

通用 AI 内容趋势研究 Agent。当前完成 Stage 01（Foundation）：本地 SQLite、任务基础 API、可配置的研究工作台和核心适配器抽象。

## 本地运行

后端要求 Python 3.12 和 `uv`：

```powershell
cd backend
uv sync
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

## Stage 01 边界

已提供任务创建、列表、详情和系统配置持久化。真实采集、扩词、排行、LLM/VLM、趋势、Concept、Prompt 和报告生成均留待后续阶段。

配置 API 位于 `/api/v1/config`：可管理采集与 Browser 默认参数、平台配置、AI Provider（读取时 API Key 掩码化）、Prompt 模板及 Ranking 参数。Stage 01 前端已暴露这些基础配置项；保存的 Ranking/Provider/Prompt 仅供后续阶段消费，不会在本阶段执行分析或调用模型。
