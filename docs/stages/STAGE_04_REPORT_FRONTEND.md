# Stage 04 — Concept, Prompt, Report & Final Frontend

## 目标

完成最终用户价值闭环：

```text
真实爆款数据
→ 图文分析
→ 趋势
→ Creative Concept
→ 图片 Prompt
→ Report
→ Vue 展示
```

系统仍然不实际生成图片，也不自动发布。

## 必须实现

### 最终配置页面

本阶段补齐最终页面化配置：

- Concept Prompt
- Image Prompt 模板
- Report 默认参数
- 默认 Concept 数量
- Prompt 输出语言/风格等业务参数

全部保存到 SQLite，不要求用户修改系统配置文件。

### Creative Concept Generator

默认生成 10～20 个：

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

要求：

- 综合多个趋势来源
- 不复刻单一内容
- trend_basis 能追溯到真实分析依据

### Image Prompt Generator

每个 Concept 输出：

```text
hero_prompt
detail_prompt
lifestyle_prompt
cover_prompt
negative_prompt
```

要求：

- 英文 Prompt 为主
- 可附中文解释
- 根据 topic + VisualAnalysis + TrendAnalysis + domain_attributes 动态生成
- 不把美甲、服装等行业字段写死
- 不调用图片生成模型

### Report Generator

生成：

```text
reports/{task_id}/report.md
reports/{task_id}/report.json
reports/{task_id}/prompts.md
```

`report.md` 至少包含：

1. 研究任务
2. 数据概览
3. 搜索关键词
4. Hot
5. Rising
6. 热门文章
7. 热门图片
8. 文案结构分析
9. 视觉结构分析
10. 爆款原因分析
11. 当前热门趋势
12. 近期上升趋势
13. 用户偏好
14. 可复用规律
15. 推荐创作方向
16. Creative Concepts
17. AI 图片 Prompt
18. 下一轮推荐关键词
19. 数据限制

### 前端最终页面

Task 详情至少包含：

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

Prompt 页面要求：

- Prompt Card
- 一键复制
- Hero / Detail / Lifestyle / Cover / Negative 分区
- 显示 Trend Basis
- 可按 Concept 切换
- 不提供“直接生成图片”按钮

报告页：

- 显示研究摘要
- 提供 Markdown 报告内容
- 可查看数据限制

## API

至少：

```text
GET /api/v1/research/tasks/{id}/concepts
GET /api/v1/research/tasks/{id}/prompts
GET /api/v1/research/tasks/{id}/report
```

可以增加重新生成 Concept/Prompt 的接口，但不能自动发布或生成图片。

## 最终验收

后端：

```bash
uv run pytest
```

通过。

前端：

```bash
npm run build
```

通过。

全链路：

```text
Create Task
→ Expand Query
→ Collect
→ Rank
→ Analyze Text
→ Analyze Images
→ Trend
→ Concept
→ Prompt
→ Report
→ Frontend Display
```

可以完成。

---

## 可直接给 Codex 的提示词

```text
请先阅读 AGENTS.md 和 docs/stages/STAGE_04_REPORT_FRONTEND.md。

基于前三阶段稳定代码完成最终 Stage 04。

目标：
把当前系统完成为一个真正可用的“通用 AI 内容趋势研究 Agent”。

总原则：
所有无需服务启动时确定的业务配置继续通过 Vue 页面维护并持久化到 SQLite。

一、Creative Concept

根据 Ranking、TextAnalysis、VisualAnalysis、TrendAnalysis 生成 10～20 个 CreativeConcept。

结构：
name
concept
target_audience
scenario
style
main_elements
trend_basis
differentiation

要求：
- 综合多个趋势来源。
- 不直接复刻单一内容。
- trend_basis 必须可以追溯到当前 ResearchTask 的真实趋势和分析结果。
- Concept Prompt 从 SQLite PromptTemplate 读取。
- 默认 Concept 数量可在页面配置。

二、Image Prompt Generator

每个 Concept 输出：
hero_prompt
detail_prompt
lifestyle_prompt
cover_prompt
negative_prompt

要求：
1. 英文 Prompt 为主，可附中文解释。
2. 根据 topic、VisualAnalysis、TrendAnalysis、domain_attributes 动态生成视觉描述。
3. 不允许写死美甲、女装、手机壳等行业 Schema。
4. 不调用任何图片生成模型。
5. 不实现图片生成 API。
6. Image Prompt 模板从 SQLite 读取并允许页面编辑。
7. Prompt 输出语言、默认风格等业务参数页面化。

三、Report Generator

生成：
reports/{task_id}/report.md
reports/{task_id}/report.json
reports/{task_id}/prompts.md

report.md 至少包含：
研究任务
数据概览
搜索关键词
Hot
Rising
热门文章
热门图片
文案结构分析
视觉结构分析
爆款原因分析
当前热门趋势
近期上升趋势
用户偏好
可复用规律
推荐创作方向
Creative Concepts
AI 图片 Prompt
下一轮推荐关键词
数据限制

prompts.md 只保留：
Concept
Trend Basis
Hero Prompt
Detail Prompt
Lifestyle Prompt
Cover Prompt
Negative Prompt

四、API

实现：
GET /api/v1/research/tasks/{id}/concepts
GET /api/v1/research/tasks/{id}/prompts
GET /api/v1/research/tasks/{id}/report

补齐最终配置 CRUD API。

五、Vue 3 + Element Plus 最终页面

ResearchTask 详情最终 Tabs：
概览
热门内容
Rising
爆款图片
文案分析
视觉分析
趋势
Creative Concepts
图片 Prompt

Prompt 页面：
- 使用 Element Plus Card。
- 每个 Concept 展示 Trend Basis。
- Hero / Detail / Lifestyle / Cover / Negative 分开展示。
- 每个 Prompt 提供一键复制。
- 不提供图片生成按钮。
- 不提供自动发布按钮。

系统配置页最终至少包括：
平台配置
浏览器配置
AI Provider 配置
Prompt 模板
Ranking 参数
采集默认参数
Report 默认参数

所有配置保存到 SQLite。

六、最终集成

检查完整链路：
Create Task
→ Expand Query
→ Collect
→ Rank
→ Analyze
→ Trend
→ Concept
→ Prompt
→ Report
→ Frontend

修复接口、类型、SQLite Schema 和前端之间的不一致。

检查数据迁移：
只复制项目代码 + data/app.db + 必要 data/tasks 文件，即可在另一目录继续使用历史任务和配置。

七、Git

1. 检查项目处于 Git 管理。
2. 检查 .gitignore。
3. 禁止提交 API Key、data/app.db、下载媒体、日志等运行数据。
4. 不改写已有 Git 历史。
5. 不覆盖用户无关未提交修改。

八、测试

运行：
uv run pytest

运行：
npm run build

如果项目已经配置 lint/test，也全部执行。

修复所有失败。

最后输出：
1. 完整功能清单
2. 完整数据流
3. SQLite 数据文件和迁移方式
4. 页面化配置清单
5. API 清单
6. 前端页面清单
7. Report 输出示例位置
8. Prompt 输出示例位置
9. Git 管理状态
10. 测试结果
11. 当前限制
12. 后续可扩展方向

禁止：
- 图片生成
- 自动发布
- 微服务化
- 重新推翻前三阶段稳定架构
```
