<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { downloadTaskReport, getResearchTask, getTaskAnalysis, getTaskConcepts, getTaskPrompts, getTaskRankings, getTaskReport, getTaskTrends, listTaskContents, runResearchTask } from '@/api/research'
import type { ReportDownloadFormat } from '@/api/research'
import type { ContentAnalysis, ContentItem, CreativeConcept, ImagePrompt, RankingItem, ResearchTask, TaskRankings, TaskReport, TrendAnalysis, VisualAnalysis } from '@/types'

const route = useRoute()
const taskId = Number(route.params.id)
const task = ref<ResearchTask>()
const contents = ref<ContentItem[]>([])
const loading = ref(true)
const running = ref(false)
const activeTab = ref('contents')
const rankings = ref<TaskRankings>({ hot: [], rising: [], boards: {} })
const analyses = ref<ContentAnalysis[]>([])
const trends = ref<TrendAnalysis>()
const concepts = ref<CreativeConcept[]>([])
const prompts = ref<ImagePrompt[]>([])
const report = ref<TaskReport>()
const selectedPrompt = ref<number>()
const rankingLoading = ref(false)
const analysisLoading = ref(false)
const trendLoading = ref(false)
const conceptLoading = ref(false)
const promptLoading = ref(false)
const reportLoading = ref(false)
const reportDownloading = ref<ReportDownloadFormat | null>(null)
const rankingError = ref('')
const analysisError = ref('')
const trendError = ref('')
const conceptError = ref('')
const promptError = ref('')
const reportError = ref('')
const rankingsLoaded = ref(false)
const analysisLoaded = ref(false)
const trendsLoaded = ref(false)
const conceptsLoaded = ref(false)
const promptsLoaded = ref(false)
const reportLoaded = ref(false)

const keywordGroups = computed(() => Object.entries(task.value?.expanded_keywords ?? {}).filter(([, values]) => values.length > 0))
const collectedCount = computed(() => task.value?.collected_count ?? contents.value.length)
const progressValue = computed(() => Math.min(100, Math.max(0, task.value?.progress ?? (task.value?.status === 'COMPLETED' ? 100 : 0))))
const statusType = computed(() => {
  const types: Partial<Record<ResearchTask['status'], 'success' | 'warning' | 'danger'>> = { COMPLETED: 'success', PARTIAL: 'warning', FAILED: 'danger' }
  return types[task.value?.status ?? 'PENDING'] ?? 'info'
})
const isActive = computed(() => ['EXPANDING_QUERY', 'COLLECTING'].includes(task.value?.status ?? ''))
const hotItems = computed(() => rankings.value.hot)
const risingItems = computed(() => rankings.value.rising)
const imageAnalyses = computed(() => analyses.value.filter((item) => item.visual_analysis && thumbnail(contentFor(item))))
const textAnalyses = computed(() => analyses.value.filter((item) => item.text_analysis))
const visualAnalyses = computed(() => analyses.value.filter((item) => item.visual_analysis))
const selectedPromptItem = computed(() => prompts.value.find((item, index) => (item.id ?? index) === selectedPrompt.value) ?? prompts.value[0])

