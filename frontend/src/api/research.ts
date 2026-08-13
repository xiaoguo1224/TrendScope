import client from './client'
import type { ContentAnalysis, ContentItem, CreativeConcept, ImagePrompt, RankingItem, ResearchTask, ResearchTaskCreate, TaskAnalysisResult, TaskRankings, TaskReport, TrendAnalysis } from '@/types'

export const listResearchTasks = async (): Promise<ResearchTask[]> => (await client.get('/research/tasks')).data
export const getResearchTask = async (id: number): Promise<ResearchTask> => (await client.get(`/research/tasks/${id}`)).data
export const createResearchTask = async (payload: ResearchTaskCreate): Promise<ResearchTask> => (await client.post('/research/tasks', payload)).data
export const runResearchTask = async (id: number): Promise<ResearchTask> => (await client.post(`/research/tasks/${id}/run`)).data
export const listTaskContents = async (id: number): Promise<ContentItem[]> => (await client.get(`/research/tasks/${id}/contents`)).data

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : []
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : {}
}

function strings(value: unknown): string[] {
  return asArray<unknown>(value).filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
}

export const getTaskRankings = async (id: number): Promise<TaskRankings> => {
  const data: unknown = (await client.get(`/research/tasks/${id}/rankings`)).data
  const record = data && typeof data === 'object' ? data as Record<string, unknown> : {}
  const rankings = record.rankings && typeof record.rankings === 'object' ? record.rankings as Record<string, unknown> : record
  const boardsValue = rankings.boards
  const boards = Array.isArray(boardsValue)
    ? Object.fromEntries(boardsValue.filter((value): value is Record<string, unknown> => Boolean(value) && typeof value === 'object').map((board) => [String(board.name ?? 'unknown'), asArray<RankingItem>(board.items)]))
    : boardsValue && typeof boardsValue === 'object'
      ? Object.fromEntries(Object.entries(boardsValue as Record<string, unknown>).map(([key, value]) => [key, asArray<RankingItem>(value)]))
      : {}
  const byName = (name: string): RankingItem[] => Object.entries(boards).find(([key]) => key.toLowerCase() === name)?.[1] ?? []
  return { hot: asArray<RankingItem>(rankings.hot).length ? asArray<RankingItem>(rankings.hot) : byName('hot'), rising: asArray<RankingItem>(rankings.rising).length ? asArray<RankingItem>(rankings.rising) : byName('rising'), boards }
}

export const getTaskAnalysis = async (id: number): Promise<TaskAnalysisResult> => {
  const data: unknown = (await client.get(`/research/tasks/${id}/analysis`)).data
  const record = data && typeof data === 'object' ? data as Record<string, unknown> : {}
  const items = asArray<ContentAnalysis>(Array.isArray(data) ? data : record.items ?? record.analysis).map((item) => {
    const contentAnalysis = item.content_analysis ?? {}
    return {
      ...item,
      visual_analysis: item.visual_analysis ?? item.visual_analyses?.[0] ?? null,
      why_it_may_be_popular: item.why_it_may_be_popular ?? contentAnalysis.why_it_may_be_popular ?? null,
      core_content_elements: item.core_content_elements ?? contentAnalysis.core_content_elements ?? [],
      core_visual_elements: item.core_visual_elements ?? contentAnalysis.core_visual_elements ?? [],
      target_audience: item.target_audience ?? contentAnalysis.target_audience ?? [],
      emotional_value: item.emotional_value ?? contentAnalysis.emotional_value ?? null,
      reusable_patterns: item.reusable_patterns ?? contentAnalysis.reusable_patterns ?? [],
      trend_tags: item.trend_tags ?? contentAnalysis.trend_tags ?? [],
      evidence: item.evidence ?? contentAnalysis.evidence,
      limitations: item.limitations ?? contentAnalysis.limitations ?? []
    }
  })
  return { items, limitations: asArray<string>(record.limitations) }
}

export const getTaskTrends = async (id: number): Promise<TrendAnalysis> => {
  const data: unknown = (await client.get(`/research/tasks/${id}/trends`)).data
  return data && typeof data === 'object' ? data as TrendAnalysis : { insufficient_data: true, limitations: ['趋势接口未返回有效数据。'] }
}

