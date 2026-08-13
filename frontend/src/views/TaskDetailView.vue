<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getResearchTask } from '@/api/research'
import type { ResearchTask } from '@/types'

const route = useRoute()
const task = ref<ResearchTask>()
const loading = ref(true)
onMounted(async () => { try { task.value = await getResearchTask(Number(route.params.id)) } finally { loading.value = false } })
</script>

<template><section v-loading="loading"><div class="page-header"><div><h1>{{ task?.topic ?? '研究任务' }}</h1><p class="muted">任务 #{{ route.params.id }}</p></div></div><el-card v-if="task"><el-descriptions :column="2" border><el-descriptions-item label="平台">{{ task.platform }}</el-descriptions-item><el-descriptions-item label="状态"><el-tag type="info">{{ task.status }}</el-tag></el-descriptions-item><el-descriptions-item label="时间范围">{{ task.time_range }}</el-descriptions-item><el-descriptions-item label="最大采集数">{{ task.max_items }}</el-descriptions-item><el-descriptions-item label="关键词" :span="2">{{ task.keywords.join('、') }}</el-descriptions-item><el-descriptions-item label="研究目标" :span="2">{{ task.research_goals || '未填写' }}</el-descriptions-item></el-descriptions><el-divider /><el-tabs><el-tab-pane v-for="name in ['概览', '热门内容', 'Rising', '爆款图片', '文案分析', '视觉分析', '趋势', 'Creative Concepts', '图片 Prompt']" :key="name" :label="name"><el-empty description="该能力将在后续 Stage 实现" /></el-tab-pane></el-tabs></el-card></section></template>
