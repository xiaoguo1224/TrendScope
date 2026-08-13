# AGENTS.md

## 1. 项目名称

通用 AI 内容趋势研究 Agent（Generic AI Content Trend Research Agent）

## 2. 项目定位

本项目是一个面向多平台、多主题的 AI 内容趋势研究系统。

用户通过前端创建 Research Task，自定义：

- `platform`：研究平台
- `topic`：研究主题
- `keywords`：初始关键词
- `time_range`：研究时间范围
- `max_items`：最大采集数量
- `research_goals`：研究目标

系统负责：

1. 理解用户研究意图；
2. 补充搜索关键词；
3. 通过浏览器采集公开可见内容；
4. 将不同平台内容标准化；
5. 基于真实互动数据筛选热门和 Rising 内容；
6. 分析文章；
7. 分析图片；
8. 聚合跨内容趋势；
9. 总结可复用的文案与视觉规律；
10. 生成 Creative Concept；
11. 生成可用于外部图片模型的高质量图片 Prompt；
12. 输出 Markdown / JSON 研究报告；
13. 通过 Web 前端展示任务、爆款内容、爆款图片、分析结果、趋势和 Prompt。

系统不得固定为“小红书”“穿戴甲”“美甲”或任何单一平台/领域。

---

## 3. 固定技术栈

### 前端

- Vue 3
- TypeScript
- Vite
- Element Plus
- Pinia
- Vue Router
- Axios

### 后端

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2.x
- Alembic
- Playwright
- pytest
- uv

### 数据库

- SQLite

数据库固定使用 SQLite 文件数据库。

目标：

- 无需额外安装或配置数据库服务；
- 数据随项目目录或数据目录一起迁移；
- 适合本地部署、单机部署和快速分发；
- 后续如果规模明显增长，再评估 SQLite，但第一版不得为了“未来可能需要”提前引入数据库服务。

### AI

- `LLMProvider` 抽象
- `VisionProvider` 抽象
- 测试环境使用 Mock Provider

### 浏览器

- `BrowserAdapter` 抽象
- 第一版默认 `PlaywrightBrowserAdapter`
- 测试使用 `MockBrowserAdapter`
- 未来允许扩展 `MCPBrowserAdapter`

### 平台

- `PlatformAdapter` 抽象
- 不同平台的搜索、DOM、数据结构差异只允许存在于 PlatformAdapter 内

---

## 4. 当前明确不做

当前版本不要实现：

- 自动发布
- 自动点赞、评论、关注
- 社交媒体账号矩阵
- 商品 SKU
- 订单与电商交易
- 图片生成 API
- 视频生成
- 微服务
- Kafka / RabbitMQ 等复杂消息队列
- 验证码破解
- 平台签名破解
- 私有 API 逆向
- 绕过登录限制
- 代理池规避风控
- 其他绕过平台访问控制的能力

项目核心边界：

> 发现 → 采集 → 排名 → 分析 → 趋势 → Concept → Prompt → Report

---

## 5. 总体业务流程

```text
Vue 3 + Element Plus
        ↓
Create ResearchTask
        ↓
FastAPI
        ↓
Topic Understanding
        ↓
Query Expansion
        ↓
BrowserAdapter
        ↓
PlatformAdapter
        ↓
Content Normalization
        ↓
SQLite
        ↓
Ranking Engine
        ↓
Text Analysis + Visual Analysis
        ↓
Trend Analysis
        ↓
Creative Concept
        ↓
Image Prompt Generator
        ↓
Report Generator
        ↓
Vue 3 结果展示
```

---

## 6. 核心设计原则

### 6.1 平台无关

核心业务层不得大量出现：

```python
if platform == "xiaohongshu":
    ...
elif platform == "douyin":
    ...
```

平台差异必须通过 `PlatformAdapter` 处理。

推荐接口：

```python
class PlatformAdapter(Protocol):
    async def search(self, query: str, limit: int): ...
    async def open_content(self, url: str): ...
    async def extract_content(self): ...
    async def download_media(self, content): ...
```

