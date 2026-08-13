# Stage 03 — Ranking & AI Analysis

## 目标

基于已经采集的真实数据实现热门内容筛选、Rising 检测、文章分析、图片分析和趋势聚合。

## 必须实现

### 页面化分析配置

本阶段新增的分析参数不得写死为系统配置文件。

必须通过页面配置并保存 SQLite：

- Ranking 权重
- Freshness 参数
- Growth 参数
- Text Analysis Prompt
- Visual Analysis Prompt
- Trend Analysis Prompt
- LLM Provider / Vision Provider
- 模型名
- API Base URL
- timeout
- retry

### Ranking Engine

至少计算：

```text
engagement_score
freshness_score
growth_score
hot_score
```

要求：

- 根据平台实际存在的指标动态计算
- 支持 like/favorite/comment/share/view
- 不存在的指标忽略
- 对大数值使用 log1p 或合理归一化
- 有多个 Snapshot 时计算 velocity
- 无历史 Snapshot 时 growth_score = null

榜单：

- Hot
- Rising
- Most Saved
- Most Discussed
- Most Shared
- Most Viewed

### LLM Text Analysis

输出：

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

### VLM Visual Analysis

实现 VisionProvider 和 MockVisionProvider。

输出：

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

### Content Analysis

综合：

- 互动数据
- 排名
- 文案分析
- 图片分析

输出：

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

### Trend Analysis

跨多个 ContentItem 聚合：

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

## API

至少：

```text
GET /api/v1/research/tasks/{id}/rankings
GET /api/v1/research/tasks/{id}/analysis
GET /api/v1/research/tasks/{id}/trends
```

## 前端

Task 详情增加 Tabs：

- Hot
- Rising
- 爆款图片
- 文案分析
- 视觉分析
- 趋势

图片分析页要能看到：

- 原图
- 来源内容
- 原始公开指标
- AI 视觉标签
- domain_attributes
- AI 分析说明

## 验收

- Ranking 单测
- Snapshot 增长测试
- Mock LLM/VLM 测试
- Pydantic 结构化输出验证
- 单条 AI 分析失败可继续
- 前端可查看完整分析
- `uv run pytest` 通过
- `npm run build` 通过

---

## 可直接给 Codex 的提示词

```text
请先阅读 AGENTS.md 和 docs/stages/STAGE_03_ANALYSIS.md。

基于 Stage 01、02 已有实现继续开发，不允许重写稳定的采集层。

现在实现 Stage 03：Ranking & AI Analysis。

总原则：
本阶段所有无需进程启动时确定的参数，全部通过 Vue 系统配置页管理并保存到 SQLite，不新增要求用户手工编辑 .env/YAML/JSON 的业务配置。

一、Ranking Engine

1. 实现 engagement_score。
2. 实现 freshness_score。
3. 实现 growth_score。
4. 实现 hot_score。
5. 根据 ContentItem 实际存在的互动指标动态参与评分。
6. 支持 like_count、favorite_count、comment_count、share_count、view_count。
7. 使用 log1p 或合理归一化避免头部绝对数值完全支配。
8. 根据 ContentMetricSnapshot 计算单位时间增长速度。
9. 没有足够 Snapshot 时 growth_score 必须为 null，禁止推测。
10. 输出 Hot、Rising、Most Saved、Most Discussed、Most Shared、Most Viewed。
11. 平台没有某指标则跳过对应榜单。
12. Ranking 权重、Freshness、Growth 参数从 SQLite RankingConfig 读取，并提供 Element Plus 配置页面。

二、Text Analysis

实现结构化 TextAnalysis：
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

Text Analysis Prompt 从 PromptTemplate 表读取并可在前端维护。
不要做原文简单改写。

三、Vision Analysis

1. 定义 VisionProvider。
2. 提供 MockVisionProvider。
3. AI Provider 配置从 SQLite 读取。
4. Provider 页面至少允许设置 Provider、模型名、API Base URL、API Key、timeout、retry、enabled。
5. API Key 查询只返回掩码，禁止写日志。
6. 对 ContentItem 本地图片进行视觉分析。
7. 输出通用 VisualAnalysis：
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
8. 行业字段只能进入 domain_attributes，不得写死进主 Schema。
9. Visual Analysis Prompt 从 SQLite 读取。

四、Content Analysis

综合真实互动数据、TextAnalysis、VisualAnalysis，输出：
why_it_may_be_popular
core_content_elements
core_visual_elements
target_audience
emotional_value
reusable_patterns
trend_tags
evidence
limitations

必须区分客观数据和 AI 推断。

五、Trend Analysis

对多个 ContentItem 聚合：
hot_topics
rising_topics
visual_patterns
copywriting_patterns
audience_patterns
scenario_patterns
style_patterns
domain_patterns

Trend Analysis Prompt 从 SQLite 读取。
数据不足时必须返回 insufficient_data 或明确 limitation。

六、API

实现：
GET /api/v1/research/tasks/{id}/rankings
GET /api/v1/research/tasks/{id}/analysis
GET /api/v1/research/tasks/{id}/trends

七、Vue 前端

ResearchTask 详情加入：
Hot
Rising
爆款图片
文案分析
视觉分析
趋势

系统配置页加入：
Ranking
LLM Provider
Vision Provider
Text Analysis Prompt
Visual Analysis Prompt
Trend Analysis Prompt

使用 Element Plus 完成清晰的数据展示。

八、测试

- Ranking 算法必须有单元测试。
- Growth 必须有 Snapshot 测试。
- LLM/VLM 使用 Mock 测试。
- 模型输出必须经过 Pydantic Schema 校验。
- 单条内容分析失败不得导致整个任务失败。
- SQLite 测试不得依赖外部数据库。
- 运行 uv run pytest。
- 运行 npm run build。
- 修复所有失败。

不要实现图片生成。
不要实现自动发布。
不要实现最终 Prompt/Report，留到 Stage 04。
不要破坏 Git 历史或覆盖用户无关修改。
```
