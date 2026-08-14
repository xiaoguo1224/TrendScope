<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { createResearchTask } from '@/api/research'
import { listPlatformConfigs } from '@/api/configuration'
import type { PlatformConfig } from '@/types'

const router = useRouter()
const formRef = ref<FormInstance>()
const submitting = ref(false)
const platformLoading = ref(true)
const platforms = ref<PlatformConfig[]>([])
const form = reactive({ platform: 'generic-web', topic: '', keywordsText: '', time_range: '7d', max_items: 50, research_goals: '' })
const enabledPlatforms = computed(() => platforms.value.filter((item) => item.enabled))
const rules: FormRules = { platform: [{ required: true, message: '请选择已启用的平台', trigger: 'change' }], topic: [{ required: true, message: '请输入研究主题', trigger: 'blur' }], keywordsText: [{ required: true, message: '至少输入一个关键词', trigger: 'blur' }] }

async function loadPlatforms(): Promise<void> {
  platformLoading.value = true
  try {
    platforms.value = await listPlatformConfigs()
    if (!enabledPlatforms.value.some((item) => item.name === form.platform)) form.platform = enabledPlatforms.value[0]?.name ?? ''
  } finally { platformLoading.value = false }
}

async function submit(): Promise<void> {
  if (!formRef.value || !(await formRef.value.validate().catch(() => false))) return
  submitting.value = true
  try {
    const task = await createResearchTask({ ...form, keywords: form.keywordsText.split(/[,，\n]/).map((value) => value.trim()).filter(Boolean) })
    ElMessage.success('研究任务已创建')
    router.push(`/tasks/${task.id}`)
  } finally { submitting.value = false }
}

onMounted(loadPlatforms)
</script>

<template><section class="page-card"><div class="page-header"><div><h1>创建研究任务</h1><p class="muted">选择已启用的平台后创建任务；任务详情中可启动完整研究流程。</p></div></div><el-card><el-form ref="formRef" :model="form" :rules="rules" label-width="120px" @submit.prevent="submit"><el-form-item label="平台" prop="platform"><el-select v-model="form.platform" :loading="platformLoading" placeholder="请选择已启用的平台" style="width: 100%"><el-option v-for="item in enabledPlatforms" :key="item.id ?? item.name" :label="item.name" :value="item.name" /></el-select><div v-if="!platformLoading && enabledPlatforms.length === 0" class="form-help">没有已启用的平台。请先到“系统配置 → 平台配置”新增或启用平台。</div></el-form-item><el-form-item label="研究主题" prop="topic"><el-input v-model="form.topic" /></el-form-item><el-form-item label="关键词" prop="keywordsText"><el-input v-model="form.keywordsText" type="textarea" placeholder="用逗号或换行分隔" /></el-form-item><el-form-item label="时间范围"><el-select v-model="form.time_range"><el-option label="近 24 小时" value="24h" /><el-option label="近 7 天" value="7d" /><el-option label="近 30 天" value="30d" /></el-select></el-form-item><el-form-item label="最大采集数"><el-input-number v-model="form.max_items" :min="1" :max="500" /></el-form-item><el-form-item label="研究目标"><el-input v-model="form.research_goals" type="textarea" /></el-form-item><el-form-item><el-button type="primary" :loading="submitting" :disabled="platformLoading || enabledPlatforms.length === 0" @click="submit">保存任务</el-button><el-button @click="router.push('/tasks')">取消</el-button></el-form-item></el-form></el-card></section></template>
