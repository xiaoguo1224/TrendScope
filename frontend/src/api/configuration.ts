import client from './client'
import type { AIProviderConfig, AppSetting, PlatformConfig, PlatformConfigTestResult, PromptTemplate, RankingConfig } from '@/types'

export const listSettings = async (): Promise<AppSetting[]> => (await client.get('/config/settings')).data
export const updateSetting = async (key: string, value: unknown, description?: string): Promise<AppSetting> => (await client.put(`/config/settings/${key}`, { value, description })).data
export const resetSettings = async (): Promise<AppSetting[]> => (await client.post('/config/settings/reset-defaults')).data
export const listRankingConfigs = async (): Promise<RankingConfig[]> => (await client.get('/config/ranking-configs')).data
export const createRankingConfig = async (payload: RankingConfig): Promise<RankingConfig> => (await client.post('/config/ranking-configs', payload)).data
export const updateRankingConfig = async (id: number, payload: RankingConfig): Promise<RankingConfig> => (await client.put(`/config/ranking-configs/${id}`, payload)).data
export const resetRankingConfig = async (): Promise<RankingConfig> => (await client.post('/config/ranking-configs/reset-default')).data
export const listPlatformConfigs = async (): Promise<PlatformConfig[]> => (await client.get('/config/platforms')).data
export const createPlatformConfig = async (payload: PlatformConfig): Promise<PlatformConfig> => (await client.post('/config/platforms', payload)).data
export const updatePlatformConfig = async (id: number, payload: PlatformConfig): Promise<PlatformConfig> => (await client.put(`/config/platforms/${id}`, payload)).data
export const deletePlatformConfig = async (id: number): Promise<void> => { await client.delete(`/config/platforms/${id}`) }
export const testPlatformConfig = async (id: number, query = '测试关键词'): Promise<PlatformConfigTestResult> => (await client.post(`/config/platforms/${id}/test`, { query })).data
export const listAIProviderConfigs = async (): Promise<AIProviderConfig[]> => (await client.get('/config/ai-providers')).data
export const createAIProviderConfig = async (payload: AIProviderConfig): Promise<AIProviderConfig> => (await client.post('/config/ai-providers', payload)).data
export const updateAIProviderConfig = async (id: number, payload: AIProviderConfig): Promise<AIProviderConfig> => (await client.put(`/config/ai-providers/${id}`, payload)).data
export const deleteAIProviderConfig = async (id: number): Promise<void> => { await client.delete(`/config/ai-providers/${id}`) }
export const listPromptTemplates = async (): Promise<PromptTemplate[]> => (await client.get('/config/prompt-templates')).data
export const createPromptTemplate = async (payload: PromptTemplate): Promise<PromptTemplate> => (await client.post('/config/prompt-templates', payload)).data
export const updatePromptTemplate = async (id: number, payload: PromptTemplate): Promise<PromptTemplate> => (await client.put(`/config/prompt-templates/${id}`, payload)).data
export const deletePromptTemplate = async (id: number): Promise<void> => { await client.delete(`/config/prompt-templates/${id}`) }
