<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createAIProviderConfig, createPlatformConfig, createPromptTemplate, createRankingConfig, deleteAIProviderConfig, deletePlatformConfig, deletePromptTemplate, listAIProviderConfigs, listPlatformConfigs, listPromptTemplates, listRankingConfigs, listSettings, resetRankingConfig, resetSettings, testAIProviderConfig, testPlatformConfig, testSystemBrowserConnection, updateAIProviderConfig, updatePlatformConfig, updatePromptTemplate, updateRankingConfig, updateSetting } from '@/api/configuration'
import type { AIProviderConfig, AIProviderConfigTestResult, BrowserConnectionTestResult, PlatformConfig, PlatformConfigTestResult, PromptTemplate, RankingConfig } from '@/types'

type CommonPlatformSelectors = { resultContainer: string; contentLink: string; cover: string; searchTitle: string; searchAuthor: string; publishTime: string; searchLikeCount: string; detailTitle: string; detailContent: string; detailImage: string; detailAuthor: string; detailLikeCount: string; detailCollectCount: string; detailCommentCount: string }
type EditablePlatform = PlatformConfig & { selectorsText: string; parserRulesText: string; common: CommonPlatformSelectors }
type EditableProvider = AIProviderConfig & { savedKeyMask: string | null }

const saving = ref(false)
const loading = ref(true)
const collection = reactive({ max_items: 50, time_range: '7d', request_interval_ms: 1200, scroll_interval_ms: 1000 })
const browser = reactive({ mode: 'isolated' as 'isolated' | 'system_cdp', cdp_endpoint: 'http://127.0.0.1:9222', headless: true, timeout_seconds: 30, download_images: true, headers: {} as Record<string, string> })
const browserHeadersText = ref('')
const browserConnectionTesting = ref(false)
const browserConnectionResult = ref<BrowserConnectionTestResult | null>(null)
const reportDefaults = reactive({ concept_count: 12, prompt_language: 'English', prompt_style: 'editorial', include_markdown: true })
const ranking = reactive<RankingConfig>({ name: 'default', enabled: true, like_weight: 1, favorite_weight: 1.2, comment_weight: 1.5, share_weight: 1.5, view_weight: 0.1, freshness_half_life_hours: 72, growth_window_hours: 24 })
const platforms = ref<EditablePlatform[]>([])
const platformTesting = ref<number | null>(null)
const platformTestResults = reactive<Record<number, PlatformConfigTestResult>>({})
const providerTesting = ref<number | null>(null)
const providerTestResults = reactive<Record<number, AIProviderConfigTestResult>>({})
const providers = ref<EditableProvider[]>([])
const templates = ref<PromptTemplate[]>([])
const llmProviders = computed(() => providers.value.filter((item) => item.provider_type === 'llm'))
const visionProviders = computed(() => providers.value.filter((item) => item.provider_type === 'vision'))
type PromptPurpose = 'query_expansion' | 'text_analysis' | 'visual_analysis' | 'trend_analysis' | 'creative_concept' | 'image_prompt'
const promptGroups = computed(() => [
  { purpose: 'query_expansion' as const, label: 'Query Expansion', hint: '保留用户关键词，并补充可公开搜索的相关词。' },
  { purpose: 'text_analysis' as const, label: 'Text Analysis', hint: '分析文案结构和可复用规律，不复写原文。' },
  { purpose: 'visual_analysis' as const, label: 'Visual Analysis', hint: '分析通用视觉字段，领域特有结论写入 domain_attributes。' },
  { purpose: 'trend_analysis' as const, label: 'Trend Analysis', hint: '聚合多条内容，区分事实、推断和数据不足。' },
  { purpose: 'creative_concept' as const, label: 'Creative Concept', hint: '综合多个趋势并保留可追溯的 Trend Basis。' },
  { purpose: 'image_prompt' as const, label: 'Image Prompt', hint: '只生成文本 Prompt，不调用图片生成服务。' }
].map((group) => ({ ...group, templates: templates.value.filter((item) => item.purpose === group.purpose) })))
const rankingWeights = computed(() => [
  { label: '点赞权重', key: 'like_weight' as const }, { label: '收藏权重', key: 'favorite_weight' as const }, { label: '评论权重', key: 'comment_weight' as const }, { label: '分享权重', key: 'share_weight' as const }, { label: '浏览权重', key: 'view_weight' as const }
])

