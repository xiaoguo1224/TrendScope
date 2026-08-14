<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { downloadTaskReport, getResearchTask, getTaskAnalysis, getTaskConcepts, getTaskPrompts, getTaskRankings, getTaskReport, getTaskTrends, listTaskContents, runResearchTask, runTaskAnalysis } from '@/api/research'
import type { ReportDownloadFormat } from '@/api/research'
import type { ContentItem, CreativeConcept, ImagePrompt, RankingItem, ResearchTask, TaskAnalysisResult, TaskRankings, TaskReport, TrendAnalysis } from '@/types'

const route = useRoute()
const taskId = Number(route.params.id)
const task = ref<ResearchTask>()
const contents = ref<ContentItem[]>([])
const rankings = ref<TaskRankings>({ hot: [], rising: [], boards: {} })
const analysis = ref<TaskAnalysisResult>()
const trends = ref<TrendAnalysis>()
const concepts = ref<CreativeConcept[]>([])
const prompts = ref<ImagePrompt[]>([])
const report = ref<TaskReport>()
const activeTab = ref('contents')
const loading = ref(true)
const running = ref(false)
const analysisRunning = ref(false)
const tabLoading = ref(false)
const error = ref('')
const selectedPrompt = ref<number>()
const reportDownloading = ref<ReportDownloadFormat | null>(null)
const statusType = computed(() => {
  const types: Partial<Record<ResearchTask['status'], 'success' | 'warning' | 'danger'>> = { COMPLETED: 'success', PARTIAL: 'warning', FAILED: 'danger' }
  return types[task.value?.status ?? 'PENDING']
})
const selectedPromptItem = computed(() => prompts.value.find((item, index) => (item.id ?? index) === selectedPrompt.value) ?? prompts.value[0])

function strings(value: unknown): string[] { return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0) : [] }
function score(value: number | null | undefined): string { return typeof value === 'number' ? value.toFixed(2) : '—' }
function contentFor(item: RankingItem): ContentItem | undefined { return contents.value.find((content) => content.id === (item.content_item_id ?? item.content_id)) }
function titleFor(item: RankingItem): string { return contentFor(item)?.title || item.title || `内容 #${item.content_item_id ?? item.content_id ?? '—'}` }
function promptLabel(item: ImagePrompt, index: number): string { return item.concept_name || `Concept ${index + 1}` }
function promptText(value: string | null | undefined): string { return value?.trim() || '暂无 Prompt 内容。' }

async function loadBase(): Promise<void> {
  loading.value = true
  try { [task.value, contents.value] = await Promise.all([getResearchTask(taskId), listTaskContents(taskId)]) } finally { loading.value = false }
}
async function loadTab(tab = activeTab.value): Promise<void> {
  tabLoading.value = true; error.value = ''
  try {
    if (tab === 'hot' || tab === 'rising') rankings.value = await getTaskRankings(taskId)
    else if (['images', 'text', 'visual'].includes(tab)) analysis.value = await getTaskAnalysis(taskId)
    else if (tab === 'trends') trends.value = await getTaskTrends(taskId)
    else if (tab === 'concepts') concepts.value = await getTaskConcepts(taskId)
    else if (tab === 'prompts') { prompts.value = await getTaskPrompts(taskId); selectedPrompt.value = prompts.value[0]?.id ?? (prompts.value.length ? 0 : undefined) }
    else if (tab === 'report') report.value = await getTaskReport(taskId)
  } catch { error.value = '当前结果暂时无法加载，请稍后重试。' } finally { tabLoading.value = false }
}
function onTabChange(tab: string | number): void { void loadTab(String(tab)) }
async function runAnalysis(): Promise<void> {
  analysisRunning.value = true; error.value = ''
  try {
    analysis.value = await runTaskAnalysis(taskId, true)
    task.value = await getResearchTask(taskId)
    trends.value = undefined; concepts.value = []; prompts.value = []; report.value = undefined
    ElMessage.success('任务级综合分析已完成；查看各标签页不会再次调用模型。')
  } catch { error.value = '任务级综合分析执行失败，请稍后重试。' } finally { analysisRunning.value = false }
}
async function startResearch(): Promise<void> {
  running.value = true
  try { task.value = await runResearchTask(taskId); contents.value = await listTaskContents(taskId); analysis.value = undefined; ElMessage.success('研究采集已完成') } finally { running.value = false }
}
async function downloadReport(fileFormat: ReportDownloadFormat): Promise<void> {
  reportDownloading.value = fileFormat
  try {
    const blob = await downloadTaskReport(taskId, fileFormat)
    const url = URL.createObjectURL(blob); const anchor = document.createElement('a')
    anchor.href = url; anchor.download = `research-task-${taskId}-${fileFormat}.${fileFormat === 'json' ? 'json' : 'md'}`; anchor.click(); URL.revokeObjectURL(url)
  } finally { reportDownloading.value = null }
}
onMounted(loadBase)
</script>