未来可以扩展：

- XiaohongshuAdapter
- DouyinAdapter
- TikTokAdapter
- InstagramAdapter
- YouTubeAdapter
- GenericWebAdapter

第一版不要求全部实现。

### 6.2 浏览器无关

业务层不得直接操作 Playwright。

统一使用：

```python
class BrowserAdapter(Protocol):
    async def open(self, url: str): ...
    async def scroll(self, ...): ...
    async def extract_visible_content(self, ...): ...
    async def screenshot(self, ...): ...
    async def download_media(self, ...): ...
```

实现：

- `PlaywrightBrowserAdapter`
- `MockBrowserAdapter`

未来：

- `MCPBrowserAdapter`

### 6.3 领域无关

核心 Schema 不得写死：

- nail_shape
- garment_type
- phone_case_material

行业专有字段统一使用：

```json
{
  "domain_attributes": {}
}
```

### 6.4 模型无关

业务层不得直接绑定具体模型厂商。

统一抽象：

```python
class LLMProvider(Protocol):
    async def generate_structured(...): ...

class VisionProvider(Protocol):
    async def analyze_images(...): ...
```

### 6.5 数据事实与 AI 推断分离

确定性代码负责：

- 点赞、收藏、评论、分享、播放
- 发布时间
- 时间衰减
- 增长速度
- 排名
- 聚合统计

LLM/VLM 负责：

- 文案语义分析
- 图片视觉分析
- 风格归纳
- 趋势解释
- Concept
- Prompt

LLM 不得虚构任何互动数据和增长数据。

---

## 7. 核心领域模型

### 7.1 ResearchTask

至少包含：

```text
id
platform
topic
keywords
expanded_keywords
time_range
max_items
research_goals
status
error_message
created_at
updated_at
```

建议状态：

```text
PENDING
EXPANDING_QUERY
COLLECTING
RANKING
ANALYZING
GENERATING_REPORT
COMPLETED
PARTIAL
FAILED
```

### 7.2 ContentItem

统一平台内容模型：

```text
id
research_task_id
platform
external_id
url
title
text
author_name
published_at
like_count
favorite_count
comment_count
share_count
view_count
media_type
image_urls
local_image_paths
video_urls
query_keyword
collected_at
raw_data
created_at
updated_at
```

平台不存在的指标使用 `null`。

### 7.3 ContentMetricSnapshot

```text
id
content_item_id
like_count
favorite_count
comment_count
share_count
view_count
captured_at
```

用于计算：

```text
like_velocity
favorite_velocity
comment_velocity
share_velocity
view_velocity
```

没有多次快照时，增长字段必须为 `null`。

---

## 8. Query Expansion

用户输入关键词必须保留，AI 只能补充。

统一输出：

```json
{
  "core_keywords": [],
  "long_tail_keywords": [],
  "trend_keywords": [],
  "audience_keywords": [],
  "scenario_keywords": [],
  "style_keywords": []
}
```

必须限制扩展数量，禁止无限递归扩词。

---

## 9. Ranking Engine

不得简单按点赞数排序。

至少支持：

```text
engagement_score
freshness_score
growth_score
hot_score
```

可选：

```text
save_score
discussion_score
share_score
view_score
```

建议对大数值使用 `log1p` 等处理。

榜单：

```text
Hot
Rising
Most Saved
Most Discussed
Most Shared
Most Viewed
```

不存在对应指标时跳过该榜单。

---

## 10. Text Analysis

统一字段至少包含：

```text
hook_type
title_structure
opening_hook
writing_style
emotion
pain_points
benefits
target_audience
scenario
cta
hashtags
topic_tags
reusable_patterns
```

目标是学习结构，而不是原文改写。

---

## 11. Visual Analysis

统一字段：

```text
subject
main_colors
secondary_colors
style
composition
camera_angle
lighting
background
visual_focus
scene
mood
target_audience
notable_elements
reusable_visual_patterns
domain_attributes
confidence
```

