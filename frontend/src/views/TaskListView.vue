<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useTaskStore } from '@/stores/tasks'

const store = useTaskStore()
const router = useRouter()
onMounted(() => store.fetchTasks())
</script>

<template>
  <section>
    <div class="page-header"><div><h1>研究任务</h1><p class="muted">管理趋势研究的基础任务记录。</p></div><el-button type="primary" @click="router.push('/tasks/new')">创建研究任务</el-button></div>
    <el-card><el-table v-loading="store.loading" :data="store.tasks" empty-text="尚未创建研究任务">
      <el-table-column prop="id" label="ID" width="90" />
      <el-table-column prop="platform" label="平台" width="150" />
      <el-table-column prop="topic" label="主题" min-width="240" />
      <el-table-column label="关键词" min-width="220"><template #default="{ row }"><el-tag v-for="keyword in row.keywords" :key="keyword" class="tag">{{ keyword }}</el-tag></template></el-table-column>
      <el-table-column prop="status" label="状态" width="130"><template #default="{ row }"><el-tag type="info">{{ row.status }}</el-tag></template></el-table-column>
      <el-table-column label="创建时间" width="190"><template #default="{ row }">{{ new Date(row.created_at).toLocaleString() }}</template></el-table-column>
      <el-table-column label="操作" width="100"><template #default="{ row }"><el-button link type="primary" @click="router.push(`/tasks/${row.id}`)">查看</el-button></template></el-table-column>
    </el-table></el-card>
  </section>
</template>

<style scoped>.tag { margin-right: 6px; }</style>
