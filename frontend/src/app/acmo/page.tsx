'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import ReactMarkdown from 'react-markdown';
import {
  Brain,
  Loader2,
  AlertCircle,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Clock,
  TrendingUp,
  TrendingDown,
  Minus,
  ChevronDown,
  ChevronRight,
  Sparkles,
  Target,
  BarChart3,
  GitBranch,
  History,
} from 'lucide-react';

interface Recommendation {
  id: string;
  type: string;
  action: string;
  channel?: string;
  campaign?: string;
  reason: string;
  confidence: string;
  signals: string[];
  budget_amount?: number;
  budget_percent?: number;
  status?: string;
  created_at?: string;
}

interface SynthesisResult {
  synthesis: string;
  recommendations_extracted: Recommendation[];
  recommendations_saved: number;
  usage: { input_tokens: number; output_tokens: number };
  generated_at: string;
}

interface PastRecommendation {
  id: string;
  action: string;
  channel?: string;
  status: string;
  outcome?: string;
  created_at: string;
  reason?: string;
}

export default function ACMOPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<{ available: boolean } | null>(null);
  const [synthesis, setSynthesis] = useState<SynthesisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [customQuestion, setCustomQuestion] = useState('');
  const [showRecommendations, setShowRecommendations] = useState(true);
  const [pastRecommendations, setPastRecommendations] = useState<PastRecommendation[]>([]);
  const [recommendationsSummary, setRecommendationsSummary] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<'analysis' | 'history' | 'patterns'>('analysis');

  useEffect(() => {
    const init = async () => {
      try {
        const [statusData, summaryData, pastData] = await Promise.all([
          api.getSynthesisStatus(),
          api.getRecommendationsSummary(30).catch(() => null),
          api.getAiRecommendations(30, 20).catch(() => ({ recommendations: [] })),
        ]);
        setStatus(statusData);
        setRecommendationsSummary(summaryData);
        setPastRecommendations(pastData.recommendations || []);
      } catch (err) {
        console.error('Failed to init ACMO:', err);
      }
    };
    init();
  }, []);

  const runAnalysis = async (question?: string) => {
    setLoading(true);
    setError(null);

    try {
      const result = await api.analyze(question, 30, true);
      if (result.success) {
        setSynthesis(result);
        // Refresh past recommendations after new analysis
        const pastData = await api.getAiRecommendations(30, 20).catch(() => ({ recommendations: [] }));
        setPastRecommendations(pastData.recommendations || []);
      } else {
        setError('Analysis failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  const handleCustomQuestion = (e: React.FormEvent) => {
    e.preventDefault();
    if (customQuestion.trim()) {
      runAnalysis(customQuestion);
    }
  };

  const updateRecommendationStatus = async (recId: string, status: 'done' | 'ignored', reason?: string) => {
    try {
      await api.updateRecommendationStatus(recId, status, undefined, reason);
      // Refresh
      const pastData = await api.getAiRecommendations(30, 20).catch(() => ({ recommendations: [] }));
      setPastRecommendations(pastData.recommendations || []);
    } catch (err) {
      console.error('Failed to update status:', err);
    }
  };

  if (status && !status.available) {
    return (
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-8">AI Chief Marketing Officer</h1>
        <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-8 text-center">
          <AlertCircle className="h-12 w-12 text-yellow-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-yellow-800">AI Not Available</h2>
          <p className="text-yellow-700 mt-2">
            Please set ANTHROPIC_API_KEY in your .env file to enable AI analysis.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-gradient-to-br from-purple-500 to-indigo-600 rounded-xl">
            <Brain className="h-8 w-8 text-white" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900">AI Chief Marketing Officer</h1>
            <p className="text-gray-500">Autonomous marketing optimization powered by multi-signal analysis</p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('analysis')}
          className={`px-4 py-2 font-medium transition-colors border-b-2 -mb-px ${
            activeTab === 'analysis'
              ? 'text-purple-600 border-purple-600'
              : 'text-gray-500 border-transparent hover:text-gray-700'
          }`}
        >
          <div className="flex items-center gap-2">
            <Sparkles size={18} />
            Analysis
          </div>
        </button>
        <button
          onClick={() => setActiveTab('history')}
          className={`px-4 py-2 font-medium transition-colors border-b-2 -mb-px ${
            activeTab === 'history'
              ? 'text-purple-600 border-purple-600'
              : 'text-gray-500 border-transparent hover:text-gray-700'
          }`}
        >
          <div className="flex items-center gap-2">
            <History size={18} />
            Recommendation History
          </div>
        </button>
        <button
          onClick={() => setActiveTab('patterns')}
          className={`px-4 py-2 font-medium transition-colors border-b-2 -mb-px ${
            activeTab === 'patterns'
              ? 'text-purple-600 border-purple-600'
              : 'text-gray-500 border-transparent hover:text-gray-700'
          }`}
        >
          <div className="flex items-center gap-2">
            <GitBranch size={18} />
            Learning Patterns
          </div>
        </button>
      </div>

      {/* Analysis Tab */}
      {activeTab === 'analysis' && (
        <div className="space-y-6">
          {/* Quick Actions */}
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Run Analysis</h2>

            <div className="flex flex-wrap gap-3 mb-4">
              <button
                onClick={() => runAnalysis()}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg font-medium hover:from-purple-700 hover:to-indigo-700 disabled:opacity-50 transition-all"
              >
                {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Brain className="h-5 w-5" />}
                Full Analysis & Recommendations
              </button>

              <button
                onClick={() => runAnalysis("What are the top 3 actions I should take today?")}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                <Target className="h-5 w-5" />
                Today's Top Actions
              </button>

              <button
                onClick={() => runAnalysis("How are my TOF campaigns performing? Should I adjust them?")}
                disabled={loading}
                className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 disabled:opacity-50"
              >
                <BarChart3 className="h-5 w-5" />
                TOF Analysis
              </button>
            </div>

            {/* Custom Question */}
            <form onSubmit={handleCustomQuestion} className="flex gap-3">
              <input
                type="text"
                value={customQuestion}
                onChange={(e) => setCustomQuestion(e.target.value)}
                placeholder="Ask a specific question about your marketing..."
                className="flex-1 px-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500"
                disabled={loading}
              />
              <button
                type="submit"
                disabled={loading || !customQuestion.trim()}
                className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 disabled:opacity-50"
              >
                Ask
              </button>
            </form>
          </div>

          {/* Error */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3">
              <AlertCircle className="h-5 w-5 text-red-500 flex-shrink-0" />
              <p className="text-red-700">{error}</p>
            </div>
          )}

          {/* Loading State */}
          {loading && (
            <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
              <Loader2 className="h-12 w-12 animate-spin text-purple-600 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Analyzing Marketing Performance</h3>
              <p className="text-gray-500">
                Gathering signals from multiple sources, analyzing cross-channel correlations,
                and generating recommendations...
              </p>
            </div>
          )}

          {/* Synthesis Result */}
          {synthesis && !loading && (
            <div className="space-y-6">
              {/* Extracted Recommendations */}
              {synthesis.recommendations_extracted.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <button
                    onClick={() => setShowRecommendations(!showRecommendations)}
                    className="w-full px-6 py-4 flex items-center justify-between bg-gradient-to-r from-purple-50 to-indigo-50 border-b border-gray-200"
                  >
                    <div className="flex items-center gap-3">
                      <Sparkles className="h-5 w-5 text-purple-600" />
                      <span className="font-semibold text-gray-900">
                        {synthesis.recommendations_extracted.length} Recommendations Extracted
                      </span>
                      {synthesis.recommendations_saved > 0 && (
                        <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full">
                          {synthesis.recommendations_saved} saved for tracking
                        </span>
                      )}
                    </div>
                    {showRecommendations ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                  </button>

                  {showRecommendations && (
                    <div className="divide-y divide-gray-100">
                      {synthesis.recommendations_extracted.map((rec, i) => (
                        <div key={i} className="p-4 hover:bg-gray-50">
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                {rec.type === 'scale' && <TrendingUp className="h-4 w-4 text-green-500" />}
                                {rec.type === 'cut' && <TrendingDown className="h-4 w-4 text-red-500" />}
                                {rec.type === 'hold' && <Minus className="h-4 w-4 text-gray-500" />}
                                {rec.type === 'test' && <Target className="h-4 w-4 text-blue-500" />}
                                <span className="font-medium text-gray-900">{rec.action}</span>
                                <span className={`text-xs px-2 py-0.5 rounded-full ${
                                  rec.confidence === 'high' ? 'bg-green-100 text-green-700' :
                                  rec.confidence === 'low' ? 'bg-yellow-100 text-yellow-700' :
                                  'bg-gray-100 text-gray-700'
                                }`}>
                                  {rec.confidence} confidence
                                </span>
                              </div>
                              {rec.reason && (
                                <p className="text-sm text-gray-600 mt-1">{rec.reason}</p>
                              )}
                              {rec.channel && (
                                <span className="inline-block mt-2 text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                                  {rec.channel}
                                </span>
                              )}
                            </div>
                            {rec.budget_amount && (
                              <div className="text-right">
                                <span className={`font-semibold ${rec.type === 'scale' ? 'text-green-600' : rec.type === 'cut' ? 'text-red-600' : 'text-gray-600'}`}>
                                  {rec.type === 'cut' ? '-' : '+'}${Math.abs(rec.budget_amount).toFixed(0)}/day
                                </span>
                                {rec.budget_percent && (
                                  <span className="text-xs text-gray-500 block">
                                    ({rec.budget_percent}%)
                                  </span>
                                )}
                              </div>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Full Analysis */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900">Full Analysis</h3>
                  <div className="text-xs text-gray-500">
                    {synthesis.usage.input_tokens.toLocaleString()} input / {synthesis.usage.output_tokens.toLocaleString()} output tokens
                  </div>
                </div>
                <div className="prose prose-sm max-w-none prose-headings:text-gray-900 prose-p:text-gray-700 prose-strong:text-gray-900 prose-ul:text-gray-700 prose-li:text-gray-700">
                  <ReactMarkdown>{synthesis.synthesis}</ReactMarkdown>
                </div>
              </div>
            </div>
          )}

          {/* Empty State */}
          {!synthesis && !loading && !error && (
            <div className="bg-gradient-to-br from-purple-50 to-indigo-50 rounded-xl border border-purple-100 p-12 text-center">
              <Brain className="h-16 w-16 text-purple-400 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-gray-900 mb-2">Ready to Analyze</h3>
              <p className="text-gray-600 max-w-md mx-auto mb-6">
                The AI CMO will analyze your marketing data from multiple sources,
                consider cross-channel effects, and provide actionable recommendations
                with full reasoning.
              </p>
              <button
                onClick={() => runAnalysis()}
                className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg font-medium hover:from-purple-700 hover:to-indigo-700"
              >
                <Brain className="h-5 w-5" />
                Start Analysis
              </button>
            </div>
          )}
        </div>
      )}

      {/* History Tab */}
      {activeTab === 'history' && (
        <div className="bg-white rounded-xl border border-gray-200">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">Recommendation History</h2>
            <p className="text-sm text-gray-500">Track what was recommended and what was acted upon</p>
          </div>

          {pastRecommendations.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              <History className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p>No recommendations yet. Run an analysis to generate recommendations.</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-100">
              {pastRecommendations.map((rec) => (
                <div key={rec.id} className="p-4 hover:bg-gray-50">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        {rec.status === 'done' && <CheckCircle2 className="h-4 w-4 text-green-500" />}
                        {rec.status === 'ignored' && <XCircle className="h-4 w-4 text-red-500" />}
                        {rec.status === 'pending' && <Clock className="h-4 w-4 text-yellow-500" />}
                        <span className="font-medium text-gray-900">{rec.action}</span>
                        {rec.outcome && (
                          <span className={`text-xs px-2 py-0.5 rounded-full ${
                            rec.outcome === 'positive' ? 'bg-green-100 text-green-700' :
                            rec.outcome === 'negative' ? 'bg-red-100 text-red-700' :
                            'bg-gray-100 text-gray-700'
                          }`}>
                            {rec.outcome} outcome
                          </span>
                        )}
                      </div>
                      {rec.reason && (
                        <p className="text-sm text-gray-600">{rec.reason}</p>
                      )}
                      <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                        {rec.channel && <span>{rec.channel}</span>}
                        <span>{new Date(rec.created_at).toLocaleDateString()}</span>
                      </div>
                    </div>

                    {rec.status === 'pending' && (
                      <div className="flex gap-2">
                        <button
                          onClick={() => updateRecommendationStatus(rec.id, 'done')}
                          className="px-3 py-1 text-sm bg-green-50 text-green-700 rounded-lg hover:bg-green-100"
                        >
                          Mark Done
                        </button>
                        <button
                          onClick={() => {
                            const reason = prompt('Why was this recommendation not followed?');
                            if (reason !== null) {
                              updateRecommendationStatus(rec.id, 'ignored', reason);
                            }
                          }}
                          className="px-3 py-1 text-sm bg-gray-50 text-gray-700 rounded-lg hover:bg-gray-100"
                        >
                          Ignore
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Patterns Tab */}
      {activeTab === 'patterns' && (
        <div className="space-y-6">
          {recommendationsSummary ? (
            <>
              {/* Summary Stats */}
              <div className="grid grid-cols-4 gap-4">
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="text-2xl font-bold text-gray-900">{recommendationsSummary.total_recommendations}</div>
                  <div className="text-sm text-gray-500">Total Recommendations</div>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="text-2xl font-bold text-green-600">{recommendationsSummary.acted_upon}</div>
                  <div className="text-sm text-gray-500">Acted Upon</div>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="text-2xl font-bold text-gray-400">{recommendationsSummary.ignored}</div>
                  <div className="text-sm text-gray-500">Ignored</div>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="text-2xl font-bold text-blue-600">
                    {recommendationsSummary.outcomes.positive}/{recommendationsSummary.acted_upon || 1}
                  </div>
                  <div className="text-sm text-gray-500">Success Rate</div>
                </div>
              </div>

              {/* Outcome Breakdown */}
              <div className="bg-white rounded-xl border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">Outcome Distribution</h3>
                <div className="flex gap-4">
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-green-500 rounded"></div>
                    <span className="text-sm text-gray-700">Positive: {recommendationsSummary.outcomes.positive}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-red-500 rounded"></div>
                    <span className="text-sm text-gray-700">Negative: {recommendationsSummary.outcomes.negative}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-gray-400 rounded"></div>
                    <span className="text-sm text-gray-700">Neutral: {recommendationsSummary.outcomes.neutral}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="w-4 h-4 bg-yellow-400 rounded"></div>
                    <span className="text-sm text-gray-700">Pending: {recommendationsSummary.outcomes.pending}</span>
                  </div>
                </div>
              </div>

              {/* Observed Patterns */}
              {recommendationsSummary.patterns && recommendationsSummary.patterns.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Observed Patterns</h3>
                  <div className="space-y-3">
                    {recommendationsSummary.patterns.map((pattern: string, i: number) => (
                      <div key={i} className="flex items-start gap-3 p-3 bg-purple-50 rounded-lg">
                        <GitBranch className="h-5 w-5 text-purple-600 flex-shrink-0 mt-0.5" />
                        <p className="text-gray-700">{pattern}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Examples */}
              {recommendationsSummary.examples && recommendationsSummary.examples.length > 0 && (
                <div className="bg-white rounded-xl border border-gray-200 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Examples</h3>
                  <div className="space-y-4">
                    {recommendationsSummary.examples.map((ex: any, i: number) => (
                      <div key={i} className={`p-4 rounded-lg border ${
                        ex.type === 'success' ? 'border-green-200 bg-green-50' :
                        ex.type === 'failure' ? 'border-red-200 bg-red-50' :
                        'border-gray-200 bg-gray-50'
                      }`}>
                        <div className="flex items-center gap-2 mb-2">
                          {ex.type === 'success' && <CheckCircle2 className="h-4 w-4 text-green-600" />}
                          {ex.type === 'failure' && <XCircle className="h-4 w-4 text-red-600" />}
                          {ex.type === 'ignored' && <Clock className="h-4 w-4 text-gray-600" />}
                          <span className="font-medium text-gray-900 capitalize">{ex.type}</span>
                        </div>
                        <p className="text-sm text-gray-700">{ex.recommendation}</p>
                        {ex.metrics_change && (
                          <p className="text-xs text-gray-500 mt-2">Result: {ex.metrics_change}</p>
                        )}
                        {ex.reason_ignored && (
                          <p className="text-xs text-gray-500 mt-2">Reason ignored: {ex.reason_ignored}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 p-12 text-center text-gray-500">
              <GitBranch className="h-12 w-12 mx-auto mb-4 text-gray-300" />
              <p>No patterns available yet. Run analyses and track outcomes to build learning data.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
