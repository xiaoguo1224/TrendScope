import client from './client'
import type { ContentItem, ResearchTask, ResearchTaskCreate } from '@/types'

export const listResearchTasks = async (): Promise<ResearchTask[]> => (await client.get('/research/tasks')).data
export const getResearchTask = async (id: number): Promise<ResearchTask> => (await client.get(`/research/tasks/${id}`)).data
export const createResearchTask = async (payload: ResearchTaskCreate): Promise<ResearchTask> => (await client.post('/research/tasks', payload)).data
export const runResearchTask = async (id: number): Promise<ResearchTask> => (await client.post(`/research/tasks/${id}/run`)).data
export const listTaskContents = async (id: number): Promise<ContentItem[]> => (await client.get(`/research/tasks/${id}/contents`)).data
