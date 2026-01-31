/**
 * API client for the TuffWraps Marketing API.
 */

// Use backend URL directly if available, otherwise use local proxy
const API_BASE = typeof window !== 'undefined' && process.env.NEXT_PUBLIC_BACKEND_URL
  ? `${process.env.NEXT_PUBLIC_BACKEND_URL}/api`
  : '/api';

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  try {
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
      ...options,
    });

    if (!response.ok) {
      // Try to get error details from response
      const errorText = await response.text();
      let errorDetail = `API error: ${response.status} ${response.statusText}`;

      try {
        const errorJson = JSON.parse(errorText);
        errorDetail = errorJson.detail || errorJson.message || errorDetail;
      } catch {
        // If not JSON, check for common issues
        if (response.status === 502 || response.status === 503) {
          errorDetail = 'Backend server is unavailable. Please check if the backend is running.';
        } else if (response.status === 404) {
          errorDetail = `Endpoint not found: ${endpoint}`;
        } else if (errorText) {
          errorDetail = errorText.substring(0, 200);
        }
      }

      throw new Error(errorDetail);
    }

    return response.json();
  } catch (err) {
    // Handle network errors (no response at all)
    if (err instanceof TypeError && err.message.includes('fetch')) {
      throw new Error('Network error: Cannot connect to the API server. Please check your connection.');
    }
    throw err;
  }
}

// Types
export interface Summary {
  cam_per_order: number;
  total_orders: number;
  total_revenue: number;
  total_ad_spend: number;
  total_cam: number;
  spend_decision: 'increase' | 'hold' | 'decrease';
  campaigns_to_scale_count: number;
  campaigns_to_watch_count: number;
  alerts_count: number;
  has_data: boolean;
  generated_at?: string;
  message?: string;
}

export interface ActionItem {
  id: string;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  action_type: string;
  action: string;
  campaign: string;
  channel: string;
  reason: string;
  budget_change: string;
  budget_amount: number;
  budget_percent: number;
  new_budget: string;
  icon: string;
}

export interface ActionsResponse {
  actions: ActionItem[];
  summary: {
    cam_per_order: number;
    total_orders: number;
    total_ad_spend: number;
    spend_decision: string;
  } | null;
  generated_at: string;
}

