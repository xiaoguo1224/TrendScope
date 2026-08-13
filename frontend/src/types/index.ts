export type ResearchTaskStatus = 'PENDING' | 'EXPANDING_QUERY' | 'COLLECTING' | 'RANKING' | 'ANALYZING' | 'GENERATING_REPORT' | 'COMPLETED' | 'PARTIAL' | 'FAILED'

export interface ResearchTask { id: number; platform: string; topic: string; keywords: string[]; expanded_keywords: Record<string, string[]> | null; time_range: string; max_items: number; research_goals: string | null; status: ResearchTaskStatus; error_message: string | null; created_at: string; updated_at: string }
export interface ResearchTaskCreate { platform: string; topic: string; keywords: string[]; time_range: string; max_items: number; research_goals?: string }
export interface AppSetting { key: string; value: unknown; description: string | null; updated_at: string }
export interface RankingConfig { id?: number; name: string; enabled: boolean; like_weight: number; favorite_weight: number; comment_weight: number; share_weight: number; view_weight: number; freshness_half_life_hours: number; growth_window_hours: number }
export interface PlatformConfig { id?: number; name: string; search_url_template: string | null; selectors: Record<string, string>; parser_rules: Record<string, unknown>; enabled: boolean }
export interface AIProviderConfig { id?: number; name: string; provider_type: string; base_url: string | null; model_name: string | null; api_key?: string | null; timeout_seconds: number; max_retries: number; enabled: boolean }
export interface PromptTemplate { id?: number; name: string; purpose: string; template: string; enabled: boolean }
