<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { createAIProviderConfig, createPlatformConfig, createPromptTemplate, createRankingConfig, deleteAIProviderConfig, deletePlatformConfig, deletePromptTemplate, listAIProviderConfigs, listPlatformConfigs, listPromptTemplates, listRankingConfigs, listSettings, resetRankingConfig, resetSettings, updateAIProviderConfig, updatePlatformConfig, updatePromptTemplate, updateRankingConfig, updateSetting } from '@/api/configuration'
import type { AIProviderConfig, PlatformConfig, PromptTemplate, RankingConfig } from '@/types'

type EditablePlatform = PlatformConfig & { selectorsText: string; parserRulesText: string }
type EditableProvider = AIProviderConfig & { savedKeyMask: string | null }

const saving = ref(false)
const loading = ref(true)
const collection = reactive({ max_items: 50, time_range: '7d', request_interval_ms: 1200, scroll_interval_ms: 1000 })
const browser = reactive({ headless: true, timeout_seconds: 30, download_images: true })
const reportDefaults = reactive({ concept_count: 12, prompt_language: 'English', prompt_style: 'editorial', include_markdown: true })
const ranking = reactive<RankingConfig>({ name: 'default', enabled: true, like_weight: 1, favorite_weight: 1.2, comment_weight: 1.5, share_weight: 1.5, view_weight: 0.1, freshness_half_life_hours: 72, growth_window_hours: 24 })
const platforms = ref<EditablePlatform[]>([])
const providers = ref<EditableProvider[]>([])
const templates = ref<PromptTemplate[]>([])
const llmProviders = computed(() => providers.value.filter((item) => item.provider_type === 'llm'))
const visionProviders = computed(() => providers.value.filter((item) => item.provider_type === 'vision'))
const queryTemplates = computed(() => templates.value.filter((item) => item.purpose === 'query_expansion'))
const textTemplates = computed(() => templates.value.filter((item) => item.purpose === 'text_analysis'))
const visualTemplates = computed(() => templates.value.filter((item) => item.purpose === 'visual_analysis'))
const trendTemplates = computed(() => templates.value.filter((item) => item.purpose === 'trend_analysis'))
const conceptTemplates = computed(() => templates.value.filter((item) => item.purpose === 'creative_concept'))
const imagePromptTemplates = computed(() => templates.value.filter((item) => item.purpose === 'image_prompt'))
const rankingWeights = computed(() => [
  { label: '点赞权重', key: 'like_weight' as const }, { label: '收藏权重', key: 'favorite_weight' as const }, { label: '评论权重', key: 'comment_weight' as const }, { label: '分享权重', key: 'share_weight' as const }, { label: '浏览权重', key: 'view_weight' as const }
])