function contentFor(item: ContentAnalysis | RankingItem): ContentItem | undefined {
  const embedded = item.content ?? item.item
  if (embedded) return embedded
  const contentId = item.content_item_id ?? item.content_id
  const collected = contents.value.find((content) => content.id === contentId)
  if (collected) return collected
  if (!contentId) return undefined
  const facts = (('objective_facts' in item ? item.objective_facts : undefined) ?? {}) as Record<string, unknown>
  const metrics = (('metrics' in item ? item.metrics : undefined) ?? facts) as Record<string, unknown>
  const localPaths = (('local_image_paths' in item ? item.local_image_paths : undefined) ?? []) as string[]
  return {
    id: contentId, research_task_id: taskId, platform: task.value?.platform ?? '', external_id: String(contentId), url: item.url ?? '', title: item.title ?? null, text: null, author_name: null, published_at: null,
    like_count: typeof metrics.like_count === 'number' ? metrics.like_count : null, favorite_count: typeof metrics.favorite_count === 'number' ? metrics.favorite_count : null, comment_count: typeof metrics.comment_count === 'number' ? metrics.comment_count : null, share_count: typeof metrics.share_count === 'number' ? metrics.share_count : null, view_count: typeof metrics.view_count === 'number' ? metrics.view_count : null,
    media_type: null, image_urls: [], local_image_paths: localPaths, video_urls: [], query_keyword: null, collected_at: '', raw_data: null
  }
}
function localMediaUrl(item: ContentItem, path: string): string | undefined {
  const filename = path.split(/[\\/]/).pop()
  return filename ? `/api/v1/research/tasks/${taskId}/contents/${item.id}/media/${encodeURIComponent(filename)}` : undefined
}
function thumbnail(item?: ContentItem): string | undefined { return item?.local_image_paths[0] ? localMediaUrl(item, item.local_image_paths[0]) : item?.image_urls[0] }
function previewImages(item?: ContentItem): string[] { return item?.local_image_paths.length ? item.local_image_paths.map((path) => localMediaUrl(item, path)).filter((path): path is string => Boolean(path)) : item?.image_urls ?? [] }
function displayNumber(value: number | null | undefined): string { return value == null ? '—' : new Intl.NumberFormat().format(value) }
function displayScore(value: unknown): string { return typeof value === 'number' ? value.toFixed(2) : '—' }
function arrayValue(value: unknown): string[] { return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [] }
function textValue(value: unknown): string { return typeof value === 'string' && value.trim() ? value : '—' }
function visualTags(visual?: VisualAnalysis | null): string[] {
  if (!visual) return []
  return [visual.subject, visual.style, visual.composition, visual.camera_angle, visual.lighting, visual.scene, visual.mood].filter((item): item is string => typeof item === 'string' && item.length > 0)
}
function formatJson(value: unknown): string { return JSON.stringify(value ?? {}, null, 2) }
function promptLabel(item: ImagePrompt, index: number): string { return item.concept_name || (item.concept && typeof item.concept === 'object' ? item.concept.name : item.concept) || `Concept ${index + 1}` }
function promptText(value: string | null | undefined): string { return value?.trim() || '暂无 Prompt 内容。' }
function promptField(item: ImagePrompt, field: string): string | null { const value = item[field]; return typeof value === 'string' ? value : null }

