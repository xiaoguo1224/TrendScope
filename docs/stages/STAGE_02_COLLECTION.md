# Stage 02 — Collection

## 目标

实现 Query Expansion、Playwright 浏览器层、平台适配层和真实内容采集闭环。

本阶段关注“获取正确数据”，不做复杂 AI 内容分析。

## 必须实现

### 配置页面完善

本阶段必须把与采集和模型相关的可调参数全部页面化并保存到 SQLite。

至少包括：

- PlatformConfig
- search_url_template
- Selector / 解析规则
- 平台启用状态
- 默认采集数量
- 默认滚动/等待间隔
- Browser Headless
- Browser timeout
- 下载图片开关
- LLM Provider 基础配置
- Query Expansion Prompt

不得要求用户为了这些内容手工修改 `.env` 或 YAML/JSON。

### Query Expansion

输入：

- platform
- topic
- user keywords
- time range
- research goals

输出：

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

要求：

- 保留所有用户关键词
- AI 只能补充
- 有最大扩展数量
- 有 Mock LLMProvider
- 无 API Key 时系统仍可测试

### Browser

实现：

- PlaywrightBrowserAdapter
- open
- scroll
- extract_visible_content
- screenshot
- download_media

### Platform

实现平台注册机制：

```text
PlatformRegistry
```

第一版至少实现一个真实可运行的 PlatformAdapter，再保留 Generic Adapter 能力。

具体平台差异必须封装在 Adapter 内。

### Collection

实现：

```text
ResearchTask
→ Query Expansion
→ PlatformAdapter
→ BrowserAdapter
→ ContentItem
→ ContentMetricSnapshot
```

要求：

- 去重
- 单条失败继续
- 下载公开图片
- 保存本地路径
- 保存 raw_data
- 同一内容重新采集时写 MetricSnapshot
- 任务支持 PARTIAL

## API

至少：

```text
POST /api/v1/research/tasks/{id}/run

GET /api/v1/research/tasks/{id}/contents
```

任务详情返回当前状态和基础进度。

## 前端

详情页增加：

- 当前 Stage
- 当前状态
- 原始关键词
- 扩展关键词
- 已采集数量
- Content 列表
- 内容公开指标
- 图片缩略图
- 错误信息

提供“开始研究”按钮。

## 安全边界

仅采集正常浏览过程中公开可见信息。

遇到登录、验证码、访问验证、权限阻止时停止，不做规避。

## 验收

- 至少一个真实 PlatformAdapter 可完成基本搜索/解析
- Mock 测试完整
- ContentItem 写入 SQLite 文件数据库
- 图片可保存
- Snapshot 可生成
- `uv run pytest` 通过
- `npm run build` 通过

---

## 可直接给 Codex 的提示词

```text
请先阅读 AGENTS.md 和 docs/stages/STAGE_02_COLLECTION.md。

基于 Stage 01 已有代码继续开发，不要推翻现有架构。

现在只实现 Stage 02：Collection。

目标：
完成“用户 ResearchTask → 页面化配置 → 关键词扩展 → 浏览器采集 → PlatformAdapter 解析 → ContentItem → ContentMetricSnapshot”的闭环。

要求：

1. 延续 SQLite 文件数据库，不引入 PostgreSQL/MySQL。
2. 所有采集类、平台类和 Query Expansion 可调配置必须通过 Vue 页面维护并保存到 SQLite。
3. 不要求用户编辑 .env/YAML/JSON 来配置平台、Selector、Browser 参数或 Prompt。
4. 实现 LLMProvider 抽象和 MockLLMProvider。
5. AI Provider 基础配置从 SQLite 读取；API Key 前端读取时只返回掩码，日志不得输出完整 Key。
6. 实现 QueryExpansionService。
7. 用户原始关键词必须完整保留，AI 只允许补充。
8. 扩展关键词分类：
   core_keywords
   long_tail_keywords
   trend_keywords
   audience_keywords
   scenario_keywords
   style_keywords
9. 限制扩词数量。
10. Query Expansion Prompt 从 PromptTemplate 表读取，可在页面修改。
11. 实现 PlaywrightBrowserAdapter。
12. 业务 Service 不允许直接操作 Playwright。
13. Browser Headless、timeout、等待间隔、下载图片开关从数据库配置读取。
14. 实现 PlatformRegistry。
15. 至少实现一个真实可运行的 PlatformAdapter。
16. 平台搜索 URL、Selector、解析规则、启用状态等通过 PlatformConfig 页面管理并保存到 SQLite。
17. 平台 DOM、Selector、数据结构差异只能存在于 PlatformAdapter 或其配置中。
18. 实现 ContentCollectorService。
19. 统一转换成 ContentItem。
20. 内容去重。
21. 下载公开图片到 data/tasks/{task_id}/media/{content_id}/。
22. 保存 image_urls 和 local_image_paths。
23. 保存 raw_data。
24. 每次重新采集内容时写 ContentMetricSnapshot。
25. 单条内容失败不得让整个任务失败。
26. 支持 PARTIAL 状态。
27. 实现 POST /api/v1/research/tasks/{id}/run。
28. 实现 GET /api/v1/research/tasks/{id}/contents。
29. Vue 详情页展示扩展关键词、采集数量、内容列表、公开指标和图片。
30. 添加开始研究按钮。
31. 系统配置页补充平台配置、浏览器配置、LLM Provider 配置、Query Expansion Prompt 配置。
32. 只处理正常浏览公开可见信息。
33. 遇到验证码、登录限制、访问验证时记录状态并停止，不实现绕过。
34. 不实现 Ranking。
35. 不实现 Text/Vision Analysis。
36. 不实现 Trend/Concept/Prompt。
37. 运行 uv run pytest。
38. 运行 npm run build。
39. 修复所有失败。
40. 不覆盖用户已有 Git 历史和无关未提交修改。

最后给出：
- 实现摘要
- Git 变更摘要
- 页面化配置项
- 支持的平台 Adapter
- 采集数据流
- SQLite 数据库变化
- API
- 前端变化
- 测试结果
- 已知限制
```
