export type ResearchTaskStatus = 'PENDING' | 'EXPANDING_QUERY' | 'COLLECTING' | 'RANKING' | 'ANALYZING' | 'GENERATING_REPORT' | 'COMPLETED' | 'PARTIAL' | 'FAILED'

export interface ResearchTask { id: number; platform: string; topic: string; keywords: string[]; expanded_keywords: Record<string, string[]> | null; time_range: string; max_items: number; research_goals: string | null; status: ResearchTaskStatus; error_message: string | null; current_stage?: string | null; progress?: number | null; collected_count?: number | null; created_at: string; updated_at: string }
export interface ResearchTaskCreate { platform: string; topic: string; keywords: string[]; time_range: string; max_items: number; research_goals?: string }
export interface ContentItem { id: number; research_task_id: number; platform: string; external_id: string; url: string; title: string | null; text: string | null; author_name: string | null; published_at: string | null; like_count: number | null; favorite_count: number | null; comment_count: number | null; share_count: number | null; view_count: number | null; media_type: string | null; image_urls: string[]; local_image_paths: string[]; video_urls: string[]; query_keyword: string | null; collected_at: string; raw_data: Record<string, unknown> | null; error_message?: string | null }
export interface AppSetting { key: string; value: unknown; description: string | null; updated_at: string }
export interface RankingConfig { id?: number; name: string; enabled: boolean; like_weight: number; favorite_weight: number; comment_weight: number; share_weight: number; view_weight: number; freshness_half_life_hours: number; growth_window_hours: number }
export interface PlatformConfig { id?: number; name: string; search_url_template: string | null; selectors: Record<string, string | Record<string, string>>; parser_rules: Record<string, unknown>; enabled: boolean }
export interface PlatformConfigTestResult { success: boolean; search_result_count: number; first_result: Record<string, unknown> | null; detail_result: Record<string, unknown> | null; message: string | null }
export interface BrowserConnectionTestResult { success: boolean; message: string }
export interface AIProviderConfig { id?: number; name: string; provider_type: string; base_url: string | null; model_name: string | null; api_key?: string | null; timeout_seconds: number; max_retries: number; enabled: boolean }
export interface AIProviderConfigTestResult { success: boolean; endpoint: string; response_preview: string | null; message: string }
export interface PromptTemplate { id?: number; name: string; purpose: string; template: string; enabled: boolean }

export type PublicMetricKey = 'like_count' | 'favorite_count' | 'comment_count' | 'share_count' | 'view_count'
export interface RankingItem {
  content_item_id?: number
  content_id?: number
  title?: string | null
  url?: string
  metrics?: Partial<Record<PublicMetricKey, number>>
  rank?: number | null
  engagement_score?: number | null
  freshness_score?: number | null
  growth_score?: number | null
  hot_score?: number | null
  item?: ContentItem
  content?: ContentItem
  [key: string]: unknown
}
export interface TaskRankings {
  hot: RankingItem[]
  rising: RankingItem[]
  boards: Record<string, RankingItem[]>
}
export interface TextAnalysis {
  hook_type?: string | null
  title_structure?: string | null
  opening_hook?: string | null
  writing_style?: string | null
  emotion?: string | null
  pain_points?: string[]
  benefits?: string[]
  target_audience?: string[]
  scenario?: string[]
  cta?: string | null
  hashtags?: string[]
  topic_tags?: string[]
  reusable_patterns?: string[]
  [key: string]: unknown
}
export interface VisualAnalysis {
  subject?: string | null
  main_colors?: string[]
  secondary_colors?: string[]
  style?: string | null
  composition?: string | null
  camera_angle?: string | null
  lighting?: string | null
  background?: string | null
  visual_focus?: string | null
  scene?: string | null
  mood?: string | null
  target_audience?: string[]
  notable_elements?: string[]
  reusable_visual_patterns?: string[]
  domain_attributes?: Record<string, unknown>
  confidence?: number | null
  [key: string]: unknown
}
export interface ContentAnalysis {
  content_item_id?: number
  content_id?: number
  title?: string | null
  url?: string
  content?: ContentItem
  item?: ContentItem
  text_analysis?: TextAnalysis | null
  visual_analysis?: VisualAnalysis | null
  visual_analyses?: VisualAnalysis[]
  local_image_paths?: string[]
  objective_facts?: Record<string, unknown>
  content_analysis?: {
    why_it_may_be_popular?: string | null
    core_content_elements?: string[]
    core_visual_elements?: string[]
    target_audience?: string[]
    emotional_value?: string | null
    reusable_patterns?: string[]
    trend_tags?: string[]
    evidence?: string[] | Record<string, unknown>
    limitations?: string[]
  } | null
  analysis_error?: string | null
  why_it_may_be_popular?: string | null
  core_content_elements?: string[]
  core_visual_elements?: string[]
  target_audience?: string[]
  emotional_value?: string | null
  reusable_patterns?: string[]
  trend_tags?: string[]
  evidence?: string[] | Record<string, unknown>
  limitations?: string[]
  error_message?: string | null
  [key: string]: unknown
}
export interface TaskAnalysisResult { items: ContentAnalysis[]; limitations: string[] }
export interface TrendAnalysis {
  hot_topics?: string[]
  rising_topics?: string[]
  visual_patterns?: string[]
  copywriting_patterns?: string[]
  audience_patterns?: string[]
  scenario_patterns?: string[]
  style_patterns?: string[]
  domain_patterns?: string[]
  insufficient_data?: boolean
  limitations?: string[]
  limitation?: string | null
  [key: string]: unknown
}

export interface CreativeConcept {
  id?: number
  name: string
  concept: string
  target_audience: string[]
  scenario: string[]
  style: string | null
  main_elements: string[]
  trend_basis: string[]
  differentiation: string | null
  [key: string]: unknown
}

export interface ImagePrompt {
  id?: number
  concept_id?: number
  concept_name?: string
  concept?: CreativeConcept | string | null
  trend_basis: string[]
  hero_prompt: string | null
  detail_prompt: string | null
  lifestyle_prompt: string | null
  cover_prompt: string | null
  negative_prompt: string | null
  [key: string]: unknown
}

export interface TaskReport {
  summary: string | null
  markdown: string | null
  limitations: string[]
  [key: string]: unknown
}
