<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createAIProviderConfig, createPlatformConfig, createPromptTemplate, createRankingConfig, listAIProviderConfigs, listPlatformConfigs, listPromptTemplates, listRankingConfigs, listSettings, resetRankingConfig, resetSettings, updateAIProviderConfig, updatePlatformConfig, updatePromptTemplate, updateRankingConfig, updateSetting } from '@/api/configuration'
import type { AIProviderConfig, PlatformConfig, PromptTemplate, RankingConfig } from '@/types'

const saving = ref(false)
const collection = reactive({ max_items: 50, time_range: '7d', request_interval_ms: 1200, scroll_interval_ms: 1000 })
const browser = reactive({ headless: true, timeout_seconds: 30, download_images: true })
const ranking = reactive<RankingConfig>({ name: 'default', enabled: true, like_weight: 1, favorite_weight: 1.2, comment_weight: 1.5, share_weight: 1.5, view_weight: 0.1, freshness_half_life_hours: 72, growth_window_hours: 24 })
const platforms = ref<PlatformConfig[]>([])
const providers = ref<AIProviderConfig[]>([])
const templates = ref<PromptTemplate[]>([])
const rankingWeights = computed(() => [
  { label: '点赞权重', key: 'like_weight' as const },
  { label: '收藏权重', key: 'favorite_weight' as const },
  { label: '评论权重', key: 'comment_weight' as const },
  { label: '分享权重', key: 'share_weight' as const },
  { label: '浏览权重', key: 'view_weight' as const }
])

onMounted(async () => {
  const [settings, rankings, platformItems, providerItems, templateItems] = await Promise.all([listSettings(), listRankingConfigs(), listPlatformConfigs(), listAIProviderConfigs(), listPromptTemplates()])
  const collectionSetting = settings.find((item) => item.key === 'collection_defaults')?.value as Partial<typeof collection> | undefined
  const browserSetting = settings.find((item) => item.key === 'browser_defaults')?.value as Partial<typeof browser> | undefined
  Object.assign(collection, collectionSetting)
  Object.assign(browser, browserSetting)
  if (rankings[0]) Object.assign(ranking, rankings[0])
  platforms.value = platformItems
  providers.value = providerItems.map((item) => ({ ...item, api_key: '' }))
  templates.value = templateItems
})

async function save(): Promise<void> {
  saving.value = true
  try {
    await Promise.all([
      updateSetting('collection_defaults', { ...collection }, 'Default collection parameters'),
      updateSetting('browser_defaults', { ...browser }, 'Default browser parameters'),
      ranking.id ? updateRankingConfig(ranking.id, ranking) : createRankingConfig(ranking)
    ])
    ElMessage.success('配置已保存到 SQLite')
  } finally { saving.value = false }
}

async function restoreDefaults(): Promise<void> {
  const [settings, defaultRanking] = await Promise.all([resetSettings(), resetRankingConfig()])
  Object.assign(collection, settings.find((item) => item.key === 'collection_defaults')?.value)
  Object.assign(browser, settings.find((item) => item.key === 'browser_defaults')?.value)
  Object.assign(ranking, defaultRanking)
  ElMessage.success('默认配置已恢复')
}

async function savePlatform(item: PlatformConfig): Promise<void> { const saved = item.id ? await updatePlatformConfig(item.id, item) : await createPlatformConfig(item); if (!item.id) platforms.value.push(saved); ElMessage.success('平台配置已保存') }
async function saveProvider(item: AIProviderConfig): Promise<void> { const saved = item.id ? await updateAIProviderConfig(item.id, item) : await createAIProviderConfig(item); if (!item.id) providers.value.push({ ...saved, api_key: '' }); item.api_key = ''; ElMessage.success('AI Provider 配置已保存') }
async function saveTemplate(item: PromptTemplate): Promise<void> { const saved = item.id ? await updatePromptTemplate(item.id, item) : await createPromptTemplate(item); if (!item.id) templates.value.push(saved); ElMessage.success('Prompt 模板已保存') }
function addPlatform(): void { platforms.value.push({ name: '', search_url_template: null, selectors: {}, parser_rules: {}, enabled: true }) }
function addProvider(): void { providers.value.push({ name: '', provider_type: 'llm', base_url: null, model_name: null, api_key: null, timeout_seconds: 60, max_retries: 2, enabled: false }) }
function addTemplate(): void { templates.value.push({ name: '', purpose: '', template: '', enabled: true }) }
</script>