---

## 12. Content Analysis

综合：

- 真实互动数据
- TextAnalysis
- VisualAnalysis

生成：

```text
why_it_may_be_popular
core_content_elements
core_visual_elements
target_audience
emotional_value
reusable_patterns
trend_tags
evidence
limitations
```

`why_it_may_be_popular` 属于 AI 推断，必须和客观数据分开。

---

## 13. Trend Analysis

趋势必须基于多个 ContentItem 聚合。

至少输出：

```text
hot_topics
rising_topics
visual_patterns
copywriting_patterns
audience_patterns
scenario_patterns
style_patterns
domain_patterns
```

当数据足够时可进一步输出：

```text
long_term_hot
rising
sudden_breakout
declining
newly_emerging
```

数据不足时必须明确说明。

---

## 14. Creative Concept

每个 Concept 建议包含：

```text
name
concept
target_audience
scenario
style
main_elements
trend_basis
differentiation
```

Concept 必须综合多个来源或趋势，不直接复刻单一内容。

---

## 15. Image Prompt Generator

系统不实际生成图片，只输出 Prompt。

每个 Concept 默认输出：

```text
hero_prompt
detail_prompt
lifestyle_prompt
cover_prompt
negative_prompt
```

Prompt 必须根据：

```text
topic
+
Visual Analysis
+
Trend Analysis
+
domain_attributes
```

动态决定描述维度。

---

## 16. 报告输出

每个任务：

```text
reports/{task_id}/
```

至少生成：

```text
report.md
report.json
prompts.md
```

`prompts.md` 只保留：

```text
Concept
Trend Basis
Hero Prompt
Detail Prompt
Lifestyle Prompt
Cover Prompt
Negative Prompt
```

---

## 17. 前端要求

前端固定：

```text
Vue 3 + TypeScript + Vite + Element Plus
```

第一版至少包含：

### ResearchTask 创建页

字段：

- Platform
- Topic
- Keywords
- Time Range
- Max Items
- Research Goals

### ResearchTask 列表页

展示：

- Task ID
- Platform
- Topic
- Status
- Created At
- Progress / Stage

### 系统配置页

第一版必须提供可视化配置页面。

至少包含：

```text
平台配置
AI Provider 配置
Prompt 模板
Ranking 参数
采集默认参数
```

要求：

- 所有可业务配置项在页面编辑；
- 保存到 SQLite；
- 支持启用/禁用；
- 支持恢复默认值；
- 敏感字段只显示掩码；
- 不要求用户修改配置文件。

### ResearchTask 详情页

至少包含 Tabs：

```text
概览
热门内容
Rising
爆款图片
文案分析
视觉分析
趋势
Creative Concepts
图片 Prompt
```

### 前端约束

- 使用 Pinia 管理必要状态
- 使用 Vue Router
- Axios 统一 API Client
- API 错误统一处理
- 不在组件中散落后端 URL
- 不实现复杂权限系统
- 不实现自动发布界面
- 不实现图片生成按钮
- UI 以研究工作台为目标，不做电商后台风格

---

## 18. API 原则

后端统一前缀建议：

```text
/api/v1
```

核心 API 逐阶段实现。

至少最终需要：

```text
POST /api/v1/research/tasks
GET  /api/v1/research/tasks
GET  /api/v1/research/tasks/{id}

POST /api/v1/research/tasks/{id}/run

GET /api/v1/research/tasks/{id}/contents
GET /api/v1/research/tasks/{id}/rankings
GET /api/v1/research/tasks/{id}/analysis
GET /api/v1/research/tasks/{id}/trends
GET /api/v1/research/tasks/{id}/concepts
GET /api/v1/research/tasks/{id}/prompts
GET /api/v1/research/tasks/{id}/report
```

不要为了 REST 形式过度拆分 API。

---

## 19. SQLite 要求

- 使用 SQLAlchemy 2.x 管理 ORM。
- 使用 Alembic 管理迁移。
- 默认数据库文件建议：

```text
data/app.db
```

