<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { createResearchTask } from '@/api/research'

const router = useRouter()
const formRef = ref<FormInstance>()
const submitting = ref(false)
const form = reactive({ platform: 'generic-web', topic: '', keywordsText: '', time_range: '7d', max_items: 50, research_goals: '' })
const rules: FormRules = { platform: [{ required: true, message: '请输入平台标识', trigger: 'blur' }], topic: [{ required: true, message: '请输入研究主题', trigger: 'blur' }], keywordsText: [{ required: true, message: '至少输入一个关键词', trigger: 'blur' }] }

async function submit(): Promise<void> {
  if (!formRef.value || !(await formRef.value.validate().catch(() => false))) return
  submitting.value = true
  try {
    const task = await createResearchTask({ ...form, keywords: form.keywordsText.split(/[,，\n]/).map((value) => value.trim()).filter(Boolean) })
    ElMessage.success('研究任务已创建')
    router.push(`/tasks/${task.id}`)
  } finally { submitting.value = false }
}
</script>

<template><section class="page-card"><div class="page-header"><div><h1>创建研究任务</h1><p class="muted">Stage 01 仅创建和保存任务，尚不启动采集。</p></div></div><el-card><el-form ref="formRef" :model="form" :rules="rules" label-width="120px" @submit.prevent="submit"><el-form-item label="平台" prop="platform"><el-input v-model="form.platform" /></el-form-item><el-form-item label="研究主题" prop="topic"><el-input v-model="form.topic" /></el-form-item><el-form-item label="关键词" prop="keywordsText"><el-input v-model="form.keywordsText" type="textarea" placeholder="用逗号或换行分隔" /></el-form-item><el-form-item label="时间范围"><el-select v-model="form.time_range"><el-option label="近 24 小时" value="24h" /><el-option label="近 7 天" value="7d" /><el-option label="近 30 天" value="30d" /></el-select></el-form-item><el-form-item label="最大采集数"><el-input-number v-model="form.max_items" :min="1" :max="500" /></el-form-item><el-form-item label="研究目标"><el-input v-model="form.research_goals" type="textarea" /></el-form-item><el-form-item><el-button type="primary" :loading="submitting" @click="submit">保存任务</el-button><el-button @click="router.push('/tasks')">取消</el-button></el-form-item></el-form></el-card></section></template>