async function load(): Promise<void> {
  loading.value = true
  try {
    const [taskItem, contentItems] = await Promise.all([getResearchTask(taskId), listTaskContents(taskId)])
    task.value = taskItem
    contents.value = contentItems
  } finally { loading.value = false }
}
async function loadRankings(force = false): Promise<void> {
  if (rankingsLoaded.value && !force) return
  rankingLoading.value = true; rankingError.value = ''
  try { rankings.value = await getTaskRankings(taskId); rankingsLoaded.value = true } catch { rankingError.value = '排行榜暂时无法加载，请稍后重试。' } finally { rankingLoading.value = false }
}
async function loadAnalysis(force = false): Promise<void> {
  if (analysisLoaded.value && !force) return
  analysisLoading.value = true; analysisError.value = ''
  try { analyses.value = (await getTaskAnalysis(taskId)).items; analysisLoaded.value = true } catch { analysisError.value = '分析结果暂时无法加载，请稍后重试。' } finally { analysisLoading.value = false }
}
async function loadTrends(force = false): Promise<void> {
  if (trendsLoaded.value && !force) return
  trendLoading.value = true; trendError.value = ''
  try { trends.value = await getTaskTrends(taskId); trendsLoaded.value = true } catch { trendError.value = '趋势结果暂时无法加载，请稍后重试。' } finally { trendLoading.value = false }
}
async function loadConcepts(force = false): Promise<void> {
  if (conceptsLoaded.value && !force) return
  conceptLoading.value = true; conceptError.value = ''
  try { concepts.value = await getTaskConcepts(taskId); conceptsLoaded.value = true } catch { conceptError.value = 'Creative Concepts 暂时无法加载，请稍后重试。' } finally { conceptLoading.value = false }
}
async function loadPrompts(force = false): Promise<void> {
  if (promptsLoaded.value && !force) return
  promptLoading.value = true; promptError.value = ''
  try {
    prompts.value = await getTaskPrompts(taskId)
    selectedPrompt.value = prompts.value[0]?.id ?? (prompts.value.length ? 0 : undefined)
    promptsLoaded.value = true
  } catch { promptError.value = '图片 Prompt 暂时无法加载，请稍后重试。' } finally { promptLoading.value = false }
}
async function loadReport(force = false): Promise<void> {
  if (reportLoaded.value && !force) return
  reportLoading.value = true; reportError.value = ''
  try { report.value = await getTaskReport(taskId); reportLoaded.value = true } catch { reportError.value = '研究报告暂时无法加载，请稍后重试。' } finally { reportLoading.value = false }
}
function onTabChange(tab: string | number): void {
  if (tab === 'hot' || tab === 'rising') void loadRankings()
  if (['images', 'text', 'visual'].includes(String(tab))) void loadAnalysis()
  if (tab === 'trends') void loadTrends()
  if (tab === 'concepts') void loadConcepts()
  if (tab === 'prompts') void loadPrompts()
  if (tab === 'report') void loadReport()
}
async function refreshActive(): Promise<void> {
  if (activeTab.value === 'hot' || activeTab.value === 'rising') await loadRankings(true)
  else if (['images', 'text', 'visual'].includes(activeTab.value)) await loadAnalysis(true)
  else if (activeTab.value === 'trends') await loadTrends(true)
  else if (activeTab.value === 'concepts') await loadConcepts(true)
  else if (activeTab.value === 'prompts') await loadPrompts(true)
  else if (activeTab.value === 'report') await loadReport(true)
  else await load()
}
async function copyPrompt(value: string | null | undefined): Promise<void> {
  if (!value?.trim()) return
  try {
    await navigator.clipboard.writeText(value)
    ElMessage.success('Prompt 已复制')
  } catch { ElMessage.error('复制失败，请手动复制。') }
}
async function downloadReport(fileFormat: ReportDownloadFormat): Promise<void> {
  reportDownloading.value = fileFormat
  try {
    const blob = await downloadTaskReport(taskId, fileFormat)
    const extension = fileFormat === 'json' ? 'json' : 'md'
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `research-task-${taskId}-${fileFormat}.${extension}`
    link.click()
    URL.revokeObjectURL(url)
    ElMessage.success('报告已开始下载')
  } finally { reportDownloading.value = null }
}
async function startResearch(): Promise<void> {
  running.value = true
  try {
    task.value = await runResearchTask(taskId)
    contents.value = await listTaskContents(taskId)
    rankingsLoaded.value = false; analysisLoaded.value = false; trendsLoaded.value = false; conceptsLoaded.value = false; promptsLoaded.value = false; reportLoaded.value = false
    ElMessage.success('研究采集已启动')
  } finally { running.value = false }
}
onMounted(load)
</script>