<template>
  <section v-loading="loading" class="task-detail">
    <div class="page-header">
      <div><h1>{{ task?.topic ?? '研究任务' }}</h1><p class="muted">任务 #{{ taskId }} · {{ task?.platform }}</p></div>
      <div class="actions"><el-button @click="loadTab()">刷新</el-button><el-button type="warning" :loading="analysisRunning" :disabled="running" @click="runAnalysis">运行 / 重新生成综合分析</el-button><el-button type="primary" :loading="running" @click="startResearch">开始研究</el-button></div>
    </div>
    <template v-if="task">
      <el-card class="summary-card"><el-descriptions :column="2" border><el-descriptions-item label="状态"><el-tag :type="statusType">{{ task.status }}</el-tag></el-descriptions-item><el-descriptions-item label="已采集内容">{{ contents.length }} / {{ task.max_items }}</el-descriptions-item><el-descriptions-item label="采集进度" :span="2"><el-progress :percentage="task.progress ?? 0" /></el-descriptions-item><el-descriptions-item label="关键词" :span="2"><el-tag v-for="keyword in task.keywords" :key="keyword" class="tag">{{ keyword }}</el-tag></el-descriptions-item><el-descriptions-item label="研究目标" :span="2">{{ task.research_goals || '未填写' }}</el-descriptions-item></el-descriptions><el-alert v-if="task.error_message" class="top-alert" type="warning" :closable="false" :description="task.error_message" /></el-card>
      <el-tabs v-model="activeTab" type="border-card" @tab-change="onTabChange">
        <el-tab-pane label="概览" name="contents"><el-table :data="contents" empty-text="尚未采集到公开内容"><el-table-column label="内容" min-width="360"><template #default="{ row }: { row: ContentItem }"><a :href="row.url" target="_blank" rel="noopener noreferrer">{{ row.title || row.text || row.external_id }}</a></template></el-table-column><el-table-column label="点赞" width="100" prop="like_count" /><el-table-column label="收藏" width="100" prop="favorite_count" /><el-table-column label="评论" width="100" prop="comment_count" /></el-table></el-tab-pane>
        <el-tab-pane label="Hot" name="hot"><el-table :data="rankings.hot" empty-text="暂无 Hot 排行"><el-table-column label="#" width="60"><template #default="{ $index }">{{ $index + 1 }}</template></el-table-column><el-table-column label="内容" min-width="360"><template #default="{ row }: { row: RankingItem }">{{ titleFor(row) }}</template></el-table-column><el-table-column label="互动" width="120"><template #default="{ row }: { row: RankingItem }">{{ score(row.engagement_score) }}</template></el-table-column><el-table-column label="Hot 分数" width="120"><template #default="{ row }: { row: RankingItem }">{{ score(row.hot_score) }}</template></el-table-column></el-table></el-tab-pane>
        <el-tab-pane label="Rising" name="rising"><el-table :data="rankings.rising" empty-text="暂无 Rising 内容；需要至少两次互动快照。"><el-table-column label="#" width="60"><template #default="{ $index }">{{ $index + 1 }}</template></el-table-column><el-table-column label="内容" min-width="360"><template #default="{ row }: { row: RankingItem }">{{ titleFor(row) }}</template></el-table-column><el-table-column label="增长分数" width="120"><template #default="{ row }: { row: RankingItem }">{{ score(row.growth_score) }}</template></el-table-column></el-table></el-tab-pane>
        <el-tab-pane label="爆款图片" name="images"><div v-loading="tabLoading"><el-alert v-if="error" type="error" :closable="false" :title="error" /><el-empty v-else-if="!analysis?.visual_summary" description="尚未运行任务级综合分析，或没有可用本地图片。" /><el-card v-else><template #header>模型综合视觉结论</template><p>{{ analysis.visual_summary }}</p><div class="tags"><el-tag v-for="item in analysis.visual_patterns" :key="item">{{ item }}</el-tag><el-tag v-for="item in analysis.style_patterns" :key="item" type="success">{{ item }}</el-tag></div><p><strong>证据：</strong>{{ analysis.evidence.join('；') || '未返回额外文字证据。' }}</p></el-card></div></el-tab-pane>
        <el-tab-pane label="文案分析" name="text"><div v-loading="tabLoading"><el-alert v-if="error" type="error" :closable="false" :title="error" /><el-empty v-else-if="!analysis?.copywriting_summary" description="尚未运行任务级综合分析。" /><el-card v-else><template #header>模型综合文案结论</template><p>{{ analysis.copywriting_summary }}</p><p><strong>受众洞察：</strong>{{ analysis.audience_summary }}</p><p><strong>可复用规律：</strong>{{ analysis.reusable_patterns.join('；') || '—' }}</p></el-card></div></el-tab-pane>
        <el-tab-pane label="视觉分析" name="visual"><div v-loading="tabLoading"><el-alert v-if="error" type="error" :closable="false" :title="error" /><el-empty v-else-if="!analysis?.visual_summary" description="尚未运行任务级综合分析。" /><el-card v-else><template #header>模型综合视觉分析</template><p>{{ analysis.visual_summary }}</p><el-descriptions :column="2" border><el-descriptions-item label="视觉模式">{{ analysis.visual_patterns.join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="风格模式">{{ analysis.style_patterns.join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="领域特征" :span="2">{{ analysis.domain_patterns.join('、') || '—' }}</el-descriptions-item></el-descriptions></el-card></div></el-tab-pane>
        <el-tab-pane label="趋势" name="trends"><div v-loading="tabLoading"><el-alert v-if="error" type="error" :closable="false" :title="error" /><el-empty v-else-if="!trends" description="请先运行任务级综合分析。" /><template v-else><el-alert v-if="trends.insufficient_data" type="warning" :closable="false" :description="trends.limitation || '数据不足。'" /><el-descriptions v-else :column="2" border><el-descriptions-item label="热门话题">{{ strings(trends.hot_topics).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="上升话题">{{ strings(trends.rising_topics).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="文案模式">{{ strings(trends.copywriting_patterns).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="受众模式">{{ strings(trends.audience_patterns).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="场景模式">{{ strings(trends.scenario_patterns).join('、') || '—' }}</el-descriptions-item><el-descriptions-item label="风格模式">{{ strings(trends.style_patterns).join('、') || '—' }}</el-descriptions-item></el-descriptions></template></div></el-tab-pane>
        <el-tab-pane label="Creative Concepts" name="concepts"><div v-loading="tabLoading"><el-empty v-if="concepts.length === 0" description="请先运行任务级综合分析。" /><el-row v-else :gutter="16"><el-col v-for="concept in concepts" :key="concept.id" :xs="24" :md="12"><el-card class="concept-card"><template #header>{{ concept.name }}</template><p>{{ concept.concept }}</p><p><strong>趋势依据：</strong>{{ concept.trend_basis.join('；') }}</p></el-card></el-col></el-row></div></el-tab-pane>
        <el-tab-pane label="图片 Prompt" name="prompts"><div v-loading="tabLoading"><el-empty v-if="prompts.length === 0" description="请先运行任务级综合分析。" /><template v-else-if="selectedPromptItem"><el-radio-group v-model="selectedPrompt"><el-radio-button v-for="(item, index) in prompts" :key="item.id ?? index" :value="item.id ?? index">{{ promptLabel(item, index) }}</el-radio-button></el-radio-group><el-card class="prompt-card"><p><strong>Hero：</strong>{{ promptText(selectedPromptItem.hero_prompt) }}</p><p><strong>Detail：</strong>{{ promptText(selectedPromptItem.detail_prompt) }}</p><p><strong>Lifestyle：</strong>{{ promptText(selectedPromptItem.lifestyle_prompt) }}</p><p><strong>Cover：</strong>{{ promptText(selectedPromptItem.cover_prompt) }}</p><p><strong>Negative：</strong>{{ promptText(selectedPromptItem.negative_prompt) }}</p></el-card></template></div></el-tab-pane>
        <el-tab-pane label="研究报告" name="report"><div v-loading="tabLoading"><el-empty v-if="!report" description="暂无研究报告。" /><template v-else><div class="actions"><el-button text type="primary" :loading="reportDownloading === 'markdown'" @click="downloadReport('markdown')">下载 Markdown</el-button><el-button text type="primary" :loading="reportDownloading === 'json'" @click="downloadReport('json')">下载 JSON</el-button><el-button text type="primary" :loading="reportDownloading === 'prompts'" @click="downloadReport('prompts')">下载 Prompts</el-button></div><pre class="report">{{ report.markdown }}</pre><el-alert type="warning" :closable="false" :description="report.limitations.join('；') || '无额外限制。'" /></template></div></el-tab-pane>
      </el-tabs>
    </template>
  </section>
</template>

<style scoped>
.task-detail { max-width: 1280px; }.actions { display: flex; flex-wrap: wrap; gap: 12px; }.summary-card, .concept-card, .prompt-card { margin-bottom: 16px; }.top-alert { margin-top: 16px; }.tag, .tags .el-tag { margin: 2px 6px 2px 0; }.tags { margin: 16px 0; }.report { white-space: pre-wrap; overflow: auto; line-height: 1.6; }
</style>
