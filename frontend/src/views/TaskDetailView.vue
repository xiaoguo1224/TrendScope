<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getResearchTask, listTaskContents, runResearchTask } from '@/api/research'
import type { ContentItem, ResearchTask } from '@/types'

const route = useRoute()
const taskId = Number(route.params.id)
const task = ref<ResearchTask>()
const contents = ref<ContentItem[]>([])
const loading = ref(true)
const running = ref(false)

const keywordGroups = computed(() => Object.entries(task.value?.expanded_keywords ?? {}).filter(([, values]) => values.length > 0))
const collectedCount = computed(() => task.value?.collected_count ?? contents.value.length)
const progressValue = computed(() => Math.min(100, Math.max(0, task.value?.progress ?? (task.value?.status === 'COMPLETED' ? 100 : 0))))
const statusType = computed(() => {
  const types: Partial<Record<ResearchTask['status'], 'success' | 'warning' | 'danger'>> = { COMPLETED: 'success', PARTIAL: 'warning', FAILED: 'danger' }
  return types[task.value?.status ?? 'PENDING'] ?? 'info'
})
const isActive = computed(() => ['EXPANDING_QUERY', 'COLLECTING'].includes(task.value?.status ?? ''))

function thumbnail(item: ContentItem): string | undefined {
  return item.local_image_paths[0] || item.image_urls[0]
}

function displayNumber(value: number | null): string {
  return value == null ? '—' : new Intl.NumberFormat().format(value)
}

async function load(): Promise<void> {
  loading.value = true
  try {
    const [taskItem, contentItems] = await Promise.all([getResearchTask(taskId), listTaskContents(taskId)])
    task.value = taskItem
    contents.value = contentItems
  } finally {
    loading.value = false
  }
}

async function startResearch(): Promise<void> {
  running.value = true
  try {
    task.value = await runResearchTask(taskId)
    contents.value = await listTaskContents(taskId)
    ElMessage.success('研究采集已启动')
  } finally {
    running.value = false
  }
}

onMounted(load)
</script>

<template>
  <section v-loading="loading" class="task-detail">
    <div class="page-header">
      <div><h1>{{ task?.topic ?? '研究任务' }}</h1><p class="muted">任务 #{{ route.params.id }} · {{ task?.platform }}</p></div>
      <div class="actions"><el-button @click="load">刷新</el-button><el-button type="primary" :loading="running" :disabled="isActive" @click="startResearch">开始研究</el-button></div>
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

      <el-card class="keywords-card">
        <template #header>扩展关键词</template>
        <el-empty v-if="keywordGroups.length === 0" description="开始研究后将显示 Query Expansion 结果" />
        <el-descriptions v-else :column="1" border>
          <el-descriptions-item v-for="[group, values] in keywordGroups" :key="group" :label="group"><el-tag v-for="keyword in values" :key="keyword" class="tag">{{ keyword }}</el-tag></el-descriptions-item>
        </el-descriptions>
      </el-card>

      <el-card>
        <template #header><div class="card-header"><span>已采集内容</span><span class="muted">{{ contents.length }} 条</span></div></template>
        <el-table :data="contents" empty-text="尚未采集到公开内容">
          <el-table-column label="内容" min-width="300">
            <template #default="{ row }: { row: ContentItem }"><div class="content-cell"><el-image v-if="thumbnail(row)" :src="thumbnail(row)" fit="cover" :preview-src-list="row.image_urls" class="thumbnail" /><div><a :href="row.url" target="_blank" rel="noopener noreferrer" class="content-title">{{ row.title || row.text || row.external_id }}</a><p v-if="row.author_name" class="muted compact">{{ row.author_name }}</p><p v-if="row.query_keyword" class="muted compact">查询词：{{ row.query_keyword }}</p></div></div></template>
          </el-table-column>
          <el-table-column label="公开指标" min-width="250"><template #default="{ row }: { row: ContentItem }"><div class="metric-grid"><span>赞 {{ displayNumber(row.like_count) }}</span><span>藏 {{ displayNumber(row.favorite_count) }}</span><span>评 {{ displayNumber(row.comment_count) }}</span><span>转 {{ displayNumber(row.share_count) }}</span><span>阅 {{ displayNumber(row.view_count) }}</span></div></template></el-table-column>
          <el-table-column label="采集时间" width="180"><template #default="{ row }: { row: ContentItem }">{{ new Date(row.collected_at).toLocaleString() }}</template></el-table-column>
          <el-table-column label="错误" min-width="180"><template #default="{ row }: { row: ContentItem }"><span class="error-text">{{ row.error_message || '—' }}</span></template></el-table-column>
        </el-table>
      </el-card>
    </template>
  </section>
</template>

<style scoped>
.task-detail { max-width: 1280px; }
.actions { display: flex; gap: 12px; }
.summary-card, .keywords-card { margin-bottom: 20px; }
.task-error { margin-top: 20px; }
.card-header { display: flex; justify-content: space-between; }
.tag { margin: 2px 6px 2px 0; }
.content-cell { display: flex; align-items: center; gap: 12px; }
.thumbnail { width: 64px; height: 64px; flex: 0 0 64px; border-radius: 6px; }
.content-title { color: var(--el-color-primary); font-weight: 600; text-decoration: none; }
.compact { margin: 5px 0 0; font-size: 12px; }
.metric-grid { display: flex; flex-wrap: wrap; gap: 6px 12px; color: #475467; font-size: 13px; }
.error-text { color: var(--el-color-danger); }
</style>