function normalizeConcept(value: unknown): CreativeConcept {
  const item = asRecord(value)
  return {
    ...item,
    id: typeof item.id === 'number' ? item.id : undefined,
    name: typeof item.name === 'string' ? item.name : typeof item.title === 'string' ? item.title : '未命名创作方向',
    concept: typeof item.concept === 'string' ? item.concept : typeof item.description === 'string' ? item.description : '',
    target_audience: strings(item.target_audience),
    scenario: strings(item.scenario),
    style: typeof item.style === 'string' ? item.style : null,
    main_elements: strings(item.main_elements),
    trend_basis: strings(item.trend_basis ?? item.basis ?? item.evidence),
    differentiation: typeof item.differentiation === 'string' ? item.differentiation : null
  }
}

export const getTaskConcepts = async (id: number): Promise<CreativeConcept[]> => {
  const data: unknown = (await client.get(`/research/tasks/${id}/concepts`)).data
  const record = asRecord(data)
  const values = Array.isArray(data) ? data : record.concepts ?? record.items ?? record.data
  return asArray<unknown>(values).map(normalizeConcept)
}

function normalizePrompt(value: unknown): ImagePrompt {
  const item = asRecord(value)
  const embeddedConcept = asRecord(item.concept)
  const conceptName = typeof item.concept_name === 'string'
    ? item.concept_name
    : typeof item.name === 'string'
      ? item.name
      : typeof item.concept === 'string'
        ? item.concept
        : typeof embeddedConcept.name === 'string' ? embeddedConcept.name : undefined
  return {
    ...item,
    id: typeof item.id === 'number' ? item.id : undefined,
    concept_id: typeof item.concept_id === 'number' ? item.concept_id : typeof item.creative_concept_id === 'number' ? item.creative_concept_id : typeof embeddedConcept.id === 'number' ? embeddedConcept.id : undefined,
    concept_name: conceptName,
    concept: Object.keys(embeddedConcept).length > 0 ? normalizeConcept(embeddedConcept) : typeof item.concept === 'string' ? item.concept : null,
    trend_basis: strings(item.trend_basis ?? item.basis ?? embeddedConcept.trend_basis),
    hero_prompt: typeof item.hero_prompt === 'string' ? item.hero_prompt : null,
    detail_prompt: typeof item.detail_prompt === 'string' ? item.detail_prompt : null,
    lifestyle_prompt: typeof item.lifestyle_prompt === 'string' ? item.lifestyle_prompt : null,
    cover_prompt: typeof item.cover_prompt === 'string' ? item.cover_prompt : null,
    negative_prompt: typeof item.negative_prompt === 'string' ? item.negative_prompt : null
  }
}

export const getTaskPrompts = async (id: number): Promise<ImagePrompt[]> => {
  const data: unknown = (await client.get(`/research/tasks/${id}/prompts`)).data
  const record = asRecord(data)
  const values = Array.isArray(data) ? data : record.prompts ?? record.items ?? record.data
  return asArray<unknown>(values).map(normalizePrompt)
}

export const getTaskReport = async (id: number): Promise<TaskReport> => {
  const data: unknown = (await client.get(`/research/tasks/${id}/report`)).data
  if (typeof data === 'string') return { summary: null, markdown: data, limitations: [] }
  const record = asRecord(data)
  const report = asRecord(record.report)
  const source = Object.keys(report).length > 0 ? report : record
  const content = asRecord(source.content)
  const researchTask = asRecord(content.research_task)
  const overview = asRecord(content.data_overview)
  const generatedSummary = typeof researchTask.topic === 'string'
    ? `围绕“${researchTask.topic}”在 ${typeof researchTask.platform === 'string' ? researchTask.platform : '当前平台'} 的研究；已采集 ${typeof overview.collected_content_count === 'number' ? overview.collected_content_count : 0} 条公开内容。`
    : null
  return {
    ...source,
    summary: typeof source.summary === 'string' ? source.summary : typeof source.research_summary === 'string' ? source.research_summary : generatedSummary,
    markdown: typeof source.markdown === 'string' ? source.markdown : typeof source.report_markdown === 'string' ? source.report_markdown : typeof source.content === 'string' ? source.content : null,
    limitations: strings(source.limitations ?? source.data_limitations)
  }
}
