# Stage 01 — Foundation

## 目标

建立完整的前后端基础工程、SQLite 数据模型和核心抽象。

本阶段不要实现真实平台采集，也不要实现 AI 分析。

## 必须实现

### Git

- 初始化 Git 仓库（如果当前尚未初始化）
- 完整 `.gitignore`
- 明确运行时数据不提交
- README 说明 Git 和数据迁移方式

### 后端

- FastAPI 基础工程
- Pydantic v2
- SQLAlchemy 2.x
- SQLite
- Alembic
- 配置管理
- 日志
- 统一异常处理
- `/health`
- ResearchTask
- ContentItem
- ContentMetricSnapshot
- AppSetting / PlatformConfig / AIProviderConfig / PromptTemplate / RankingConfig（可合理调整拆分）
- Repository
- BrowserAdapter 接口
- PlatformAdapter 接口
- MockBrowserAdapter
- MockPlatformAdapter
- pytest

### 前端

初始化：

- Vue 3
- TypeScript
- Vite
- Element Plus
- Pinia
- Vue Router
- Axios

建立基础布局和页面：

- ResearchTask 列表页
- ResearchTask 创建页
- ResearchTask 详情页占位
- 系统配置页
- 404

前端只接 Stage 01 已存在 API。

## 本阶段 API

至少：

```text
GET  /health

POST /api/v1/research/tasks
GET  /api/v1/research/tasks
GET  /api/v1/research/tasks/{id}
```

## 明确不做

- Playwright 真实采集
- 具体平台 Adapter
- Query Expansion
- Ranking
- LLM
- VLM
- Trend Analysis
- Concept
- Prompt Generator
- Report Generator

## 验收

后端：

```bash
uv run pytest
```

通过。

数据库：

- 无需外部数据库服务
- 默认自动使用 `data/app.db`
- Alembic upgrade 正常
- 表结构正确
- 数据库文件随 `data/` 目录可迁移

前端：

```bash
npm run build
```

通过。

页面可以：

1. 创建 ResearchTask
2. 查看 Task 列表
3. 查看基础 Task 详情
4. 查看和修改基础系统配置，并持久化到 SQLite

---

## 可直接给 Codex 的提示词

```text
请先完整阅读项目根目录 AGENTS.md，然后阅读 docs/stages/STAGE_01_FOUNDATION.md。

现在只实现 Stage 01：Foundation。

固定技术栈：

前端：
Vue 3 + TypeScript + Vite + Element Plus + Pinia + Vue Router + Axios

后端：
Python 3.12 + FastAPI + Pydantic v2 + SQLAlchemy 2.x + Alembic + pytest + uv

数据库：
SQLite 文件数据库，默认 data/app.db

要求：

1. 建立 backend/ 和 frontend/ 两个目录。
2. 如果当前项目尚未初始化 Git，则执行 git init。
3. 创建合理的 .gitignore。
4. 源码、migration、docs 纳入 Git；data/app.db、任务下载数据、日志、reports 运行产物默认忽略。
5. README 说明 Git 使用建议、数据库文件位置和数据迁移方式。
6. 后端实现 FastAPI 基础工程、配置、日志、异常处理和 /health。
7. 使用 SQLite 文件数据库，不依赖 PostgreSQL/MySQL 等外部数据库服务。
8. 默认数据库路径为 data/app.db，并确保目录自动创建。
9. 使用 Alembic 管理数据库迁移。
10. 实现 ResearchTask、ContentItem、ContentMetricSnapshot。
11. 增加配置持久化模型，至少覆盖 AppSetting、PlatformConfig、AIProviderConfig、PromptTemplate、RankingConfig；可以合理合并，但不要全部塞进一个无约束 JSON Blob。
12. 实现 Repository 层。
13. 定义 BrowserAdapter 和 PlatformAdapter 抽象接口。
14. 提供 MockBrowserAdapter 和 MockPlatformAdapter。
15. 实现 POST /api/v1/research/tasks。
16. 实现 GET /api/v1/research/tasks。
17. 实现 GET /api/v1/research/tasks/{id}。
18. 实现基础配置 CRUD API。
19. 初始化 Vue 3 前端。
20. 前端使用 Element Plus。
21. 实现 ResearchTask 列表页、创建页和基础详情页。
22. 实现系统配置页，第一版至少可维护采集默认参数、Browser 默认参数和 Ranking 默认参数。
23. 所有无需启动时确定的业务配置必须通过页面保存到 SQLite，不要求用户修改 .env/YAML/JSON。
24. Axios API Client 集中管理。
25. 不要实现真实平台采集。
26. 不要实现 Query Expansion。
27. 不要实现 Ranking、LLM、VLM、趋势分析和 Prompt。
28. 编写必要测试。
29. 完成后运行 uv run pytest 和 npm run build，并修复所有失败。

不要重写 AGENTS.md 中已经确定的架构。

最后输出：
- 完成内容
- Git 状态和 .gitignore 设计
- 主要目录
- SQLite 数据文件位置
- 数据库迁移
- 配置模型与配置 API
- API
- 前端页面
- 测试结果
- 下一阶段尚未实现的范围
```