function formatJson(value: object): string { return JSON.stringify(value, null, 2) }
function formatHeaders(value: Record<string, string> | undefined): string { return Object.entries(value ?? {}).map(([name, headerValue]) => `${name}: ${headerValue}`).join('\n') }
function selectorGroup(selectors: PlatformConfig['selectors'], name: 'search' | 'detail'): Record<string, string> { const group = selectors[name]; return group && typeof group === 'object' ? group : {} }
function commonSelectors(selectors: PlatformConfig['selectors']): CommonPlatformSelectors {
  const search = selectorGroup(selectors, 'search'); const detail = selectorGroup(selectors, 'detail')
  return { resultContainer: search.result_container ?? (typeof selectors.item === 'string' ? selectors.item : ''), contentLink: search.content_link ?? '', cover: search.cover ?? '', searchTitle: search.title ?? (typeof selectors.field_title === 'string' ? selectors.field_title : ''), searchAuthor: search.author ?? '', publishTime: search.publish_time ?? '', searchLikeCount: search.like_count ?? '', detailTitle: detail.title ?? '', detailContent: detail.content ?? '', detailImage: detail.image ?? '', detailAuthor: detail.author ?? '', detailLikeCount: detail.like_count ?? '', detailCollectCount: detail.collect_count ?? '', detailCommentCount: detail.comment_count ?? '' }
}
function platformForEdit(item: PlatformConfig): EditablePlatform { return { ...item, selectorsText: formatJson(item.selectors), parserRulesText: formatJson(item.parser_rules), common: commonSelectors(item.selectors) } }
function providerForEdit(item: AIProviderConfig): EditableProvider { return { ...item, savedKeyMask: item.api_key ?? null, api_key: '' } }
function parseObject(value: string, field: string): Record<string, unknown> {
  try { const parsed: unknown = JSON.parse(value || '{}'); if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error(); return parsed as Record<string, unknown> } catch { throw new Error(`${field} 必须是合法的 JSON 对象`) }
}
function parseSelectors(value: string): PlatformConfig['selectors'] {
  const selectors = parseObject(value, 'Selector JSON')
  for (const item of Object.values(selectors)) {
    if (typeof item === 'string') continue
    if (!item || Array.isArray(item) || typeof item !== 'object' || Object.values(item).some((selector) => typeof selector !== 'string')) throw new Error('Selector JSON 的值必须是字符串或一层 Selector 对象')
  }
  return selectors as PlatformConfig['selectors']
}
function mergeCommonSelectors(item: EditablePlatform, selectors: PlatformConfig['selectors']): PlatformConfig['selectors'] {
  const search = { ...selectorGroup(selectors, 'search') }; const detail = { ...selectorGroup(selectors, 'detail') }; const common = item.common
  const put = (target: Record<string, string>, key: string, value: string): void => { if (value.trim()) target[key] = value.trim() }
  put(search, 'result_container', common.resultContainer); put(search, 'content_link', common.contentLink); put(search, 'cover', common.cover); put(search, 'title', common.searchTitle); put(search, 'author', common.searchAuthor); put(search, 'publish_time', common.publishTime); put(search, 'like_count', common.searchLikeCount)
  put(detail, 'title', common.detailTitle); put(detail, 'content', common.detailContent); put(detail, 'image', common.detailImage); put(detail, 'author', common.detailAuthor); put(detail, 'like_count', common.detailLikeCount); put(detail, 'collect_count', common.detailCollectCount); put(detail, 'comment_count', common.detailCommentCount)
  return { ...selectors, ...(Object.keys(search).length ? { search } : {}), ...(Object.keys(detail).length ? { detail } : {}) }
}
function syncCommonSelectors(item: EditablePlatform): void { item.common = commonSelectors(parseSelectors(item.selectorsText)) }
function parseHeaders(value: string): Record<string, string> {
  const source = value.trim()
  if (!source) return {}
  const parsed = source.startsWith('{') ? parseObject(source, '浏览器 Header') : Object.fromEntries(source.split(/\r?\n/).filter(Boolean).map((line) => {
    const separator = line.indexOf(':')
    if (separator <= 0) throw new Error('每个 Header 必须使用“名称: 值”格式')
    return [line.slice(0, separator).trim(), line.slice(separator + 1).trim()]
  }))
  const headers: Record<string, string> = {}
  for (const [name, headerValue] of Object.entries(parsed)) {
    if (!/^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$/.test(name) || typeof headerValue !== 'string' || /[\r\n]/.test(headerValue)) throw new Error('浏览器 Header 包含无效的名称或值')
    headers[name] = headerValue
  }
  return headers
}
function imageCount(value: unknown): string { return Array.isArray(value) ? `${value.length} 张` : '—' }
function providerTestDescription(result: AIProviderConfigTestResult): string { return `调用地址：${result.endpoint}${result.request_preview ? `；测试输入：${result.request_preview}` : ''}${result.response_preview ? `；模型输出：${result.response_preview}` : ''}` }