- 数据库文件必须位于可迁移的数据目录中。
- 项目移动时，只要同时移动 `data/`，历史任务、配置和分析结果即可一起迁移。
- JSON 类字段使用 SQLAlchemy JSON 类型保存；不要依赖 PostgreSQL JSONB。
- 必须开启并正确处理 SQLite foreign keys。
- 合理建立索引。
- `ResearchTask`、`ContentItem`、`ContentMetricSnapshot` 必须有外键关系。
- ContentItem 去重优先考虑 `(platform, external_id)`，并结合任务范围设计。
- 对频繁过滤字段建立索引：
  - research_task_id
  - platform
  - published_at
  - collected_at
- 禁止在业务层随意拼原始 SQL。
- 必须考虑 SQLite 并发能力有限，第一版以单机、低并发研究任务为目标，不引入复杂并发写入模型。

---

## 20. 配置管理原则

除真正属于“程序运行时基础设施”的配置外，其余配置全部通过前端页面维护，并保存到 SQLite。

### 20.1 允许保留为系统级配置的内容

仅保留：

- 后端监听地址和端口
- 前端开发服务器端口
- SQLite 数据库文件路径
- 数据目录路径
- 日志级别
- 极少数启动时必须确定的运行参数

这些配置可以通过默认值、命令行参数或少量环境变量提供。

### 20.2 必须页面化并持久化的配置

以下内容不得要求用户手工编辑 `.env`、YAML 或 JSON 文件：

- 平台配置
- 平台名称
- 平台搜索 URL 模板
- Selector
- 页面解析规则
- 平台启用/禁用状态
- 默认采集数量
- 默认时间范围
- 请求/滚动间隔
- 浏览器 Headless 开关
- 浏览器超时时间
- 下载图片开关
- AI Provider 配置
- LLM Provider
- Vision Provider
- API Base URL
- 模型名称
- API Key
- 超时时间
- 最大重试次数
- Query Expansion Prompt
- Text Analysis Prompt
- Visual Analysis Prompt
- Trend Analysis Prompt
- Concept Prompt
- Image Prompt 模板
- Ranking 权重
- Freshness 参数
- Growth 参数
- 报告默认参数

这些配置必须：

```text
Vue 页面
↓
FastAPI Config API
↓
SQLite
```

### 20.3 敏感配置

API Key 等敏感数据仍保存于 SQLite，但：

- 前端读取时只返回掩码值；
- 不在日志中输出；
- API 返回不得泄露完整 Key；
- 更新时允许覆盖；
- 后端内部 Provider 使用时才读取完整值。

第一版不要求复杂密钥管理系统，但必须避免明显泄露。

### 20.4 配置领域模型

建议至少设计：

```text
AppSetting
PlatformConfig
AIProviderConfig
PromptTemplate
RankingConfig
```

可以根据实现合理合并，但不要把所有配置塞入一个无约束 JSON Blob。

---

## 21. Git 管理要求

整个项目必须使用 Git 管理。

Codex 在任何阶段开发时都必须遵守：

1. 项目根目录必须是 Git 仓库。
2. 如果尚未初始化，则执行：

```bash
git init
```

3. 必须提供合理 `.gitignore`。
4. 源代码、Alembic migration、文档、前端代码必须纳入 Git。
5. 运行时数据默认不提交：
   - `data/app.db`
   - `data/tasks/`
   - 下载图片
   - reports 运行产物
   - 日志
6. 提供示例目录或 `.gitkeep` 保留必要空目录。
7. 每个 Stage 完成后建议形成独立提交。
8. Codex 不得擅自改写 Git 历史、force push 或删除用户已有提交。
9. 如果当前工作区存在用户未提交修改，不得无关覆盖。
10. README 必须说明 Git 管理建议和数据迁移方式。

推荐阶段提交：

```text
feat: initialize content trend agent
feat: add configurable collection pipeline
feat: add ranking and ai analysis
feat: add concepts prompts and reports
```

---



## 22. 采集安全边界