<template>
  <section v-loading="loading" class="task-detail">
    <div class="page-header">
      <div><h1>{{ task?.topic ?? '研究任务' }}</h1><p class="muted">任务 #{{ route.params.id }} · {{ task?.platform }}</p></div>
      <div class="actions"><el-button @click="refreshActive">刷新</el-button><el-button type="primary" :loading="running" :disabled="isActive" @click="startResearch">开始研究</el-button></div>
    </div>

    <template v-if="task">
      <el-card class="summary-card">
        <el-descriptions :column="2" border>
          <el-descriptions-item label="当前状态"><el-tag :type="statusType">{{ task.status }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="当前阶段">{{ task.current_stage ?? task.status }}</el-descriptions-item>
          <el-descriptions-item label="采集进度" :span="2"><el-progress :percentage="progressValue" :status="task.status === 'FAILED' ? 'exception' : undefined" /></el-descriptions-item>
          <el-descriptions-item label="已采集内容">{{ collectedCount }} / {{ task.max_items }}</el-descriptions-item>
          <el-descriptions-item label="时间范围">{{ task.time_range }}</el-descriptions-item>
          <el-descriptions-item label="原始关键词" :span="2"><el-tag v-for="keyword in task.keywords" :key="keyword" class="tag">{{ keyword }}</el-tag></el-descriptions-item>
          <el-descriptions-item label="研究目标" :span="2">{{ task.research_goals || '未填写' }}</el-descriptions-item>
        </el-descriptions>
        <el-alert v-if="task.error_message" class="task-error" type="error" :closable="false" title="任务错误" :description="task.error_message" />
      </el-card>

      <el-tabs v-model="activeTab" type="border-card" @tab-change="onTabChange">
        <el-tab-pane label="概览" name="contents">
          <el-card shadow="never" class="keywords-card"><template #header>扩展关键词</template><el-empty v-if="keywordGroups.length === 0" description="开始研究后将显示 Query Expansion 结果" /><el-descriptions v-else :column="1" border><el-descriptions-item v-for="[group, values] in keywordGroups" :key="group" :label="group"><el-tag v-for="keyword in values" :key="keyword" class="tag">{{ keyword }}</el-tag></el-descriptions-item></el-descriptions></el-card>
          <el-card shadow="never"><template #header><div class="card-header"><span>已采集内容</span><span class="muted">{{ contents.length }} 条</span></div></template><el-table :data="contents" empty-text="尚未采集到公开内容"><el-table-column label="内容" min-width="300"><template #default="{ row }: { row: ContentItem }"><div class="content-cell"><el-image v-if="thumbnail(row)" :src="thumbnail(row)" fit="cover" :preview-src-list="previewImages(row)" class="thumbnail" /><div><a :href="row.url" target="_blank" rel="noopener noreferrer" class="content-title">{{ row.title || row.text || row.external_id }}</a><p v-if="row.author_name" class="muted compact">{{ row.author_name }}</p><p v-if="row.query_keyword" class="muted compact">查询词：{{ row.query_keyword }}</p></div></div></template></el-table-column><el-table-column label="公开指标" min-width="250"><template #default="{ row }: { row: ContentItem }"><div class="metric-grid"><span>赞 {{ displayNumber(row.like_count) }}</span><span>藏 {{ displayNumber(row.favorite_count) }}</span><span>评 {{ displayNumber(row.comment_count) }}</span><span>转 {{ displayNumber(row.share_count) }}</span><span>阅 {{ displayNumber(row.view_count) }}</span></div></template></el-table-column><el-table-column label="采集时间" width="180"><template #default="{ row }: { row: ContentItem }">{{ new Date(row.collected_at).toLocaleString() }}</template></el-table-column></el-table></el-card>
        </el-tab-pane>

        <el-tab-pane label="Hot" name="hot"><div v-loading="rankingLoading"><el-alert v-if="rankingError" type="error" :closable="false" :title="rankingError" /><el-empty v-else-if="!rankingLoading && hotItems.length === 0" description="暂无 Hot 排行；完成采集与排名后显示。" /><el-table v-else :data="hotItems"><el-table-column label="#" width="72"><template #default="{ $index }">{{ $index + 1 }}</template></el-table-column><el-table-column label="内容" min-width="300"><template #default="{ row }: { row: RankingItem }"><a v-if="contentFor(row)" :href="contentFor(row)?.url" class="content-title" target="_blank" rel="noopener noreferrer">{{ contentFor(row)?.title || contentFor(row)?.text || contentFor(row)?.external_id }}</a></template></el-table-column><el-table-column label="互动" width="110"><template #default="{ row }: { row: RankingItem }">{{ displayScore(row.engagement_score) }}</template></el-table-column><el-table-column label="新鲜度" width="110"><template #default="{ row }: { row: RankingItem }">{{ displayScore(row.freshness_score) }}</template></el-table-column><el-table-column label="Hot 分数" width="120"><template #default="{ row }: { row: RankingItem }">{{ displayScore(row.hot_score) }}</template></el-table-column></el-table></div></el-tab-pane>
        <el-tab-pane label="Rising" name="rising"><div v-loading="rankingLoading"><el-alert v-if="rankingError" type="error" :closable="false" :title="rankingError" /><el-empty v-else-if="!rankingLoading && risingItems.length === 0" description="暂无 Rising 内容。Rising 需要至少两个互动快照来计算增长。" /><el-table v-else :data="risingItems"><el-table-column label="#" width="72"><template #default="{ $index }">{{ $index + 1 }}</template></el-table-column><el-table-column label="内容" min-width="320"><template #default="{ row }: { row: RankingItem }"><a v-if="contentFor(row)" :href="contentFor(row)?.url" class="content-title" target="_blank" rel="noopener noreferrer">{{ contentFor(row)?.title || contentFor(row)?.text || contentFor(row)?.external_id }}</a></template></el-table-column><el-table-column label="增长分数" width="130"><template #default="{ row }: { row: RankingItem }">{{ displayScore(row.growth_score) }}</template></el-table-column><el-table-column label="Hot 分数" width="120"><template #default="{ row }: { row: RankingItem }">{{ displayScore(row.hot_score) }}</template></el-table-column></el-table></div></el-tab-pane>

        <el-tab-pane label="爆款图片" name="images"><div v-loading="analysisLoading"><el-alert v-if="analysisError" type="error" :closable="false" :title="analysisError" /><el-empty v-else-if="!analysisLoading && imageAnalyses.length === 0" description="暂无带图片的视觉分析结果。" /><el-card v-for="entry in imageAnalyses" :key="entry.content_item_id ?? entry.content_id" class="analysis-card" shadow="never"><div class="image-analysis"><el-image :src="thumbnail(contentFor(entry))" :preview-src-list="previewImages(contentFor(entry))" fit="cover" class="analysis-image" /><div class="analysis-body"><a v-if="contentFor(entry)" :href="contentFor(entry)?.url" target="_blank" rel="noopener noreferrer" class="content-title">{{ contentFor(entry)?.title || contentFor(entry)?.text || contentFor(entry)?.external_id }}</a><p class="muted">来源：{{ contentFor(entry)?.platform }} · {{ contentFor(entry)?.author_name || '未知作者' }}</p><div class="metric-grid"><span>赞 {{ displayNumber(contentFor(entry)?.like_count) }}</span><span>藏 {{ displayNumber(contentFor(entry)?.favorite_count) }}</span><span>评 {{ displayNumber(contentFor(entry)?.comment_count) }}</span><span>转 {{ displayNumber(contentFor(entry)?.share_count) }}</span><span>阅 {{ displayNumber(contentFor(entry)?.view_count) }}</span></div><div class="tag-row"><el-tag v-for="tag in visualTags(entry.visual_analysis)" :key="tag" effect="plain">{{ tag }}</el-tag></div><p><strong>AI 分析说明：</strong>{{ textValue(entry.why_it_may_be_popular) }}</p><p><strong>视觉要素：</strong>{{ arrayValue(entry.core_visual_elements).join('、') || '—' }}</p><el-collapse><el-collapse-item title="domain_attributes" name="domain"><pre>{{ formatJson(entry.visual_analysis?.domain_attributes) }}</pre></el-collapse-item></el-collapse></div></div></el-card></div></el-tab-pane>
        <el-tab-pane label="文案分析" name="text"><div v-loading="analysisLoading"><el-alert v-if="analysisError" type="error" :closable="false" :title="analysisError" /><el-empty v-else-if="!analysisLoading && textAnalyses.length === 0" description="暂无文案分析结果。" /><el-card v-for="entry in textAnalyses" :key="entry.content_item_id ?? entry.content_id" class="analysis-card" shadow="never"><template #header><a v-if="contentFor(entry)" :href="contentFor(entry)?.url" class="content-title" target="_blank" rel="noopener noreferrer">{{ contentFor(entry)?.title || contentFor(entry)?.text || contentFor(entry)?.external_id }}</a></template><el-descriptions :column="2" border><el-descriptions-item label="Hook 类型">{{ textValue(entry.text_analysis?.hook_type) }}</el-descriptions-item><el-descriptions-item label="标题结构">{{ textValue(entry.text_analysis?.title_structure) }}</el-descriptions-item><el-descriptions-item label="开场 Hook" :span="2">{{ textValue(entry.text_analysis?.opening_hook) }}</el-descriptions-item><el-descriptions-item label="写作风格">{{ textValue(entry.text_analysis?.writing_style) }}</el-descriptions-item><el-descriptions-item label="情绪">{{ textValue(entry.text_analysis?.emotion) }}</el-descriptions-item><el-descriptions-item label="痛点">{{ arrayValue(entry.text_analysis?.pain_points).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="收益点">{{ arrayValue(entry.text_analysis?.benefits).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="目标受众">{{ arrayValue(entry.text_analysis?.target_audience).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="场景">{{ arrayValue(entry.text_analysis?.scenario).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="CTA">{{ textValue(entry.text_analysis?.cta) }}</el-descriptions-item><el-descriptions-item label="话题标签">{{ arrayValue(entry.text_analysis?.hashtags).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="可复用模式" :span="2">{{ arrayValue(entry.text_analysis?.reusable_patterns).join('、') || '—' }}</el-descriptions-item></el-descriptions></el-card></div></el-tab-pane>
        <el-tab-pane label="视觉分析" name="visual"><div v-loading="analysisLoading"><el-alert v-if="analysisError" type="error" :closable="false" :title="analysisError" /><el-empty v-else-if="!analysisLoading && visualAnalyses.length === 0" description="暂无视觉分析结果。" /><el-card v-for="entry in visualAnalyses" :key="entry.content_item_id ?? entry.content_id" class="analysis-card" shadow="never"><template #header><a v-if="contentFor(entry)" :href="contentFor(entry)?.url" class="content-title" target="_blank" rel="noopener noreferrer">{{ contentFor(entry)?.title || contentFor(entry)?.text || contentFor(entry)?.external_id }}</a></template><el-descriptions :column="2" border><el-descriptions-item label="主体">{{ textValue(entry.visual_analysis?.subject) }}</el-descriptions-item><el-descriptions-item label="风格">{{ textValue(entry.visual_analysis?.style) }}</el-descriptions-item><el-descriptions-item label="主色">{{ arrayValue(entry.visual_analysis?.main_colors).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="辅助色">{{ arrayValue(entry.visual_analysis?.secondary_colors).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="构图">{{ textValue(entry.visual_analysis?.composition) }}</el-descriptions-item><el-descriptions-item label="镜头角度">{{ textValue(entry.visual_analysis?.camera_angle) }}</el-descriptions-item><el-descriptions-item label="光线">{{ textValue(entry.visual_analysis?.lighting) }}</el-descriptions-item><el-descriptions-item label="背景">{{ textValue(entry.visual_analysis?.background) }}</el-descriptions-item><el-descriptions-item label="视觉焦点">{{ textValue(entry.visual_analysis?.visual_focus) }}</el-descriptions-item><el-descriptions-item label="情绪">{{ textValue(entry.visual_analysis?.mood) }}</el-descriptions-item><el-descriptions-item label="显著元素" :span="2">{{ arrayValue(entry.visual_analysis?.notable_elements).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="可复用视觉模式" :span="2">{{ arrayValue(entry.visual_analysis?.reusable_visual_patterns).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="置信度">{{ displayScore(entry.visual_analysis?.confidence) }}</el-descriptions-item><el-descriptions-item label="AI 说明">{{ textValue(entry.why_it_may_be_popular) }}</el-descriptions-item></el-descriptions></el-card></div></el-tab-pane>
        <el-tab-pane label="趋势" name="trends"><div v-loading="trendLoading"><el-alert v-if="trendError" type="error" :closable="false" :title="trendError" /><el-empty v-else-if="!trendLoading && !trends" description="暂无趋势分析结果。" /><template v-else-if="trends"><el-alert v-if="trends.insufficient_data" type="warning" :closable="false" title="数据量不足，趋势仅供参考" :description="arrayValue(trends.limitations).join('；') || trends.limitation || '请采集更多公开内容后重新执行分析。'" /><el-descriptions class="trend-grid" :column="2" border><el-descriptions-item label="热门话题">{{ arrayValue(trends.hot_topics).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="上升话题">{{ arrayValue(trends.rising_topics).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="视觉模式">{{ arrayValue(trends.visual_patterns).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="文案模式">{{ arrayValue(trends.copywriting_patterns).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="受众模式">{{ arrayValue(trends.audience_patterns).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="场景模式">{{ arrayValue(trends.scenario_patterns).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="风格模式">{{ arrayValue(trends.style_patterns).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="领域模式">{{ arrayValue(trends.domain_patterns).join('、') || '—' }}</el-descriptions-item></el-descriptions></template></div></el-tab-pane>
        <el-tab-pane label="Creative Concepts" name="concepts"><div v-loading="conceptLoading"><el-alert v-if="conceptError" type="error" :closable="false" :title="conceptError" /><el-empty v-else-if="!conceptLoading && concepts.length === 0" description="暂无创作方向；完成趋势分析和 Concept 生成后显示。" /><el-row v-else :gutter="16"><el-col v-for="(concept, index) in concepts" :key="concept.id ?? `${concept.name}-${index}`" :xs="24" :lg="12"><el-card class="concept-card" shadow="never"><template #header><div class="card-header"><strong>{{ concept.name }}</strong><el-tag effect="plain">{{ concept.style || '通用风格' }}</el-tag></div></template><p>{{ concept.concept || '暂无方向说明。' }}</p><el-descriptions :column="1" size="small" border><el-descriptions-item label="目标受众">{{ concept.target_audience.join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="应用场景">{{ concept.scenario.join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="核心元素">{{ concept.main_elements.join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="差异化">{{ concept.differentiation || '—' }}</el-descriptions-item></el-descriptions><div class="trend-basis"><strong>Trend Basis</strong><p>{{ concept.trend_basis.join('；') || '暂无可追溯趋势依据。' }}</p></div></el-card></el-col></el-row></div></el-tab-pane>
        <el-tab-pane label="图片 Prompt" name="prompts"><div v-loading="promptLoading"><el-alert v-if="promptError" type="error" :closable="false" :title="promptError" /><el-empty v-else-if="!promptLoading && prompts.length === 0" description="暂无图片 Prompt；完成 Concept 与 Prompt 生成后显示。" /><template v-else-if="selectedPromptItem"><el-radio-group v-model="selectedPrompt" class="concept-switcher"><el-radio-button v-for="(item, index) in prompts" :key="item.id ?? index" :value="item.id ?? index">{{ promptLabel(item, index) }}</el-radio-button></el-radio-group><el-card class="prompt-card" shadow="never"><template #header><div class="card-header"><strong>{{ promptLabel(selectedPromptItem, prompts.indexOf(selectedPromptItem)) }}</strong><el-tag type="info">仅输出 Prompt，不生成图片</el-tag></div></template><div class="trend-basis"><strong>Trend Basis</strong><p>{{ selectedPromptItem.trend_basis.join('；') || '暂无可追溯趋势依据。' }}</p></div><el-row :gutter="16"><el-col v-for="section in [{ key: 'hero_prompt', label: 'Hero' }, { key: 'detail_prompt', label: 'Detail' }, { key: 'lifestyle_prompt', label: 'Lifestyle' }, { key: 'cover_prompt', label: 'Cover' }, { key: 'negative_prompt', label: 'Negative' }]" :key="section.key" :xs="24" :md="12"><section class="prompt-section"><div class="card-header"><strong>{{ section.label }} Prompt</strong><el-button text type="primary" @click="copyPrompt(promptField(selectedPromptItem, section.key))">复制</el-button></div><pre>{{ promptText(promptField(selectedPromptItem, section.key)) }}</pre></section></el-col></el-row></el-card></template></div></el-tab-pane>
        <el-tab-pane label="研究报告" name="report"><div v-loading="reportLoading"><el-alert v-if="reportError" type="error" :closable="false" :title="reportError" /><el-empty v-else-if="!reportLoading && !report" description="暂无研究报告；任务完成后将生成 Markdown 报告。" /><template v-else-if="report"><el-card shadow="never" class="report-card"><template #header>研究摘要</template><p>{{ report.summary || '报告未提供独立摘要，请查看下方 Markdown 内容。' }}</p></el-card><el-card shadow="never" class="report-card"><template #header><div class="card-header"><strong>Markdown 报告</strong><div><el-button text type="primary" :loading="reportDownloading === 'markdown'" @click="downloadReport('markdown')">下载 Markdown</el-button><el-button text type="primary" :loading="reportDownloading === 'json'" @click="downloadReport('json')">下载 JSON</el-button><el-button text type="primary" :loading="reportDownloading === 'prompts'" @click="downloadReport('prompts')">下载 Prompts</el-button></div></div></template><pre class="markdown-report">{{ report.markdown || '暂无 Markdown 报告内容。' }}</pre></el-card><el-alert type="warning" :closable="false" title="数据限制" :description="report.limitations.join('；') || '报告未返回额外数据限制。'" /></template></div></el-tab-pane>
      </el-tabs>
    </template>
  </section>
</template>

<style scoped>
  .task-detail { max-width: 1280px; }.actions { display: flex; gap: 12px; }.summary-card { margin-bottom: 20px; }.keywords-card { margin-bottom: 16px; }.task-error { margin-top: 20px; }.card-header { display: flex; justify-content: space-between; gap: 12px; align-items: center; }.tag { margin: 2px 6px 2px 0; }.content-cell { display: flex; align-items: center; gap: 12px; }.thumbnail { width: 64px; height: 64px; flex: 0 0 64px; border-radius: 6px; }.content-title { color: var(--el-color-primary); font-weight: 600; text-decoration: none; }.compact { margin: 5px 0 0; font-size: 12px; }.metric-grid { display: flex; flex-wrap: wrap; gap: 6px 12px; color: #475467; font-size: 13px; }.analysis-card, .concept-card, .report-card { margin-bottom: 16px; }.image-analysis { display: flex; gap: 18px; }.analysis-image { width: 180px; height: 180px; flex: 0 0 180px; border-radius: 6px; }.analysis-body { min-width: 0; flex: 1; }.tag-row { display: flex; flex-wrap: wrap; gap: 6px; margin: 12px 0; }.tag-row .el-tag { margin: 0; }.analysis-body pre, .prompt-section pre, .markdown-report { margin: 0; overflow: auto; white-space: pre-wrap; word-break: break-word; }.trend-grid { margin-top: 16px; }.trend-basis { margin-top: 16px; color: #475467; }.trend-basis p { margin: 6px 0 0; }.concept-switcher { display: flex; flex-wrap: wrap; margin-bottom: 16px; }.prompt-section { border: 1px solid var(--el-border-color-lighter); border-radius: 6px; padding: 12px; margin-bottom: 16px; min-height: 120px; }.prompt-section pre { margin-top: 10px; font-family: inherit; }.markdown-report { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; line-height: 1.65; }
</style>