async function load(): Promise<void> {
  loading.value = true
  try {
    const [settings, rankings, platformItems, providerItems, templateItems] = await Promise.all([listSettings(), listRankingConfigs(), listPlatformConfigs(), listAIProviderConfigs(), listPromptTemplates()])
    Object.assign(collection, settings.find((item) => item.key === 'collection_defaults')?.value as Partial<typeof collection>)
    Object.assign(browser, settings.find((item) => item.key === 'browser_defaults')?.value as Partial<typeof browser>)
    browserHeadersText.value = formatHeaders(browser.headers)
    Object.assign(reportDefaults, settings.find((item) => item.key === 'report_defaults')?.value as Partial<typeof reportDefaults>)
    if (rankings[0]) Object.assign(ranking, rankings[0])
    platforms.value = platformItems.map(platformForEdit)
    providers.value = providerItems.map(providerForEdit)
    templates.value = templateItems
  } finally { loading.value = false }
}

async function saveDefaults(): Promise<void> {
  saving.value = true
  try {
    browser.headers = parseHeaders(browserHeadersText.value)
    const savedRanking = await Promise.all([updateSetting('collection_defaults', { ...collection }, 'Default collection parameters'), updateSetting('browser_defaults', { ...browser }, 'Default browser parameters'), updateSetting('report_defaults', { ...reportDefaults }, 'Report generation defaults'), ranking.id ? updateRankingConfig(ranking.id, ranking) : createRankingConfig(ranking)])
    if (!ranking.id) Object.assign(ranking, savedRanking[3])
    ElMessage.success('默认参数已保存到 SQLite')
  } finally { saving.value = false }
}
async function testBrowserConnection(): Promise<void> {
  browserConnectionTesting.value = true
  browserConnectionResult.value = null
  try {
    browser.headers = parseHeaders(browserHeadersText.value)
    await updateSetting('browser_defaults', { ...browser }, 'Default browser parameters')
    browserConnectionResult.value = await testSystemBrowserConnection()
    ElMessage[browserConnectionResult.value.success ? 'success' : 'warning'](browserConnectionResult.value.success ? '系统浏览器已连接' : '系统浏览器连接失败')
  } finally { browserConnectionTesting.value = false }
}
async function restoreDefaults(): Promise<void> { const [settings, defaultRanking] = await Promise.all([resetSettings(), resetRankingConfig()]); Object.assign(collection, settings.find((item) => item.key === 'collection_defaults')?.value); Object.assign(browser, settings.find((item) => item.key === 'browser_defaults')?.value); browserHeadersText.value = formatHeaders(browser.headers); Object.assign(reportDefaults, settings.find((item) => item.key === 'report_defaults')?.value); Object.assign(ranking, defaultRanking); ElMessage.success('默认配置已恢复') }
async function savePlatform(item: EditablePlatform): Promise<void> {
  const selectors = mergeCommonSelectors(item, parseSelectors(item.selectorsText))
  const parser_rules = parseObject(item.parserRulesText, '解析规则')
  const payload: PlatformConfig = { id: item.id, name: item.name, search_url_template: item.search_url_template || null, selectors, parser_rules, enabled: item.enabled }
  const saved = item.id ? await updatePlatformConfig(item.id, payload) : await createPlatformConfig(payload)
  const next = platformForEdit(saved); const index = platforms.value.indexOf(item); if (index === -1) platforms.value.push(next); else platforms.value[index] = next
  ElMessage.success('平台配置已保存')
}
async function runPlatformTest(item: EditablePlatform): Promise<void> {
  if (!item.id) { ElMessage.warning('请先保存平台配置，再执行测试'); return }
  platformTesting.value = item.id
  try { platformTestResults[item.id] = await testPlatformConfig(item.id); ElMessage[platformTestResults[item.id].success ? 'success' : 'warning'](platformTestResults[item.id].success ? '配置测试完成' : '配置测试未通过') } finally { platformTesting.value = null }
}
async function saveProvider(item: EditableProvider): Promise<void> {
  const payload: AIProviderConfig = { id: item.id, name: item.name, provider_type: item.provider_type, base_url: item.base_url || null, model_name: item.model_name || null, api_key: item.api_key || null, timeout_seconds: item.timeout_seconds, max_retries: item.max_retries, enabled: item.enabled }
  const saved = item.id ? await updateAIProviderConfig(item.id, payload) : await createAIProviderConfig(payload)
  const next = providerForEdit(saved); const index = providers.value.indexOf(item); if (index === -1) providers.value.push(next); else providers.value[index] = next
  ElMessage.success('AI Provider 配置已保存')
}
async function runProviderTest(item: EditableProvider): Promise<void> {
  if (!item.id) { ElMessage.warning('请先保存模型配置，再执行测试'); return }
  providerTesting.value = item.id
  try {
    providerTestResults[item.id] = await testAIProviderConfig(item.id)
    ElMessage[providerTestResults[item.id].success ? 'success' : 'warning'](providerTestResults[item.id].success ? '模型配置测试成功' : '模型配置测试未通过')
  } finally { providerTesting.value = null }
}
async function saveTemplate(item: PromptTemplate): Promise<void> { const saved = item.id ? await updatePromptTemplate(item.id, item) : await createPromptTemplate(item); const index = templates.value.indexOf(item); if (index === -1) templates.value.push(saved); else templates.value[index] = saved; ElMessage.success('Prompt 模板已保存') }
async function remove(item: PlatformConfig | AIProviderConfig | PromptTemplate, kind: 'platform' | 'provider' | 'template'): Promise<void> {
  if (!item.id) { if (kind === 'platform') platforms.value = platforms.value.filter((value) => value !== item); else if (kind === 'provider') providers.value = providers.value.filter((value) => value !== item); else templates.value = templates.value.filter((value) => value !== item); return }
  await ElMessageBox.confirm('删除后无法恢复，确认继续吗？', '确认删除', { type: 'warning' })
  if (kind === 'platform') { await deletePlatformConfig(item.id); platforms.value = platforms.value.filter((value) => value.id !== item.id) } else if (kind === 'provider') { await deleteAIProviderConfig(item.id); providers.value = providers.value.filter((value) => value.id !== item.id) } else { await deletePromptTemplate(item.id); templates.value = templates.value.filter((value) => value.id !== item.id) }
  ElMessage.success('配置已删除')
}
function addPlatform(): void { platforms.value.push({ name: '', search_url_template: null, selectors: {}, parser_rules: {}, enabled: true, selectorsText: '{}', parserRulesText: '{}', common: commonSelectors({}) }) }
function addProvider(providerType: 'llm' | 'vision'): void { providers.value.push({ name: '', provider_type: providerType, base_url: null, model_name: null, api_key: '', savedKeyMask: null, timeout_seconds: 60, max_retries: 2, enabled: false }) }
function addTemplate(purpose: PromptPurpose): void {
  const defaults: Record<typeof purpose, string> = {
    query_expansion: 'Expand the user-provided keywords. Preserve all original keywords and return categorized additions only.',
    text_analysis: 'Analyze the content structure. Return reusable patterns, not a rewrite of the original text.',
    visual_analysis: 'Analyze the image using the configured generic visual fields and place domain-specific observations in domain_attributes.',
    trend_analysis: 'Aggregate multiple content analyses. Distinguish evidence from inference and state limitations when data is insufficient.',
    creative_concept: 'Create distinct creative concepts from multiple current trends. Include a traceable trend_basis and avoid replicating any single source.',
    image_prompt: 'Create generic image prompts from the topic, visual trends, domain_attributes, and the current concept. Return Hero, Detail, Lifestyle, Cover, and Negative prompts.'
  }
  templates.value.push({ name: purpose.replace('_', '-'), purpose, template: defaults[purpose], enabled: true })
}