function formatJson(value: object): string { return JSON.stringify(value, null, 2) }
function platformForEdit(item: PlatformConfig): EditablePlatform { return { ...item, selectorsText: formatJson(item.selectors), parserRulesText: formatJson(item.parser_rules) } }
function providerForEdit(item: AIProviderConfig): EditableProvider { return { ...item, savedKeyMask: item.api_key ?? null, api_key: '' } }
function parseObject(value: string, field: string): Record<string, unknown> {
  try { const parsed: unknown = JSON.parse(value || '{}'); if (!parsed || Array.isArray(parsed) || typeof parsed !== 'object') throw new Error(); return parsed as Record<string, unknown> } catch { throw new Error(`${field} 必须是合法的 JSON 对象`) }
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [settings, rankings, platformItems, providerItems, templateItems] = await Promise.all([listSettings(), listRankingConfigs(), listPlatformConfigs(), listAIProviderConfigs(), listPromptTemplates()])
    Object.assign(collection, settings.find((item) => item.key === 'collection_defaults')?.value as Partial<typeof collection>)
    Object.assign(browser, settings.find((item) => item.key === 'browser_defaults')?.value as Partial<typeof browser>)
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
    const savedRanking = await Promise.all([updateSetting('collection_defaults', { ...collection }, 'Default collection parameters'), updateSetting('browser_defaults', { ...browser }, 'Default browser parameters'), updateSetting('report_defaults', { ...reportDefaults }, 'Report generation defaults'), ranking.id ? updateRankingConfig(ranking.id, ranking) : createRankingConfig(ranking)])
    if (!ranking.id) Object.assign(ranking, savedRanking[3])
    ElMessage.success('默认参数已保存到 SQLite')
  } finally { saving.value = false }
}
async function restoreDefaults(): Promise<void> { const [settings, defaultRanking] = await Promise.all([resetSettings(), resetRankingConfig()]); Object.assign(collection, settings.find((item) => item.key === 'collection_defaults')?.value); Object.assign(browser, settings.find((item) => item.key === 'browser_defaults')?.value); Object.assign(reportDefaults, settings.find((item) => item.key === 'report_defaults')?.value); Object.assign(ranking, defaultRanking); ElMessage.success('默认配置已恢复') }
async function savePlatform(item: EditablePlatform): Promise<void> {
  const selectors = parseObject(item.selectorsText, 'Selector') as Record<string, string>
  const parser_rules = parseObject(item.parserRulesText, '解析规则')
  const payload: PlatformConfig = { id: item.id, name: item.name, search_url_template: item.search_url_template || null, selectors, parser_rules, enabled: item.enabled }
  const saved = item.id ? await updatePlatformConfig(item.id, payload) : await createPlatformConfig(payload)
  const next = platformForEdit(saved); const index = platforms.value.indexOf(item); if (index === -1) platforms.value.push(next); else platforms.value[index] = next
  ElMessage.success('平台配置已保存')
}
async function saveProvider(item: EditableProvider): Promise<void> {
  const payload: AIProviderConfig = { id: item.id, name: item.name, provider_type: item.provider_type, base_url: item.base_url || null, model_name: item.model_name || null, api_key: item.api_key || null, timeout_seconds: item.timeout_seconds, max_retries: item.max_retries, enabled: item.enabled }
  const saved = item.id ? await updateAIProviderConfig(item.id, payload) : await createAIProviderConfig(payload)
  const next = providerForEdit(saved); const index = providers.value.indexOf(item); if (index === -1) providers.value.push(next); else providers.value[index] = next
  ElMessage.success('AI Provider 配置已保存')
}
async function saveTemplate(item: PromptTemplate): Promise<void> { const saved = item.id ? await updatePromptTemplate(item.id, item) : await createPromptTemplate(item); const index = templates.value.indexOf(item); if (index === -1) templates.value.push(saved); else templates.value[index] = saved; ElMessage.success('Prompt 模板已保存') }
async function remove(item: PlatformConfig | AIProviderConfig | PromptTemplate, kind: 'platform' | 'provider' | 'template'): Promise<void> {
  if (!item.id) { if (kind === 'platform') platforms.value = platforms.value.filter((value) => value !== item); else if (kind === 'provider') providers.value = providers.value.filter((value) => value !== item); else templates.value = templates.value.filter((value) => value !== item); return }
  await ElMessageBox.confirm('删除后无法恢复，确认继续吗？', '确认删除', { type: 'warning' })
  if (kind === 'platform') { await deletePlatformConfig(item.id); platforms.value = platforms.value.filter((value) => value.id !== item.id) } else if (kind === 'provider') { await deleteAIProviderConfig(item.id); providers.value = providers.value.filter((value) => value.id !== item.id) } else { await deletePromptTemplate(item.id); templates.value = templates.value.filter((value) => value.id !== item.id) }
  ElMessage.success('配置已删除')
}
function addPlatform(): void { platforms.value.push({ name: '', search_url_template: null, selectors: {}, parser_rules: {}, enabled: true, selectorsText: '{}', parserRulesText: '{}' }) }
function addProvider(providerType: 'llm' | 'vision'): void { providers.value.push({ name: '', provider_type: providerType, base_url: null, model_name: null, api_key: '', savedKeyMask: null, timeout_seconds: 60, max_retries: 2, enabled: false }) }
function addTemplate(purpose: 'query_expansion' | 'text_analysis' | 'visual_analysis' | 'trend_analysis' | 'creative_concept' | 'image_prompt'): void {
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
    <div class="page-header"><div><h1>系统配置</h1><p class="muted">采集与模型业务配置保存到 SQLite；API Key 仅以掩码回显。</p></div><div><el-button @click="restoreDefaults">恢复默认值</el-button><el-button type="primary" :loading="saving" @click="saveDefaults">保存默认参数</el-button></div></div>
    <el-tabs type="border-card">
      <el-tab-pane label="采集默认参数"><el-form label-width="170px"><el-form-item label="默认最大采集数"><el-input-number v-model="collection.max_items" :min="1" :max="500" /></el-form-item><el-form-item label="默认时间范围"><el-select v-model="collection.time_range"><el-option value="24h" label="近 24 小时" /><el-option value="7d" label="近 7 天" /><el-option value="30d" label="近 30 天" /></el-select></el-form-item><el-form-item label="请求间隔 (ms)"><el-input-number v-model="collection.request_interval_ms" :min="0" /></el-form-item><el-form-item label="滚动/等待间隔 (ms)"><el-input-number v-model="collection.scroll_interval_ms" :min="0" /></el-form-item></el-form></el-tab-pane>
      <el-tab-pane label="Browser 默认参数"><el-form label-width="170px"><el-form-item label="无头模式"><el-switch v-model="browser.headless" /></el-form-item><el-form-item label="超时时间 (秒)"><el-input-number v-model="browser.timeout_seconds" :min="1" :max="600" /></el-form-item><el-form-item label="下载公开图片"><el-switch v-model="browser.download_images" /></el-form-item></el-form></el-tab-pane>
      <el-tab-pane label="Ranking 默认参数"><el-alert type="info" :closable="false" title="用于 Hot、Rising 与互动指标榜单；保存后由后端 Ranking Engine 读取。" /><el-form label-width="170px" class="form-top"><el-form-item label="启用默认规则"><el-switch v-model="ranking.enabled" /></el-form-item><el-form-item v-for="item in rankingWeights" :key="item.key" :label="item.label"><el-input-number v-model="ranking[item.key]" :step="0.1" /></el-form-item><el-form-item label="新鲜度半衰期 (小时)"><el-input-number v-model="ranking.freshness_half_life_hours" :min="1" /></el-form-item><el-form-item label="增长窗口 (小时)"><el-input-number v-model="ranking.growth_window_hours" :min="1" /></el-form-item></el-form></el-tab-pane>
      <el-tab-pane label="Report 默认参数"><el-alert type="info" :closable="false" title="控制 Concept 数量和图片 Prompt 的输出偏好；保存后由报告与 Prompt 生成流程读取。" /><el-form label-width="170px" class="form-top"><el-form-item label="默认 Concept 数量"><el-input-number v-model="reportDefaults.concept_count" :min="10" :max="20" /></el-form-item><el-form-item label="Prompt 输出语言"><el-select v-model="reportDefaults.prompt_language"><el-option label="English" value="English" /><el-option label="中文" value="Chinese" /><el-option label="中英双语" value="Bilingual" /></el-select></el-form-item><el-form-item label="默认 Prompt 风格"><el-input v-model="reportDefaults.prompt_style" placeholder="例如 editorial、minimal、cinematic" /></el-form-item><el-form-item label="生成 Markdown 报告"><el-switch v-model="reportDefaults.include_markdown" /></el-form-item></el-form></el-tab-pane>
      <el-tab-pane label="平台配置"><el-alert type="info" :closable="false" title="平台的搜索 URL、DOM Selector 与解析规则均在此维护。" /><el-button class="add-button" @click="addPlatform">新增平台</el-button><el-card v-for="item in platforms" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="平台名称"><el-input v-model="item.name" placeholder="例如 generic-web" /></el-form-item><el-form-item label="搜索 URL 模板"><el-input v-model="item.search_url_template" placeholder="https://example.com/search?q={query}" /></el-form-item><el-form-item label="Selector JSON"><el-input v-model="item.selectorsText" type="textarea" :rows="5" placeholder='{"result": ".card", "title": "h2"}' /></el-form-item><el-form-item label="解析规则 JSON"><el-input v-model="item.parserRulesText" type="textarea" :rows="5" placeholder='{"title": "text", "likes": "number"}' /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="savePlatform(item)">保存</el-button><el-button @click="remove(item, 'platform')">删除</el-button></el-form></el-card></el-tab-pane>
      <el-tab-pane label="LLM Provider"><el-alert type="info" :closable="false" title="Text 与 Trend 分析会读取已启用的 LLM 配置；当前未接入供应商客户端时会安全降级到 Mock。API Key 只以掩码回显。" /><el-button class="add-button" @click="addProvider('llm')">新增 LLM Provider</el-button><el-card v-for="item in llmProviders" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="Base URL"><el-input v-model="item.base_url" /></el-form-item><el-form-item label="模型"><el-input v-model="item.model_name" /></el-form-item><el-form-item label="API Key"><el-input v-model="item.api_key" show-password :placeholder="item.savedKeyMask ? `已保存：${item.savedKeyMask}；留空不覆盖` : '请输入 API Key'" /></el-form-item><el-form-item label="超时 (秒)"><el-input-number v-model="item.timeout_seconds" :min="1" :max="600" /></el-form-item><el-form-item label="最大重试次数"><el-input-number v-model="item.max_retries" :min="0" :max="10" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="saveProvider(item)">保存</el-button><el-button @click="remove(item, 'provider')">删除</el-button></el-form></el-card></el-tab-pane>
      <el-tab-pane label="Vision Provider"><el-alert type="info" :closable="false" title="图片视觉分析会读取已启用的 Vision 配置；当前未接入供应商客户端时会安全降级到 Mock，密钥不明文回显。" /><el-button class="add-button" @click="addProvider('vision')">新增 Vision Provider</el-button><el-card v-for="item in visionProviders" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="Base URL"><el-input v-model="item.base_url" /></el-form-item><el-form-item label="模型"><el-input v-model="item.model_name" /></el-form-item><el-form-item label="API Key"><el-input v-model="item.api_key" show-password :placeholder="item.savedKeyMask ? `已保存：${item.savedKeyMask}；留空不覆盖` : '请输入 API Key'" /></el-form-item><el-form-item label="超时 (秒)"><el-input-number v-model="item.timeout_seconds" :min="1" :max="600" /></el-form-item><el-form-item label="最大重试次数"><el-input-number v-model="item.max_retries" :min="0" :max="10" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="saveProvider(item)">保存</el-button><el-button @click="remove(item, 'provider')">删除</el-button></el-form></el-card></el-tab-pane>
      <el-tab-pane label="Text Analysis Prompt"><el-alert type="info" :closable="false" title="Text Analysis 使用 purpose = text_analysis 的已启用模板。" /><el-button class="add-button" @click="addTemplate('text_analysis')">新增 Text 模板</el-button><el-card v-for="item in textTemplates" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="模板"><el-input v-model="item.template" type="textarea" :rows="7" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="saveTemplate(item)">保存</el-button><el-button @click="remove(item, 'template')">删除</el-button></el-form></el-card></el-tab-pane>
      <el-tab-pane label="Visual Analysis Prompt"><el-alert type="info" :closable="false" title="Visual Analysis 使用 purpose = visual_analysis 的已启用模板；领域特有结论应输出到 domain_attributes。" /><el-button class="add-button" @click="addTemplate('visual_analysis')">新增 Visual 模板</el-button><el-card v-for="item in visualTemplates" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="模板"><el-input v-model="item.template" type="textarea" :rows="7" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="saveTemplate(item)">保存</el-button><el-button @click="remove(item, 'template')">删除</el-button></el-form></el-card></el-tab-pane>
      <el-tab-pane label="Trend Analysis Prompt"><el-alert type="info" :closable="false" title="Trend Analysis 使用 purpose = trend_analysis 的已启用模板，并要求区分事实、推断和数据不足。" /><el-button class="add-button" @click="addTemplate('trend_analysis')">新增 Trend 模板</el-button><el-card v-for="item in trendTemplates" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="模板"><el-input v-model="item.template" type="textarea" :rows="7" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="saveTemplate(item)">保存</el-button><el-button @click="remove(item, 'template')">删除</el-button></el-form></el-card></el-tab-pane>
      <el-tab-pane label="Concept Prompt"><el-alert type="info" :closable="false" title="Creative Concept 使用 purpose = creative_concept 的已启用模板；必须综合多个趋势并保留 Trend Basis。" /><el-button class="add-button" @click="addTemplate('creative_concept')">新增 Concept 模板</el-button><el-card v-for="item in conceptTemplates" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="模板"><el-input v-model="item.template" type="textarea" :rows="7" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="saveTemplate(item)">保存</el-button><el-button @click="remove(item, 'template')">删除</el-button></el-form></el-card></el-tab-pane>
      <el-tab-pane label="Image Prompt 模板"><el-alert type="info" :closable="false" title="Image Prompt 使用 purpose = image_prompt 的已启用模板，仅生成文本 Prompt，不调用图片生成服务。" /><el-button class="add-button" @click="addTemplate('image_prompt')">新增 Image Prompt 模板</el-button><el-card v-for="item in imagePromptTemplates" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="模板"><el-input v-model="item.template" type="textarea" :rows="7" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="saveTemplate(item)">保存</el-button><el-button @click="remove(item, 'template')">删除</el-button></el-form></el-card></el-tab-pane>
      <el-tab-pane label="Query Expansion Prompt"><el-alert type="info" :closable="false" title="Query Expansion 使用 purpose = query_expansion 的已启用模板。" /><el-button class="add-button" @click="addTemplate('query_expansion')">新增 Query Expansion 模板</el-button><el-card v-for="item in queryTemplates" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="模板"><el-input v-model="item.template" type="textarea" :rows="7" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="saveTemplate(item)">保存</el-button><el-button @click="remove(item, 'template')">删除</el-button></el-form></el-card></el-tab-pane>
    </el-tabs>
  </section>
</template>

<style scoped>
.settings-page { max-width: 1100px; }
.config-card { margin-top: 16px; }
.add-button { margin-top: 16px; }
.form-top { margin-top: 20px; }
</style>
