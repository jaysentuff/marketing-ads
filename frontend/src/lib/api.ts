/**
 * API client for the TuffWraps Marketing API.
 */

const API_BASE = '/api';

async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
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
};

export default api;