onMounted(load)
</script>

<template>
  <section v-loading="loading" class="page-card settings-page">
    <div class="page-header"><div><h1>系统配置</h1><p class="muted">同类配置集中管理并保存到 SQLite；密钥仅以掩码回显。</p></div><div><el-button @click="restoreDefaults">恢复默认值</el-button><el-button type="primary" :loading="saving" @click="saveDefaults">保存默认参数</el-button></div></div>
    <el-tabs type="border-card">
      <el-tab-pane label="采集与浏览器">
        <el-form label-width="170px"><el-form-item label="默认最大采集数"><el-input-number v-model="collection.max_items" :min="1" :max="500" /></el-form-item><el-form-item label="默认时间范围"><el-select v-model="collection.time_range"><el-option value="24h" label="近 24 小时" /><el-option value="7d" label="近 7 天" /><el-option value="30d" label="近 30 天" /></el-select></el-form-item><el-form-item label="请求间隔 (ms)"><el-input-number v-model="collection.request_interval_ms" :min="0" /></el-form-item><el-form-item label="滚动/等待间隔 (ms)"><el-input-number v-model="collection.scroll_interval_ms" :min="0" /></el-form-item></el-form>
        <el-divider content-position="left">Browser</el-divider>
        <el-form label-width="170px"><el-form-item label="浏览器模式"><el-radio-group v-model="browser.mode"><el-radio value="isolated">隔离 Playwright</el-radio><el-radio value="system_cdp">连接系统浏览器</el-radio></el-radio-group><div class="form-help">“连接系统浏览器”会复用专用 Chrome / Edge 配置目录中已登录的会话；不会读取或导出 Cookie。</div></el-form-item><el-form-item v-if="browser.mode === 'system_cdp'" label="本机 CDP 地址"><el-input v-model="browser.cdp_endpoint" placeholder="http://127.0.0.1:9222" /><div class="form-help">仅允许 localhost。请先按下方说明启动浏览器并完成手动登录；测试和研究任务都不会关闭该浏览器。</div></el-form-item><el-alert v-if="browser.mode === 'system_cdp'" class="browser-help" type="warning" :closable="false" title="首次登录：关闭 Chrome / Edge 后，用带 --remote-debugging-port 和独立 --user-data-dir 的命令启动；在新窗口手动登录目标平台，再保存并测试配置。" /><div v-if="browser.mode === 'system_cdp'" class="browser-connection-test"><el-button type="primary" plain :loading="browserConnectionTesting" @click="testBrowserConnection">测试系统浏览器连接</el-button><el-alert v-if="browserConnectionResult" class="browser-connection-result" :type="browserConnectionResult.success ? 'success' : 'error'" :closable="false" :title="browserConnectionResult.success ? '系统浏览器连接成功' : '系统浏览器连接失败'" :description="browserConnectionResult.message" /></div><el-form-item label="无头模式" v-if="browser.mode === 'isolated'"><el-switch v-model="browser.headless" /></el-form-item><el-form-item label="超时时间 (秒)"><el-input-number v-model="browser.timeout_seconds" :min="1" :max="600" /></el-form-item><el-form-item label="下载公开图片"><el-switch v-model="browser.download_images" /></el-form-item><el-form-item label="请求 Header"><el-input v-model="browserHeadersText" type="textarea" :rows="5" placeholder="Cookie: session=value&#10;Authorization: Bearer token" /><div class="form-help">每行一个“名称: 值”，也可粘贴 JSON 对象；留空代表不发送任何自定义 Header。已保存的 Cookie/Token 会以掩码显示，不编辑可保留，删除该行后保存则清空。</div></el-form-item></el-form>
      </el-tab-pane>
      <el-tab-pane label="排名与报告">
        <el-alert type="info" :closable="false" title="Ranking 参数用于 Hot、Rising 与指标榜单；报告参数控制 Concept 与文本 Prompt 输出。" />
        <el-form label-width="170px" class="form-top"><el-form-item label="启用默认 Ranking"><el-switch v-model="ranking.enabled" /></el-form-item><el-form-item v-for="item in rankingWeights" :key="item.key" :label="item.label"><el-input-number v-model="ranking[item.key]" :step="0.1" /></el-form-item><el-form-item label="新鲜度半衰期 (小时)"><el-input-number v-model="ranking.freshness_half_life_hours" :min="1" /></el-form-item><el-form-item label="增长窗口 (小时)"><el-input-number v-model="ranking.growth_window_hours" :min="1" /></el-form-item></el-form>
        <el-divider content-position="left">Report</el-divider>
        <el-form label-width="170px"><el-form-item label="默认 Concept 数量"><el-input-number v-model="reportDefaults.concept_count" :min="10" :max="20" /></el-form-item><el-form-item label="Prompt 输出语言"><el-select v-model="reportDefaults.prompt_language"><el-option label="English" value="English" /><el-option label="中文" value="Chinese" /><el-option label="中英双语" value="Bilingual" /></el-select></el-form-item><el-form-item label="默认 Prompt 风格"><el-input v-model="reportDefaults.prompt_style" placeholder="例如 editorial、minimal、cinematic" /></el-form-item><el-form-item label="生成 Markdown 报告"><el-switch v-model="reportDefaults.include_markdown" /></el-form-item></el-form>
      </el-tab-pane>
      <el-tab-pane label="平台配置">
        <el-alert type="info" :closable="false" title="常用字段可直接填写；复杂页面结构再展开高级配置。仅启用的平台可在创建研究任务时选择。" />
        <el-button class="add-button" @click="addPlatform">新增平台</el-button>
        <el-card v-for="item in platforms" :key="item.id ?? item.name" class="config-card">
          <el-form label-width="150px"><el-form-item label="平台名称"><el-input v-model="item.name" placeholder="例如 xiaohongshu" /></el-form-item><el-form-item label="搜索地址"><el-input v-model="item.search_url_template" placeholder="https://example.com/search?q={query}" /></el-form-item></el-form>
          <el-divider content-position="left">搜索结果选择器</el-divider>
          <el-form label-width="150px"><el-form-item label="内容 Card"><el-input v-model="item.common.resultContainer" placeholder="section.note-item" /></el-form-item><el-form-item label="详情链接"><el-input v-model="item.common.contentLink" placeholder="a[href*='/explore/']" /></el-form-item><el-form-item label="封面"><el-input v-model="item.common.cover" placeholder=".cover img" /></el-form-item><el-form-item label="标题"><el-input v-model="item.common.searchTitle" placeholder=".title" /></el-form-item><el-form-item label="作者"><el-input v-model="item.common.searchAuthor" placeholder=".author .name" /></el-form-item><el-form-item label="发布时间"><el-input v-model="item.common.publishTime" placeholder=".author .time" /></el-form-item><el-form-item label="点赞"><el-input v-model="item.common.searchLikeCount" placeholder=".like-wrapper .count" /></el-form-item></el-form>
          <el-divider content-position="left">详情页选择器</el-divider>
          <el-form label-width="150px"><el-form-item label="标题"><el-input v-model="item.common.detailTitle" placeholder="#detail-title, .title" /></el-form-item><el-form-item label="正文"><el-input v-model="item.common.detailContent" placeholder="#detail-desc, .desc" /></el-form-item><el-form-item label="图片"><el-input v-model="item.common.detailImage" placeholder=".note-slider-img, .swiper-slide img" /></el-form-item><el-form-item label="作者"><el-input v-model="item.common.detailAuthor" placeholder=".author-wrapper .username, .username" /></el-form-item><el-form-item label="点赞"><el-input v-model="item.common.detailLikeCount" placeholder=".like-wrapper .count" /></el-form-item><el-form-item label="收藏"><el-input v-model="item.common.detailCollectCount" placeholder=".collect-wrapper .count" /></el-form-item><el-form-item label="评论"><el-input v-model="item.common.detailCommentCount" placeholder=".chat-wrapper .count" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item></el-form>
          <el-collapse><el-collapse-item title="高级配置" name="advanced"><el-form label-width="150px"><el-form-item label="Selector JSON"><el-input v-model="item.selectorsText" type="textarea" :rows="12" placeholder='{"search": {"result_container": "section.note-item"}, "detail": {"content": ".desc"}}' @blur="syncCommonSelectors(item)" /></el-form-item><el-form-item label="解析规则 JSON"><el-input v-model="item.parserRulesText" type="textarea" :rows="12" placeholder='{"title": {"source": "title", "type": "text"}}' /></el-form-item></el-form></el-collapse-item></el-collapse>
          <div class="platform-actions"><el-button type="primary" @click="savePlatform(item)">保存</el-button><el-button :loading="platformTesting === item.id" :disabled="!item.id" @click="runPlatformTest(item)">测试配置</el-button><el-button @click="remove(item, 'platform')">删除</el-button></div>
          <el-alert v-if="item.id && platformTestResults[item.id]" class="test-result" :type="platformTestResults[item.id].success ? 'success' : 'error'" :closable="false" :title="platformTestResults[item.id].success ? '配置测试成功' : '配置测试未通过'" :description="platformTestResults[item.id].message ?? undefined" />
          <el-descriptions v-if="item.id && platformTestResults[item.id]?.success" :column="1" border class="test-result"><el-descriptions-item label="已解析搜索结果">{{ platformTestResults[item.id].search_result_count }} 条</el-descriptions-item><el-descriptions-item label="第一条">{{ platformTestResults[item.id].first_result?.title ?? '未找到结果' }}</el-descriptions-item><el-descriptions-item label="第一条作者">{{ platformTestResults[item.id].first_result?.author_name ?? '—' }}</el-descriptions-item><el-descriptions-item label="第一条 URL">{{ platformTestResults[item.id].first_result?.url ?? '—' }}</el-descriptions-item><el-descriptions-item label="详情正文">{{ platformTestResults[item.id].detail_result?.text ? '✅' : '—' }}</el-descriptions-item><el-descriptions-item label="详情图片">{{ imageCount(platformTestResults[item.id].detail_result?.image_urls) }}</el-descriptions-item><el-descriptions-item label="详情收藏 / 评论">{{ platformTestResults[item.id].detail_result?.favorite_count ?? '—' }} / {{ platformTestResults[item.id].detail_result?.comment_count ?? '—' }}</el-descriptions-item></el-descriptions>
        </el-card>
      </el-tab-pane>
      <el-tab-pane label="AI Provider">
        <el-alert type="info" :closable="false" title="LLM 与 Vision Provider 在同一处维护。Base URL 的路径决定适配器：支持 OpenAI 兼容（/v1、/responses、/chat 或 /chat/completions）、Anthropic（/messages）、Gemini（:generateContent）和 Ollama（/api/chat、/api/generate）。不需要另选调用协议；API Key 只以掩码回显。" />
        <el-divider content-position="left">LLM Provider</el-divider><el-button class="add-button" @click="addProvider('llm')">新增 LLM Provider</el-button><el-card v-for="item in llmProviders" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="Base URL"><el-input v-model="item.base_url" /></el-form-item><el-form-item label="模型"><el-input v-model="item.model_name" /></el-form-item><el-form-item label="API Key"><el-input v-model="item.api_key" show-password :placeholder="item.savedKeyMask ? `已保存：${item.savedKeyMask}；留空不覆盖` : '请输入 API Key'" /></el-form-item><el-form-item label="超时 (秒)"><el-input-number v-model="item.timeout_seconds" :min="1" :max="600" /></el-form-item><el-form-item label="最大重试次数"><el-input-number v-model="item.max_retries" :min="0" :max="10" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="saveProvider(item)">保存</el-button><el-button :loading="providerTesting === item.id" @click="runProviderTest(item)">测试模型配置</el-button><el-button @click="remove(item, 'provider')">删除</el-button><el-alert v-if="item.id && providerTestResults[item.id]" class="provider-test-result" :type="providerTestResults[item.id].success ? 'success' : 'error'" :closable="false" :title="providerTestResults[item.id].message" :description="providerTestDescription(providerTestResults[item.id])" /></el-form></el-card>
        <el-divider content-position="left">Vision Provider</el-divider><el-button class="add-button" @click="addProvider('vision')">新增 Vision Provider</el-button><el-card v-for="item in visionProviders" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="Base URL"><el-input v-model="item.base_url" /></el-form-item><el-form-item label="模型"><el-input v-model="item.model_name" /></el-form-item><el-form-item label="API Key"><el-input v-model="item.api_key" show-password :placeholder="item.savedKeyMask ? `已保存：${item.savedKeyMask}；留空不覆盖` : '请输入 API Key'" /></el-form-item><el-form-item label="超时 (秒)"><el-input-number v-model="item.timeout_seconds" :min="1" :max="600" /></el-form-item><el-form-item label="最大重试次数"><el-input-number v-model="item.max_retries" :min="0" :max="10" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="saveProvider(item)">保存</el-button><el-button :loading="providerTesting === item.id" @click="runProviderTest(item)">测试模型配置</el-button><el-button @click="remove(item, 'provider')">删除</el-button><el-alert v-if="item.id && providerTestResults[item.id]" class="provider-test-result" :type="providerTestResults[item.id].success ? 'success' : 'error'" :closable="false" :title="providerTestResults[item.id].message" :description="providerTestDescription(providerTestResults[item.id])" /></el-form></el-card>
      </el-tab-pane>
      <el-tab-pane label="Prompt 模板"><el-alert type="info" :closable="false" title="所有 Prompt 模板集中维护；每类仅会读取已启用的模板。" /><el-collapse class="form-top"><el-collapse-item v-for="group in promptGroups" :key="group.purpose" :name="group.purpose" :title="group.label"><p class="muted">{{ group.hint }}</p><el-button class="add-button" @click="addTemplate(group.purpose)">新增 {{ group.label }} 模板</el-button><el-card v-for="item in group.templates" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="模板"><el-input v-model="item.template" type="textarea" :rows="7" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="saveTemplate(item)">保存</el-button><el-button @click="remove(item, 'template')">删除</el-button></el-form></el-card></el-collapse-item></el-collapse></el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.settings-page { max-width: 1100px; }
.config-card { margin-top: 16px; }
.add-button { margin-top: 16px; }
.form-top { margin-top: 20px; }
.form-help { color: var(--el-text-color-secondary); font-size: 12px; line-height: 1.5; margin-top: 6px; }
.browser-help { margin: 0 0 18px 0; }
.browser-connection-test { margin: 0 0 18px 170px; }
.browser-connection-result { margin-top: 10px; max-width: 680px; }
.provider-test-result { margin-top: 14px; }
.platform-actions { display: flex; gap: 12px; margin-top: 16px; }
.test-result { margin-top: 16px; }
</style>