<template><section class="page-card"><div class="page-header"><div><h1>系统配置</h1><p class="muted">业务配置存储在 SQLite；基础设施路径与端口仍由启动配置决定。</p></div><div><el-button @click="restoreDefaults">恢复默认值</el-button><el-button type="primary" :loading="saving" @click="save">保存默认参数</el-button></div></div><el-tabs type="border-card"><el-tab-pane label="采集默认参数"><el-form label-width="170px"><el-form-item label="默认最大采集数"><el-input-number v-model="collection.max_items" :min="1" :max="500" /></el-form-item><el-form-item label="默认时间范围"><el-select v-model="collection.time_range"><el-option value="24h" label="近 24 小时" /><el-option value="7d" label="近 7 天" /><el-option value="30d" label="近 30 天" /></el-select></el-form-item><el-form-item label="请求间隔 (ms)"><el-input-number v-model="collection.request_interval_ms" :min="0" /></el-form-item><el-form-item label="滚动间隔 (ms)"><el-input-number v-model="collection.scroll_interval_ms" :min="0" /></el-form-item></el-form></el-tab-pane><el-tab-pane label="Browser 默认参数"><el-form label-width="170px"><el-form-item label="无头模式"><el-switch v-model="browser.headless" /></el-form-item><el-form-item label="超时时间 (秒)"><el-input-number v-model="browser.timeout_seconds" :min="1" :max="600" /></el-form-item><el-form-item label="下载图片"><el-switch v-model="browser.download_images" /></el-form-item></el-form></el-tab-pane><el-tab-pane label="Ranking 默认参数"><el-alert type="info" :closable="false" title="本阶段仅维护参数，不执行 Ranking。" /><el-form label-width="170px" style="margin-top: 20px"><el-form-item label="启用默认规则"><el-switch v-model="ranking.enabled" /></el-form-item><el-form-item v-for="item in rankingWeights" :key="item.key" :label="item.label"><el-input-number v-model="ranking[item.key]" :step="0.1" /></el-form-item><el-form-item label="新鲜度半衰期 (小时)"><el-input-number v-model="ranking.freshness_half_life_hours" :min="1" /></el-form-item><el-form-item label="增长窗口 (小时)"><el-input-number v-model="ranking.growth_window_hours" :min="1" /></el-form-item></el-form></el-tab-pane><el-tab-pane label="平台配置"><el-button @click="addPlatform">新增平台</el-button><el-card v-for="item in platforms" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="平台名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="搜索 URL 模板"><el-input v-model="item.search_url_template" placeholder="https://example.com/search?q={query}" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="savePlatform(item)">保存</el-button></el-form></el-card></el-tab-pane><el-tab-pane label="AI Provider"><el-button @click="addProvider">新增 Provider</el-button><el-card v-for="item in providers" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="类型"><el-select v-model="item.provider_type"><el-option value="llm" label="LLM" /><el-option value="vision" label="Vision" /></el-select></el-form-item><el-form-item label="Base URL"><el-input v-model="item.base_url" /></el-form-item><el-form-item label="模型"><el-input v-model="item.model_name" /></el-form-item><el-form-item label="API Key"><el-input v-model="item.api_key" show-password placeholder="已保存时显示掩码；留空不覆盖" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="saveProvider(item)">保存</el-button></el-form></el-card></el-tab-pane><el-tab-pane label="Prompt 模板"><el-button @click="addTemplate">新增模板</el-button><el-card v-for="item in templates" :key="item.id ?? item.name" class="config-card"><el-form label-width="150px"><el-form-item label="名称"><el-input v-model="item.name" /></el-form-item><el-form-item label="用途"><el-input v-model="item.purpose" /></el-form-item><el-form-item label="模板"><el-input v-model="item.template" type="textarea" /></el-form-item><el-form-item label="启用"><el-switch v-model="item.enabled" /></el-form-item><el-button type="primary" @click="saveTemplate(item)">保存</el-button></el-form></el-card></el-tab-pane></el-tabs></section></template>

<style scoped>.config-card { margin-top: 16px; }</style>
