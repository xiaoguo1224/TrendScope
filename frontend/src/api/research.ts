import client from './client'
import type { ContentAnalysis, ContentItem, RankingItem, ResearchTask, ResearchTaskCreate, TaskAnalysisResult, TaskRankings, TrendAnalysis } from '@/types'

export const listResearchTasks = async (): Promise<ResearchTask[]> => (await client.get('/research/tasks')).data
export const getResearchTask = async (id: number): Promise<ResearchTask> => (await client.get(`/research/tasks/${id}`)).data
export const createResearchTask = async (payload: ResearchTaskCreate): Promise<ResearchTask> => (await client.post('/research/tasks', payload)).data
export const runResearchTask = async (id: number): Promise<ResearchTask> => (await client.post(`/research/tasks/${id}/run`)).data
export const listTaskContents = async (id: number): Promise<ContentItem[]> => (await client.get(`/research/tasks/${id}/contents`)).data

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : []
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