export interface ChangelogEntry {
  id: number;
  timestamp: string;
  action_type: string;
  description: string;
  channel?: string;
  campaign?: string;
  amount?: number;
  percent_change?: number;
  original_budget?: number;
  notes?: string;
  metrics_snapshot?: Record<string, number>;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ChatSession {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
  message_count?: number;
  preview?: string;
}

export interface ChatResponse {
  success: boolean;
  message: string;
  usage: {
    input_tokens: number;
    output_tokens: number;
  };
}

export interface TimeframeSummary {
  timeframe: {
    days: number;
    label: string;
    note?: string;
  };
  summary: {
    total_sales: number;
    total_orders: number;
    total_spend: number;
    total_cam: number;
    cam_per_order: number;
    avg_ncac: number;
    blended_roas: number;
  };
  changes: {
    sales_change_pct: number;
    orders_change_pct: number;
    cam_change_pct: number;
    comparison_period: string;
  };
  channels: {
    google: { spend: number; revenue: number; roas: number; campaigns: number };
    meta: { spend: number; revenue: number; roas: number; campaigns: number };
    amazon: { sales: number; orders: number; spend: number; roas: number; meta_first_click: number; data_source?: 'api' | 'kendall' | 'unknown' };
  };
  problem_campaigns: Array<{
    name: string;
    channel: string;
    spend: number;
    roas: number;
    days_active: number;
  }>;
  winning_campaigns: Array<{
    name: string;
    channel: string;
    spend: number;
    roas: number;
    revenue: number;
  }>;
  google_campaigns: any[];
  meta_campaigns: any[];
  daily_metrics: any[];
}

export interface HaloEffectDataPoint {
  date: string;
  total_spend: number;
  meta_spend: number;
  google_spend: number;
  amazon_sales: number;
  shopify_sales: number;
  meta_first_click: number;
}

export interface HaloEffectResponse {
  data: HaloEffectDataPoint[];
  summary: {
    days: number;
    data_points: number;
    total_ad_spend: number;
    total_amazon_sales: number;
    total_shopify_sales: number;
    spend_amazon_correlation: number;
    correlation_strength: string;
  };
}

export interface CorrelationSignal {
  metric: string;
  label: string;
  change_pct: number;
  direction: 'up' | 'down' | 'flat';
  agreement: 'agree' | 'disagree' | 'neutral';
}

export interface SpendOutcomeCorrelation {
  period: {
    days: number;
    current_start: string;
    previous_start: string;
    label: string;
  };
  current_totals: {
    ad_spend: number;
    shopify_revenue: number;
    shopify_orders: number;
    new_customers: number;
    amazon_sales: number;
    mer: number;
    ncac: number;
  };
  previous_totals: {
    ad_spend: number;
    shopify_revenue: number;
    shopify_orders: number;
    new_customers: number;
    amazon_sales: number;
    mer: number;
    ncac: number;
  };
  changes: {
    ad_spend_pct: number;
    shopify_revenue_pct: number;
    new_customers_pct: number;
    amazon_sales_pct: number;
    branded_search_pct: number;
    mer_pct: number;
    ncac_pct: number;
  };
  spend_direction: 'up' | 'down' | 'flat';
  signals: CorrelationSignal[];
  signal_summary: {
    agree: number;
    disagree: number;
    neutral: number;
  };
  efficiency: {
    current_mer: number;
    previous_mer: number;
    mer_change_pct: number;
    current_ncac: number;
    previous_ncac: number;
    ncac_change_pct: number;
    note: string;
  };
  verdict: {
    status: 'confident' | 'likely_working' | 'concerning' | 'inconclusive' | 'expected_decline' | 'efficient' | 'monitoring' | 'stable';
    message: string;
  };
  daily_trend: Array<{
    date: string;
    ad_spend: number;
    shopify_revenue: number;
    new_customers: number;
    amazon_sales: number;
  }>;
}

export interface ChannelCorrelation {
  period: {
    days: number;
    label: string;
  };
  channels: {
    google: {
      channel: string;
      current_spend: number;
      previous_spend: number;
      spend_change_pct: number;
      revenue_change_pct: number;
      new_customer_change_pct: number;
      revenue_correlation: number;
      nc_correlation: number;
    };
    meta: {
      channel: string;
      current_spend: number;
      previous_spend: number;
      spend_change_pct: number;
      revenue_change_pct: number;
      new_customer_change_pct: number;
      revenue_correlation: number;
      nc_correlation: number;
    };
  };
  recommendation: string | null;
}

export interface BudgetRecommendation {
  id: string;
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  action_type: string;
  channel: string;
  campaign: string;
  action: string;
  current_daily: number;
  new_daily: number;
  weekly_impact: number;
  reason: string;
}

export interface RecommendationsResponse {
  strategy: {
    overall: 'scale' | 'grow' | 'hold' | 'test';
    reason: string;
  };
  efficiency: {
    current_ncac: number;
    ncac_target: number;
    ncac_headroom: number;
    current_mer: number;
    mer_floor: number;
    mer_headroom: number;
  };
  signal_summary: {
    agree: number;
    disagree: number;
    neutral: number;
  };
  recommendations: BudgetRecommendation[];
  period_days: number;
}

// API Functions

export const api = {
  // Metrics
  getSummary: () => fetchApi<Summary>('/metrics/summary'),
  getSignals: () => fetchApi<any>('/metrics/signals'),
  getReport: () => fetchApi<any>('/metrics/report'),
  getBlended: () => fetchApi<any>('/metrics/blended'),
  getAttribution: () => fetchApi<any>('/metrics/attribution'),
  getChannel: (channel: string) => fetchApi<any>(`/metrics/channels/${channel}`),

  // Timeframe-based metrics (for short-term analysis)
  getTimeframeSummary: (days: number) => fetchApi<TimeframeSummary>(`/metrics/timeframe/${days}`),
  getTimeframeGoogle: (days: number) => fetchApi<any>(`/metrics/timeframe/${days}/google`),
  getTimeframeMeta: (days: number) => fetchApi<any>(`/metrics/timeframe/${days}/meta`),
  getAvailableTimeframes: () => fetchApi<{ timeframes: Array<{ days: number; label: string }> }>('/metrics/timeframes'),
  getHaloEffect: (days: number = 30) => fetchApi<HaloEffectResponse>(`/metrics/halo-effect?days=${days}`),

  // Signal Triangulation (Spend-to-Outcome Correlation)
  getCorrelation: (days: number = 14) => fetchApi<SpendOutcomeCorrelation>(`/metrics/correlation?days=${days}`),
  getChannelCorrelation: (days: number = 14) => fetchApi<ChannelCorrelation>(`/metrics/correlation/channels?days=${days}`),
  getRecommendations: (days: number = 7) => fetchApi<RecommendationsResponse>(`/metrics/recommendations?days=${days}`),

  // Actions
  getActions: () => fetchApi<ActionsResponse>('/actions/list'),
  completeActions: (actions: Array<{
    id: string;
    action_type: string;
    campaign: string;
    channel: string;
    budget_amount: number;
    budget_percent: number;
    reason: string;
  }>) => fetchApi<{ success: boolean; logged_count: number }>('/actions/complete', {
    method: 'POST',
    body: JSON.stringify({ actions }),
  }),

  // Changelog
  getChangelog: (days?: number, limit?: number) =>
    fetchApi<{ entries: ChangelogEntry[]; count: number }>(
      `/changelog/entries?days=${days || 30}&limit=${limit || 50}`
    ),
  addChangelogEntry: (entry: {
    action_type: string;
    description: string;
    channel?: string;
    campaign?: string;
    amount?: number;
    percent_change?: number;
    notes?: string;
    metrics_snapshot?: Record<string, number>;
    timestamp?: string;
  }) => fetchApi<{ success: boolean; entry: ChangelogEntry }>('/changelog/entries', {
    method: 'POST',
    body: JSON.stringify(entry),
  }),
  deleteChangelogEntry: (id: number) => fetchApi<{ success: boolean }>(`/changelog/entries/${id}`, {
    method: 'DELETE',
  }),
  updateChangelogEntry: (id: number, updates: {
    description?: string;
    amount?: number;
    percent_change?: number;
    original_budget?: number;
    notes?: string;
    channel?: string;
    campaign?: string;
    timestamp?: string;
  }) => fetchApi<{ success: boolean; entry: ChangelogEntry }>(`/changelog/entries/${id}`, {
    method: 'PUT',
    body: JSON.stringify(updates),
  }),
  getActionTypes: () => fetchApi<{ action_types: Array<{ value: string; label: string }> }>('/changelog/action-types'),

  // AI Chat
  getAiStatus: () => fetchApi<{ available: boolean; anthropic_installed: boolean; api_key_set: boolean }>('/ai/status'),
  chat: (messages: ChatMessage[], includeContext?: boolean) =>
    fetchApi<ChatResponse>('/ai/chat', {
      method: 'POST',
      body: JSON.stringify({ messages, include_context: includeContext ?? true }),
    }),
  getQuickQuestions: () => fetchApi<{ questions: Array<{ id: string; label: string; question: string }> }>('/ai/quick-questions'),

  // Chat Sessions
  getChatSessions: () => fetchApi<{ sessions: ChatSession[] }>('/ai/sessions'),
  createChatSession: (title?: string) =>
    fetchApi<{ success: boolean; session: ChatSession }>('/ai/sessions', {
      method: 'POST',
      body: JSON.stringify({ title }),
    }),
  getChatSession: (sessionId: string) =>
    fetchApi<{ session: ChatSession }>(`/ai/sessions/${sessionId}`),
  updateChatSession: (sessionId: string, messages: ChatMessage[], title?: string) =>
    fetchApi<{ success: boolean; session: ChatSession }>(`/ai/sessions/${sessionId}`, {
      method: 'PUT',
      body: JSON.stringify({ messages, title }),
    }),
  deleteChatSession: (sessionId: string) =>
    fetchApi<{ success: boolean }>(`/ai/sessions/${sessionId}`, {
      method: 'DELETE',
    }),

  // AI Synthesis (ACMO)
  getSynthesisStatus: () => fetchApi<{ available: boolean; anthropic_installed: boolean; api_key_configured: boolean }>('/synthesis/status'),
  analyze: (question?: string, days?: number, saveRecommendations?: boolean) =>
    fetchApi<{
      success: boolean;
      synthesis: string;
      recommendations_extracted: Array<{
        type: string;
        action: string;
        channel?: string;
        campaign?: string;
        reason: string;
        confidence: string;
        signals: string[];
        budget_amount?: number;
        budget_percent?: number;
      }>;
      recommendations_saved: number;
      context_summary: { days_analyzed: number; context_length: number };
      usage: { input_tokens: number; output_tokens: number };
      generated_at: string;
    }>('/synthesis/analyze', {
      method: 'POST',
      body: JSON.stringify({ question, days: days || 30, save_recommendations: saveRecommendations ?? true }),
    }),
  getSynthesisContext: (days?: number) =>
    fetchApi<{ context: string; length: number; days: number }>(`/synthesis/context?days=${days || 30}`),
  getMultiSignalCampaigns: (platform: 'facebook' | 'google', days?: number, minSpend?: number) =>
    fetchApi<{
      platform: string;
      channel_name: string;
      period_days: number;
      campaigns: Array<{
        campaign_id: string;
        campaign_name: string;
        platform: string;
        funnel_role: string;
        spend: number;
        daily_spend: number;
        platform_roas: number;
        kendall_lc_roas: number;
        kendall_fc_roas: number;
        attribution_gap: { gap_percent: number; trust_level: string; interpretation: string };
        sessions: number;
        bounce_rate: number;
        atc_rate: number;
        session_quality_score: number;
        weighted_score: number;
        confidence: string;
        signals_summary: {
          strengths: string[];
          concerns: string[];
          signals: string[];
          recommendation: string;
        };
      }>;
      summary: {
        total_campaigns: number;
        total_spend: number;
        blended_kendall_roas: number;
        blended_platform_roas: number;
        overall_attribution_gap_pct: number;
      };
    }>(`/synthesis/campaigns/${platform}?days=${days || 30}&min_spend=${minSpend || 50}`),
  getCrossChannelCorrelation: (days?: number) =>
    fetchApi<{
      period_days: number;
      data_points: number;
      correlations: Record<string, number>;
      best_meta_to_branded: { correlation: number; optimal_lag_days: number; strength: string };
      best_meta_to_google_fc: { correlation: number; optimal_lag_days: number; strength: string };
      interpretation: string[];
      implication: string;
    }>(`/synthesis/correlation/cross-channel?days=${days || 30}`),

  // AI Recommendations Tracking
  getAiRecommendations: (days?: number, limit?: number) =>
    fetchApi<{ recommendations: any[]; count: number }>(`/synthesis/recommendations?days=${days || 30}&limit=${limit || 50}`),
  getPendingRecommendations: (days?: number) =>
    fetchApi<{ recommendations: any[]; count: number }>(`/synthesis/recommendations/pending?days=${days || 7}`),
  getRecommendationsSummary: (days?: number) =>
    fetchApi<{
      summary: string;
      total_recommendations: number;
      acted_upon: number;
      ignored: number;
      outcomes: { positive: number; negative: number; neutral: number; pending: number };
      patterns: string[];
      examples: any[];
    }>(`/synthesis/recommendations/summary?days=${days || 30}`),
  updateRecommendationStatus: (recommendationId: string, status: 'pending' | 'done' | 'ignored' | 'partial', actionTaken?: string, reasonNotFollowed?: string) =>
    fetchApi<{ success: boolean; recommendation: any }>(`/synthesis/recommendations/${recommendationId}/status`, {
      method: 'PUT',
      body: JSON.stringify({ status, action_taken: actionTaken, reason_not_followed: reasonNotFollowed }),
    }),

  // Analysis History
  getAnalysisHistory: (limit?: number, offset?: number) =>
    fetchApi<{
      entries: Array<{
        id: string;
        timestamp: string;
        timestamp_display: string;
        question?: string;
        days_analyzed: number;
        summary: string;
        recommendations_count: number;
        recommendations_by_type: Record<string, number>;
      }>;
      total: number;
      limit: number;
      offset: number;
      has_more: boolean;
    }>(`/synthesis/history?limit=${limit || 20}&offset=${offset || 0}`),
  getAnalysisById: (entryId: string) =>
    fetchApi<{
      id: string;
      timestamp: string;
      timestamp_display: string;
      question?: string;
      days_analyzed: number;
      summary: string;
      synthesis: string;
      recommendations_count: number;
      recommendations_by_type: Record<string, number>;
      recommendations: Array<{
        type: string;
        action: string;
        channel?: string;
        reason: string;
        confidence: string;
        signals: string[];
        budget_amount?: number;
        budget_percent?: number;
      }>;
      usage: { input_tokens: number; output_tokens: number };
    }>(`/synthesis/history/${entryId}`),
  deleteAnalysis: (entryId: string) =>
    fetchApi<{ success: boolean }>(`/synthesis/history/${entryId}`, {
      method: 'DELETE',
    }),
};

export default api;