只处理正常浏览过程中公开可见的信息。

遇到：

- 登录限制
- 验证码
- 访问验证
- 权限不足
- 平台阻止访问

系统应：

1. 记录状态；
2. 保存错误；
3. 停止对应步骤；
4. 返回可解释结果。

不要实现规避逻辑。

---

## 23. 推荐项目结构

```text
backend/
  app/
    api/
    core/
    models/
    schemas/
    repositories/
    browser/
    platforms/
    collectors/
    ranking/
    analysis/
    providers/
    prompts/
    reports/
    services/
    utils/
  tests/
  alembic/
  pyproject.toml

frontend/
  src/
    api/
    components/
    views/
    stores/
    router/
    types/
    utils/
  package.json

config/
data/
reports/
docs/
  stages/
```

---

## 24. 编码与测试要求

### 后端

- 全量类型注解
- Pydantic v2
- SQLAlchemy 2.x
- async 只用于确有 I/O 价值的位置
- 外部调用必须有 timeout
- AI Provider 重试次数有限
- 禁止 `print`
- 单条内容失败不能让整个任务失败
- 支持 `PARTIAL`

### 前端

- Vue 3 Composition API
- `<script setup lang="ts">`
- TypeScript
- Element Plus
- API 类型明确
- 组件不要包含大量业务请求逻辑

### 测试

后端：

```bash
uv run pytest
```

必须通过。

浏览器、LLM、VLM 单测使用 Mock，不依赖真实网站和真实模型 API。

前端至少保证：

```bash
npm run build
```

通过。

若配置 lint/test，则一并执行。

---

## 25. Orchestrator 原则

第一版使用简单：

```text
ResearchOrchestrator
```

串联：

```text
QueryExpansion
→ Collection
→ Ranking
→ Analysis
→ TrendAnalysis
→ ConceptGeneration
→ PromptGeneration
→ ReportGeneration
```

第一版不要强行引入 LangGraph。

只有未来出现明显复杂分支、动态工具调用、人工中断、多 Agent 协作时再评估。

---

## 26. Codex 工作方式

Codex 每次开发必须：

1. 阅读 `AGENTS.md`
2. 阅读当前阶段文档
3. 检查现有实现
4. 只实现当前阶段范围
5. 不提前大规模实现后续阶段
6. 运行后端测试
7. 若涉及前端，运行前端 build
8. 修复失败
9. 更新 README / 阶段状态
10. 输出变更摘要和测试结果

阶段顺序：

1. `STAGE_01_FOUNDATION.md`
2. `STAGE_02_COLLECTION.md`
3. `STAGE_03_ANALYSIS.md`
4. `STAGE_04_REPORT_FRONTEND.md`

禁止为了当前任务推翻前阶段已经稳定的架构。

---

## 27. 第一版最终验收

用户可以通过 Vue 3 前端创建：

```text
platform = 已支持平台
topic = 任意主题
keywords = 1～N 个关键词
```

系统能够：

```text
自动扩词
↓
采集公开内容
↓
保存 SQLite
↓
统一 ContentItem
↓
记录 MetricSnapshot
↓
Hot Ranking
↓
有历史快照时 Rising Ranking
↓
分析文章
↓
分析图片
↓
总结趋势
↓
生成 Creative Concept
↓
生成图片 Prompt
↓
输出 Markdown / JSON
↓
在 Vue 3 + Element Plus 页面展示
```

最终必须满足：

- 后端 FastAPI 正常启动
- SQLite 迁移正常
- `uv run pytest` 通过
- Vue 前端 `npm run build` 通过
- 核心模块不绑定平台
- 核心模块不绑定领域
- 项目已使用 Git 管理
- 业务配置可在前端页面维护并持久化到 SQLite
- 不实际调用图片生成模型
- 不自动发布
- 不包含绕过平台安全机制的能力

项目第一版最重要的判断标准：

> 是否能够从近期公开内容中发现有价值的趋势，并生成对后续创作有价值的 Prompt。
