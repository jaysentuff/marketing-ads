'use client';

import { useEffect, useState } from 'react';
import { api, type SpendOutcomeCorrelation, type ChannelCorrelation, type RecommendationsResponse, type BudgetRecommendation } from '@/lib/api';
import { formatCurrency } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  XCircle,
  HelpCircle,
  ArrowUpRight,
  ArrowDownRight,
  Activity,
  Target,
  DollarSign,
  Users,
  ShoppingCart,
  Search,
  Zap,
  Check,
  Loader2,
} from 'lucide-react';
import { cn } from '@/lib/utils';

export default function SignalTriangulationPage() {
  const [correlation, setCorrelation] = useState<SpendOutcomeCorrelation | null>(null);
  const [channelCorr, setChannelCorr] = useState<ChannelCorrelation | null>(null);
  const [recommendations, setRecommendations] = useState<RecommendationsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDays, setSelectedDays] = useState<7 | 14 | 30>(7);
  const [completingActions, setCompletingActions] = useState<Set<string>>(new Set());
  const [completedActions, setCompletedActions] = useState<Set<string>>(new Set());

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [corrData, channelData, recsData] = await Promise.all([
        api.getCorrelation(selectedDays),
        api.getChannelCorrelation(selectedDays),
        api.getRecommendations(selectedDays),
      ]);
      setCorrelation(corrData);
      setChannelCorr(channelData);
      setRecommendations(recsData);
      setCompletedActions(new Set()); // Reset completed when fetching new data
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to load data';
      // If the error is about needing more data, suggest a smaller timeframe
      if (errorMsg.includes('Need at least') || errorMsg.includes('Not enough data')) {
        setError(`Not enough historical data for ${selectedDays}-day comparison. Try 7d or 14d.`);
      } else {
        setError(errorMsg);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleCompleteAction = async (rec: BudgetRecommendation) => {
    if (completingActions.has(rec.id) || completedActions.has(rec.id)) return;

    setCompletingActions(prev => new Set(prev).add(rec.id));
    try {
      // Fetch current metrics for snapshot (like Action Board does)
      const reportData = await api.getReport();
      const summary = reportData?.report?.summary || {};
      const metricsSnapshot = {
        cam_per_order: summary.blended_cam_per_order || 0,
        total_orders: summary.total_orders || 0,
        total_ad_spend: summary.total_ad_spend || 0,
        total_cam: summary.blended_cam || 0,
      };

      // Calculate the change amount and percent (matching Action Board format)
      const changeAmount = rec.new_daily - rec.current_daily;
      const changePercent = rec.current_daily > 0
        ? Math.round((changeAmount / rec.current_daily) * 100)
        : 0;

      // Determine action type and format description like Action Board
      const isIncrease = rec.action_type.includes('INCREASE') || rec.action_type.includes('SCALE');
      const actionType = isIncrease ? 'spend_increase' :
                        rec.action_type.includes('HOLD') ? 'strategy_change' : 'spend_decrease';

      // Format description like Action Board: "Increased budget +$X/day (+Y%)"
      const description = isIncrease
        ? `Increased budget +$${Math.abs(changeAmount).toFixed(0)}/day (+${Math.abs(changePercent)}%)`
        : rec.action_type.includes('HOLD')
        ? `Maintained budget at $${rec.current_daily.toFixed(0)}/day`
        : `Decreased budget -$${Math.abs(changeAmount).toFixed(0)}/day (-${Math.abs(changePercent)}%)`;

      await api.addChangelogEntry({
        action_type: actionType,
        description: description,
        channel: rec.channel === 'Meta' ? 'Meta Ads' : rec.channel === 'Google' ? 'Google Ads' : rec.channel,
        campaign: rec.campaign === 'All Campaigns' ? undefined : rec.campaign,
        amount: Math.abs(changeAmount),
        percent_change: Math.abs(changePercent),
        notes: `Signal Triangulation recommendation. Reason: ${rec.reason}`,
        metrics_snapshot: metricsSnapshot,
      });
      setCompletedActions(prev => new Set(prev).add(rec.id));
    } catch (err) {
      console.error('Failed to log action:', err);
    } finally {
      setCompletingActions(prev => {
        const newSet = new Set(prev);
        newSet.delete(rec.id);
        return newSet;
      });
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedDays]);

  const getDirectionIcon = (direction: string) => {
    if (direction === 'up') return <TrendingUp className="text-green-500" size={18} />;
    if (direction === 'down') return <TrendingDown className="text-red-500" size={18} />;
    return <Minus className="text-gray-400" size={18} />;
  };

  const getAgreementBadge = (agreement: string) => {
    if (agreement === 'agree') {
      return (
        <span className="px-2 py-0.5 text-xs font-medium bg-green-100 text-green-700 rounded-full">
          Agrees
        </span>
      );
    }
    if (agreement === 'disagree') {
      return (
        <span className="px-2 py-0.5 text-xs font-medium bg-red-100 text-red-700 rounded-full">
          Conflicts
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-600 rounded-full">
        Neutral
      </span>
    );
  };

  const getVerdictStyle = (status: string) => {
    switch (status) {
      case 'confident':
      case 'likely_working':
      case 'efficient':
        return { bg: 'bg-green-50', border: 'border-green-200', icon: CheckCircle, iconColor: 'text-green-500' };
      case 'concerning':
        return { bg: 'bg-red-50', border: 'border-red-200', icon: XCircle, iconColor: 'text-red-500' };
      case 'expected_decline':
      case 'monitoring':
        return { bg: 'bg-yellow-50', border: 'border-yellow-200', icon: AlertCircle, iconColor: 'text-yellow-500' };
      default:
        return { bg: 'bg-gray-50', border: 'border-gray-200', icon: HelpCircle, iconColor: 'text-gray-500' };
    }
  };

  const getChangeColor = (change: number) => {
    if (change > 5) return 'text-green-600';
    if (change < -5) return 'text-red-600';
    return 'text-gray-600';
  };

  const formatChange = (change: number) => {
    const sign = change >= 0 ? '+' : '';
    return `${sign}${change.toFixed(1)}%`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">Signal Triangulation</h1>
        <div className="bg-red-50 border border-red-200 rounded-xl p-6">
          <div className="flex items-center gap-3">
            <AlertCircle className="text-red-500" size={24} />
            <div>
              <h2 className="font-semibold text-red-800">Unable to load data</h2>
              <p className="text-red-600 text-sm">{error}</p>
            </div>
          </div>
          <button
            onClick={fetchData}
            className="mt-4 px-4 py-2 bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition-colors"
          >
            Try Again
          </button>
        </div>
      </div>
    );
  }

  if (!correlation) return null;

  const verdictStyle = getVerdictStyle(correlation.verdict.status);
  const VerdictIcon = verdictStyle.icon;

  return (
    <div>
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Signal Triangulation</h1>
          <p className="text-gray-500 mt-1">
            Measure real outcomes, not attributed conversions
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex rounded-lg border border-gray-200 overflow-hidden">
            {([7, 14, 30] as const).map((days) => (
              <button
                key={days}
                onClick={() => setSelectedDays(days)}
                className={cn(
                  'px-4 py-2 text-sm font-medium transition-colors',
                  selectedDays === days
                    ? 'bg-primary-600 text-white'
                    : 'bg-white text-gray-600 hover:bg-gray-50'
                )}
              >
                {days}d
              </button>
            ))}
          </div>
          <button
            onClick={fetchData}
            className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <RefreshCw size={18} />
          </button>
        </div>
      </div>

      {/* Main Verdict Card */}
      <div className={cn('rounded-xl border-2 p-6 mb-6', verdictStyle.bg, verdictStyle.border)}>
        <div className="flex items-start gap-4">
          <VerdictIcon className={cn('flex-shrink-0', verdictStyle.iconColor)} size={32} />
          <div className="flex-1">
            <h2 className="text-xl font-bold text-gray-900 mb-2">
              {correlation.verdict.status === 'confident' && 'Marketing is Working'}
              {correlation.verdict.status === 'likely_working' && 'Signals Look Good'}
              {correlation.verdict.status === 'concerning' && 'Warning: Signals Conflict'}
              {correlation.verdict.status === 'inconclusive' && 'Need More Data'}
              {correlation.verdict.status === 'expected_decline' && 'Expected Decline'}
              {correlation.verdict.status === 'efficient' && 'Operating Efficiently'}
              {correlation.verdict.status === 'monitoring' && 'Monitoring'}
              {correlation.verdict.status === 'stable' && 'Stable Performance'}
            </h2>
            <p className="text-gray-700">{correlation.verdict.message}</p>
            <div className="mt-4 flex items-center gap-6">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">Spend:</span>
                <span className={cn('font-semibold', getChangeColor(correlation.changes.ad_spend_pct))}>
                  {formatChange(correlation.changes.ad_spend_pct)}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-500">Signals:</span>
                <span className="font-semibold text-green-600">{correlation.signal_summary.agree} agree</span>
                <span className="text-gray-400">|</span>
                <span className="font-semibold text-red-600">{correlation.signal_summary.disagree} conflict</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Period Comparison */}
      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        {/* Current Period */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900">Current Period</h3>
            <span className="text-sm text-gray-500">Last {selectedDays} days</span>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <DollarSign className="text-blue-600" size={20} />
              </div>
              <div>
                <p className="text-xs text-gray-500">Ad Spend</p>
                <p className="font-semibold text-gray-900">{formatCurrency(correlation.current_totals.ad_spend)}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <Activity className="text-green-600" size={20} />
              </div>
              <div>
                <p className="text-xs text-gray-500">Shopify Revenue</p>
                <p className="font-semibold text-gray-900">{formatCurrency(correlation.current_totals.shopify_revenue)}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Users className="text-purple-600" size={20} />
              </div>
              <div>
                <p className="text-xs text-gray-500">New Customers</p>
                <p className="font-semibold text-gray-900">{correlation.current_totals.new_customers}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-orange-100 rounded-lg">
                <ShoppingCart className="text-orange-600" size={20} />
              </div>
              <div>
                <p className="text-xs text-gray-500">Amazon Sales</p>
                <p className="font-semibold text-gray-900">{formatCurrency(correlation.current_totals.amazon_sales)}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Previous Period */}
        <div className="bg-gray-50 rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-700">Previous Period</h3>
            <span className="text-sm text-gray-500">Prior {selectedDays} days</span>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-200 rounded-lg">
                <DollarSign className="text-gray-500" size={20} />
              </div>
              <div>
                <p className="text-xs text-gray-500">Ad Spend</p>
                <p className="font-semibold text-gray-700">{formatCurrency(correlation.previous_totals.ad_spend)}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-200 rounded-lg">
                <Activity className="text-gray-500" size={20} />
              </div>
              <div>
                <p className="text-xs text-gray-500">Shopify Revenue</p>
                <p className="font-semibold text-gray-700">{formatCurrency(correlation.previous_totals.shopify_revenue)}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-200 rounded-lg">
                <Users className="text-gray-500" size={20} />
              </div>
              <div>
                <p className="text-xs text-gray-500">New Customers</p>
                <p className="font-semibold text-gray-700">{correlation.previous_totals.new_customers}</p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-gray-200 rounded-lg">
                <ShoppingCart className="text-gray-500" size={20} />
              </div>
              <div>
                <p className="text-xs text-gray-500">Amazon Sales</p>
                <p className="font-semibold text-gray-700">{formatCurrency(correlation.previous_totals.amazon_sales)}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Signal Agreement */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex items-center gap-2 mb-4">
          <Target className="text-primary-600" size={24} />
          <h3 className="text-lg font-semibold text-gray-900">Signal Agreement Analysis</h3>
        </div>
        <p className="text-gray-600 text-sm mb-4">
          When ad spend goes <span className={cn('font-semibold', correlation.spend_direction === 'up' ? 'text-green-600' : correlation.spend_direction === 'down' ? 'text-red-600' : 'text-gray-600')}>
            {correlation.spend_direction}
          </span>, do business metrics follow?
        </p>
        <div className="space-y-3">
          {correlation.signals.map((signal) => (
            <div
              key={signal.metric}
              className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
            >
              <div className="flex items-center gap-3">
                {getDirectionIcon(signal.direction)}
                <div>
                  <p className="font-medium text-gray-900">{signal.label}</p>
                  <p className={cn('text-sm', getChangeColor(signal.change_pct))}>
                    {formatChange(signal.change_pct)}
                  </p>
                </div>
              </div>
              {getAgreementBadge(signal.agreement)}
            </div>
          ))}
        </div>
      </div>

      {/* Efficiency Metrics */}
      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        {/* MER */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-gray-900">MER (Marketing Efficiency Ratio)</h3>
              <p className="text-xs text-gray-500">Revenue / Ad Spend - Higher is better</p>
            </div>
            {correlation.efficiency.mer_change_pct >= 0 ? (
              <ArrowUpRight className="text-green-500" size={24} />
            ) : (
              <ArrowDownRight className="text-red-500" size={24} />
            )}
          </div>
          <div className="flex items-end gap-4">
            <div>
              <p className="text-3xl font-bold text-gray-900">{correlation.efficiency.current_mer.toFixed(2)}x</p>
              <p className="text-sm text-gray-500">Current</p>
            </div>
            <div className="text-gray-400 text-2xl font-light">vs</div>
            <div>
              <p className="text-2xl font-semibold text-gray-600">{correlation.efficiency.previous_mer.toFixed(2)}x</p>
              <p className="text-sm text-gray-500">Previous</p>
            </div>
            <div className={cn('ml-auto text-lg font-semibold', getChangeColor(correlation.efficiency.mer_change_pct))}>
              {formatChange(correlation.efficiency.mer_change_pct)}
            </div>
          </div>
        </div>

        {/* NCAC */}
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="font-semibold text-gray-900">True NCAC (New Customer Cost)</h3>
              <p className="text-xs text-gray-500">Ad Spend / New Customers - Lower is better</p>
            </div>
            {correlation.efficiency.ncac_change_pct <= 0 ? (
              <ArrowDownRight className="text-green-500" size={24} />
            ) : (
              <ArrowUpRight className="text-red-500" size={24} />
            )}
          </div>
          <div className="flex items-end gap-4">
            <div>
              <p className="text-3xl font-bold text-gray-900">{formatCurrency(correlation.efficiency.current_ncac)}</p>
              <p className="text-sm text-gray-500">Current</p>
            </div>
            <div className="text-gray-400 text-2xl font-light">vs</div>
            <div>
              <p className="text-2xl font-semibold text-gray-600">{formatCurrency(correlation.efficiency.previous_ncac)}</p>
              <p className="text-sm text-gray-500">Previous</p>
            </div>
            <div className={cn('ml-auto text-lg font-semibold', correlation.efficiency.ncac_change_pct <= 0 ? 'text-green-600' : 'text-red-600')}>
              {formatChange(correlation.efficiency.ncac_change_pct)}
            </div>
          </div>
        </div>
      </div>

      {/* Channel Correlation */}
      {channelCorr && (
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Channel Spend Correlation</h3>
          <p className="text-gray-600 text-sm mb-4">
            Which platform's spend changes correlate better with business outcomes?
          </p>
          <div className="grid md:grid-cols-2 gap-6">
            {/* Google */}
            <div className="p-4 bg-gray-50 rounded-lg">
              <h4 className="font-medium text-gray-900 mb-3">Google Ads</h4>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-600 text-sm">Spend Change</span>
                  <span className={cn('font-medium', getChangeColor(channelCorr.channels.google.spend_change_pct))}>
                    {formatChange(channelCorr.channels.google.spend_change_pct)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 text-sm">Revenue Change</span>
                  <span className={cn('font-medium', getChangeColor(channelCorr.channels.google.revenue_change_pct))}>
                    {formatChange(channelCorr.channels.google.revenue_change_pct)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 text-sm">New Customers Change</span>
                  <span className={cn('font-medium', getChangeColor(channelCorr.channels.google.new_customer_change_pct))}>
                    {formatChange(channelCorr.channels.google.new_customer_change_pct)}
                  </span>
                </div>
              </div>
            </div>

            {/* Meta */}
            <div className="p-4 bg-gray-50 rounded-lg">
              <h4 className="font-medium text-gray-900 mb-3">Meta Ads</h4>
              <div className="space-y-2">
                <div className="flex justify-between">
                  <span className="text-gray-600 text-sm">Spend Change</span>
                  <span className={cn('font-medium', getChangeColor(channelCorr.channels.meta.spend_change_pct))}>
                    {formatChange(channelCorr.channels.meta.spend_change_pct)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 text-sm">Revenue Change</span>
                  <span className={cn('font-medium', getChangeColor(channelCorr.channels.meta.revenue_change_pct))}>
                    {formatChange(channelCorr.channels.meta.revenue_change_pct)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-600 text-sm">New Customers Change</span>
                  <span className={cn('font-medium', getChangeColor(channelCorr.channels.meta.new_customer_change_pct))}>
                    {formatChange(channelCorr.channels.meta.new_customer_change_pct)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Recommended Actions */}
      {recommendations && recommendations.recommendations.length > 0 && (
        <div className="mt-6 bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-primary-100 rounded-lg">
              <Zap className="text-primary-600" size={24} />
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Recommended Actions</h3>
              <p className="text-sm text-gray-500">
                Strategy: <span className="font-medium capitalize">{recommendations.strategy.overall}</span>
                {' '}&mdash;{' '}{recommendations.strategy.reason}
              </p>
            </div>
          </div>

          {/* Efficiency Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 p-4 bg-gray-50 rounded-lg">
            <div>
              <p className="text-xs text-gray-500">Current NCAC</p>
              <p className="font-semibold text-gray-900">{formatCurrency(recommendations.efficiency.current_ncac)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Target NCAC</p>
              <p className="font-semibold text-gray-900">{formatCurrency(recommendations.efficiency.ncac_target)}</p>
            </div>
            <div>
              <p className="text-xs text-gray-500">NCAC Headroom</p>
              <p className={cn('font-semibold', recommendations.efficiency.ncac_headroom > 0 ? 'text-green-600' : 'text-red-600')}>
                {recommendations.efficiency.ncac_headroom > 0 ? '+' : ''}{formatCurrency(recommendations.efficiency.ncac_headroom)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500">Current MER</p>
              <p className="font-semibold text-gray-900">{recommendations.efficiency.current_mer.toFixed(2)}x</p>
            </div>
          </div>

          {/* Action Cards */}
          <div className="space-y-3">
            {recommendations.recommendations.map((rec) => (
              <div
                key={rec.id}
                className={cn(
                  'flex items-center justify-between p-4 rounded-lg border transition-all',
                  completedActions.has(rec.id)
                    ? 'bg-green-50 border-green-200'
                    : rec.priority === 'HIGH'
                    ? 'bg-red-50 border-red-200'
                    : rec.priority === 'MEDIUM'
                    ? 'bg-yellow-50 border-yellow-200'
                    : 'bg-gray-50 border-gray-200'
                )}
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={cn(
                      'px-2 py-0.5 text-xs font-medium rounded-full',
                      rec.priority === 'HIGH' ? 'bg-red-100 text-red-700' :
                      rec.priority === 'MEDIUM' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-gray-100 text-gray-700'
                    )}>
                      {rec.priority}
                    </span>
                    <span className="text-xs text-gray-500">{rec.channel}</span>
                  </div>
                  <p className="font-medium text-gray-900">{rec.action}</p>
                  <p className="text-sm text-gray-600 truncate">{rec.campaign}</p>
                  <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
                    <span>Current: {formatCurrency(rec.current_daily)}/day</span>
                    <span className="text-primary-600 font-medium">→ New: {formatCurrency(rec.new_daily)}/day</span>
                    {rec.weekly_impact > 0 && (
                      <span className="text-green-600">+{formatCurrency(rec.weekly_impact)}/week</span>
                    )}
                  </div>
                </div>
                <div className="ml-4 flex-shrink-0">
                  {completedActions.has(rec.id) ? (
                    <div className="flex items-center gap-2 text-green-600">
                      <CheckCircle size={20} />
                      <span className="text-sm font-medium">Logged</span>
                    </div>
                  ) : (
                    <button
                      onClick={() => handleCompleteAction(rec)}
                      disabled={completingActions.has(rec.id)}
                      className={cn(
                        'flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm transition-colors',
                        completingActions.has(rec.id)
                          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                          : 'bg-primary-600 text-white hover:bg-primary-700'
                      )}
                    >
                      {completingActions.has(rec.id) ? (
                        <>
                          <Loader2 size={16} className="animate-spin" />
                          Logging...
                        </>
                      ) : (
                        <>
                          <Check size={16} />
                          Complete
                        </>
                      )}
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>

          <p className="mt-4 text-xs text-gray-500">
            Clicking "Complete" logs the action to your Activity Log for tracking. Review results in the next comparison period.
          </p>
        </div>
      )}

      {/* Explanation */}
      <div className="mt-6 bg-blue-50 border border-blue-200 rounded-xl p-6">
        <h3 className="font-semibold text-blue-900 mb-2">How This Works</h3>
        <p className="text-blue-800 text-sm">
          This page shows what ACTUALLY happened to your business when ad spend changed - no attribution models,
          no platform claims. If you increased spend and revenue, new customers, AND Amazon sales all went up,
          your marketing is working. If signals conflict (spend up, revenue down), something needs investigation.
          MER and True NCAC are ungameable metrics calculated from real Shopify data.
        </p>
      </div>
    </div>
  );
}
