'use client';

import { useEffect, useState } from 'react';
import { MetricCard } from '@/components/MetricCard';
import { api, type TimeframeSummary } from '@/lib/api';
import { formatCurrency, getHealthStatus, cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  Pause,
  AlertTriangle,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  XCircle,
  ShoppingCart,
  Info,
  LayoutDashboard,
  Clock,
} from 'lucide-react';

type TabType = 'overview' | 'short-term';

interface TimeframeData {
  yesterday: TimeframeSummary | null;
  threeDays: TimeframeSummary | null;
  sevenDays: TimeframeSummary | null;
}

export default function Dashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  // Overview state
  const [report, setReport] = useState<any>(null);
  const [signals, setSignals] = useState<any>(null);

  // Short-term state
  const [timeframeData, setTimeframeData] = useState<TimeframeData>({
    yesterday: null,
    threeDays: null,
    sevenDays: null,
  });
  const [selectedTimeframe, setSelectedTimeframe] = useState<1 | 3 | 7>(1);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);

      const [reportData, signalsData, yesterday, threeDays, sevenDays] = await Promise.all([
        api.getReport(),
        api.getSignals(),
        api.getTimeframeSummary(1),
        api.getTimeframeSummary(3),
        api.getTimeframeSummary(7),
      ]);

      setReport(reportData);
      setSignals(signalsData);
      setTimeframeData({ yesterday, threeDays, sevenDays });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const getChangeColor = (change: number) => {
    if (change > 5) return 'text-green-600';
    if (change < -5) return 'text-red-600';
    return 'text-gray-600';
  };

  const getCamStatus = (camPerOrder: number) => {
    if (camPerOrder >= 24) return { color: 'green', message: 'Healthy' };
    if (camPerOrder >= 20) return { color: 'green', message: 'On target' };
    if (camPerOrder >= 16) return { color: 'yellow', message: 'Below target' };
    return { color: 'red', message: 'Critical' };
  };

  const getRoasColor = (roas: number) => {
    if (roas >= 3) return 'text-green-600';
    if (roas >= 2) return 'text-yellow-600';
    return 'text-red-600';
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
        <h1 className="text-3xl font-bold text-gray-900 mb-4">Dashboard</h1>
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

  // Overview data
  const r = report?.report || {};
  const summary = r.summary || {};
  const channels = r.channels || {};
  const camPerOrder = summary.blended_cam_per_order || 0;
  const health = getHealthStatus(camPerOrder);

  const spendDecision = signals?.spend_decision || 'hold';
  const spendConfig = {
    increase: { color: 'bg-green-100 border-green-500', text: 'text-green-800', icon: TrendingUp, label: 'SCALE SPEND', detail: 'CMAM is healthy. Consider increasing ad spend by 10-15%.' },
    decrease: { color: 'bg-red-100 border-red-500', text: 'text-red-800', icon: TrendingDown, label: 'CUT SPEND', detail: 'CMAM is below target. Reduce spend on worst performers.' },
    hold: { color: 'bg-blue-100 border-blue-500', text: 'text-blue-800', icon: Pause, label: 'HOLD SPEND', detail: 'CMAM is stable. Maintain current spend levels.' },
  };
  const spend = spendConfig[spendDecision as keyof typeof spendConfig];
  const SpendIcon = spend.icon;

  // Short-term data
  const timeframes = [
    { key: 1 as const, label: 'Yesterday', data: timeframeData.yesterday },
    { key: 3 as const, label: '3 Days', data: timeframeData.threeDays },
    { key: 7 as const, label: '7 Days', data: timeframeData.sevenDays },
  ];
  const selectedData = timeframes.find(t => t.key === selectedTimeframe)?.data;

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-gray-500 mt-1">Quick data views and metrics</p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <RefreshCw size={18} />
          Refresh
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 mb-6 border-b border-gray-200">
        <button
          onClick={() => setActiveTab('overview')}
          className={cn(
            'flex items-center gap-2 px-4 py-3 font-medium text-sm border-b-2 transition-colors',
            activeTab === 'overview'
              ? 'border-primary-600 text-primary-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          )}
        >
          <LayoutDashboard size={18} />
          Overview (30 Day)
        </button>
        <button
          onClick={() => setActiveTab('short-term')}
          className={cn(
            'flex items-center gap-2 px-4 py-3 font-medium text-sm border-b-2 transition-colors',
            activeTab === 'short-term'
              ? 'border-primary-600 text-primary-600'
              : 'border-transparent text-gray-500 hover:text-gray-700'
          )}
        >
          <Clock size={18} />
          Short-Term (1/3/7 Day)
        </button>
      </div>

      {/* Overview Tab */}
      {activeTab === 'overview' && (
        <>
          {/* Compact Status Row */}
          <div className="flex gap-4 mb-6">
            <div className={`flex-1 ${health.bgColor} border ${health.color === 'text-green-600' ? 'border-green-200' : health.color === 'text-yellow-600' ? 'border-yellow-200' : 'border-red-200'} rounded-lg p-4 flex items-center gap-3`}>
              <div className={`w-3 h-3 rounded-full ${health.color === 'text-green-600' ? 'bg-green-500' : health.color === 'text-yellow-600' ? 'bg-yellow-500' : 'bg-red-500'}`} />
              <div>
                <span className={`font-semibold ${health.color}`}>{health.status}</span>
                <span className="text-gray-600 ml-2">CMAM/Order: {formatCurrency(camPerOrder)}</span>
              </div>
            </div>
            <div className={`flex-1 ${spend.color} border border-green-200 rounded-lg p-4 flex items-center gap-3`}>
              <SpendIcon className={`h-5 w-5 ${spend.text}`} />
              <div>
                <span className={`font-semibold ${spend.text}`}>{spend.label}</span>
                <span className="text-gray-600 ml-2 text-sm">{spend.detail}</span>
              </div>
            </div>
          </div>

          {/* Key Metrics */}
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Key Metrics (Last 30 Days)</h2>
          <div className="grid grid-cols-4 gap-4 mb-8">
            <MetricCard
              label="Total CMAM"
              value={summary.blended_cam || 0}
              format="currency"
              help="Contribution Margin After Marketing"
            />
            <MetricCard
              label="CMAM per Order"
              value={camPerOrder}
              format="currency"
              change={camPerOrder - 20}
              changeLabel="vs $20 target"
            />
            <MetricCard
              label="Total Orders"
              value={summary.total_orders || 0}
              format="number"
            />
            <MetricCard
              label="Ad Spend"
              value={summary.total_ad_spend || 0}
              format="currency"
            />
          </div>

          {/* Channel Performance */}
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Channel Performance</h2>
          <div className="grid grid-cols-4 gap-4 mb-8">
            {Object.entries(channels).map(([name, data]: [string, any]) => (
              <div key={name} className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
                <h3 className="font-semibold text-gray-900">{name}</h3>
                <p className="text-2xl font-bold text-gray-900 mt-2">
                  {formatCurrency(data.cam || 0)}
                </p>
                <p className="text-gray-500 text-sm mt-1">
                  {(data.orders || 0).toLocaleString()} orders | {(data.roas || 0).toFixed(2)}x ROAS
                </p>
              </div>
            ))}
          </div>

          {/* Alerts */}
          {signals?.alerts?.length > 0 && (
            <div className="mb-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Alerts</h2>
              {signals.alerts.map((alert: string, i: number) => (
                <div key={i} className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-2 flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-yellow-600 flex-shrink-0 mt-0.5" />
                  <span className="text-yellow-800">{alert}</span>
                </div>
              ))}
            </div>
          )}

          {/* TOF Assessment */}
          {signals?.tof_assessment && (
            <div className="mb-8">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">TOF Assessment</h2>
              <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
                <p className="text-blue-800 text-sm">
                  <strong>Why TOF is measured differently:</strong> TOF campaigns show low direct ROAS because customers don't buy immediately.
                  They see your ad, then Google your brand later.
                </p>
              </div>
              <div className="grid grid-cols-4 gap-4">
                <MetricCard
                  label="Meta First-Click (7d)"
                  value={signals.tof_assessment.meta_first_click_7d || 0}
                  format="currency"
                />
                <MetricCard
                  label="Blended NCAC"
                  value={signals.tof_assessment.ncac_7d_avg || 0}
                  format="currency"
                  help="Target: <$50"
                />
                <MetricCard
                  label="Branded Search %"
                  value={signals.tof_assessment.branded_search_pct || 0}
                  format="percent"
                />
                <MetricCard
                  label="Amazon Sales (7d)"
                  value={signals.tof_assessment.amazon_sales_7d || 0}
                  format="currency"
                />
              </div>
              {signals.tof_assessment.message && (
                <div className={`mt-4 p-4 rounded-lg ${
                  signals.tof_assessment.verdict === 'healthy' ? 'bg-green-50 border border-green-200' :
                  signals.tof_assessment.verdict === 'working' ? 'bg-blue-50 border border-blue-200' :
                  'bg-yellow-50 border border-yellow-200'
                }`}>
                  <strong className="uppercase">{signals.tof_assessment.verdict}:</strong> {signals.tof_assessment.message}
                </div>
              )}
            </div>
          )}

          <p className="text-gray-400 text-sm">Report generated: {report?.generated_at}</p>
        </>
      )}

      {/* Short-Term Tab */}
      {activeTab === 'short-term' && (
        <>
          {/* Timeframe Comparison Cards */}
          <div className="grid grid-cols-3 gap-4 mb-8">
            {timeframes.map((tf) => {
              if (!tf.data) return null;
              const camStatus = getCamStatus(tf.data.summary.cam_per_order);
              const isSelected = selectedTimeframe === tf.key;

              return (
                <button
                  key={tf.key}
                  onClick={() => setSelectedTimeframe(tf.key)}
                  className={cn(
                    'text-left rounded-xl p-5 border-2 transition-all',
                    isSelected
                      ? 'border-primary-500 ring-2 ring-primary-200'
                      : 'border-gray-200 hover:border-gray-300',
                    camStatus.color === 'green'
                      ? 'bg-green-50'
                      : camStatus.color === 'yellow'
                      ? 'bg-yellow-50'
                      : 'bg-red-50'
                  )}
                >
                  <div className="flex items-center justify-between mb-3">
                    <span className="font-semibold text-gray-900">{tf.label}</span>
                    {camStatus.color === 'green' ? (
                      <CheckCircle className="text-green-500" size={20} />
                    ) : camStatus.color === 'yellow' ? (
                      <AlertTriangle className="text-yellow-500" size={20} />
                    ) : (
                      <XCircle className="text-red-500" size={20} />
                    )}
                  </div>

                  <div className="space-y-2">
                    <div>
                      <p className="text-xs text-gray-500">CMAM/Order</p>
                      <p className={cn(
                        'text-xl font-bold',
                        camStatus.color === 'green' ? 'text-green-700' :
                        camStatus.color === 'yellow' ? 'text-yellow-700' : 'text-red-700'
                      )}>
                        {formatCurrency(tf.data.summary.cam_per_order)}
                      </p>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-200/50">
                      <div>
                        <p className="text-xs text-gray-500">Revenue</p>
                        <p className="font-semibold text-gray-900">{formatCurrency(tf.data.summary.total_sales)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">Orders</p>
                        <p className="font-semibold text-gray-900">{tf.data.summary.total_orders}</p>
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-200/50">
                      <div>
                        <p className="text-xs text-gray-500">Spend</p>
                        <p className="font-medium text-gray-700">{formatCurrency(tf.data.summary.total_spend)}</p>
                      </div>
                      <div>
                        <p className="text-xs text-gray-500">ROAS</p>
                        <p className={cn('font-medium', getRoasColor(tf.data.summary.blended_roas))}>
                          {tf.data.summary.blended_roas.toFixed(2)}x
                        </p>
                      </div>
                    </div>

                    <p className={cn(
                      'text-xs pt-2',
                      getChangeColor(tf.data.changes.cam_change_pct)
                    )}>
                      {tf.data.changes.cam_change_pct >= 0 ? '+' : ''}
                      {tf.data.changes.cam_change_pct.toFixed(1)}% vs prev period
                    </p>
                  </div>
                </button>
              );
            })}
          </div>

          {/* Selected Timeframe Details */}
          {selectedData && (
            <>
              <div className="flex items-center gap-2 mb-4">
                <h2 className="text-xl font-semibold text-gray-900">
                  {timeframes.find(t => t.key === selectedTimeframe)?.label} Details
                </h2>
                <span className="text-sm text-gray-500">
                  ({selectedData.timeframe.label})
                </span>
              </div>

              {/* Channel Breakdown */}
              <div className="grid lg:grid-cols-3 gap-6 mb-8">
                <div className="bg-white rounded-xl border border-gray-200 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Google Ads</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Spend</span>
                      <span className="font-medium text-gray-900">{formatCurrency(selectedData.channels.google.spend)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Revenue</span>
                      <span className="font-medium text-gray-900">{formatCurrency(selectedData.channels.google.revenue)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">ROAS</span>
                      <span className={cn('font-medium', getRoasColor(selectedData.channels.google.roas))}>
                        {selectedData.channels.google.roas.toFixed(2)}x
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Campaigns</span>
                      <span className="font-medium text-gray-900">{selectedData.channels.google.campaigns}</span>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-xl border border-gray-200 p-6">
                  <h3 className="text-lg font-semibold text-gray-900 mb-4">Meta Ads</h3>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Spend</span>
                      <span className="font-medium text-gray-900">{formatCurrency(selectedData.channels.meta.spend)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Revenue</span>
                      <span className="font-medium text-gray-900">{formatCurrency(selectedData.channels.meta.revenue)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">ROAS</span>
                      <span className={cn('font-medium', getRoasColor(selectedData.channels.meta.roas))}>
                        {selectedData.channels.meta.roas.toFixed(2)}x
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Campaigns</span>
                      <span className="font-medium text-gray-900">{selectedData.channels.meta.campaigns}</span>
                    </div>
                  </div>
                </div>

                {/* Amazon */}
                <div className="bg-orange-50 rounded-xl border border-orange-200 p-6">
                  <div className="flex items-center justify-between mb-4">
                    <div className="flex items-center gap-2">
                      <ShoppingCart className="text-orange-600" size={20} />
                      <h3 className="text-lg font-semibold text-gray-900">Amazon</h3>
                    </div>
                    {selectedData.channels.amazon?.data_source === 'api' && (
                      <span className="text-xs px-2 py-1 bg-green-100 text-green-700 rounded-full font-medium">
                        Live API
                      </span>
                    )}
                  </div>
                  <div className="space-y-3">
                    <div className="flex justify-between">
                      <span className="text-gray-600">Sales</span>
                      <span className="font-medium text-orange-700">{formatCurrency(selectedData.channels.amazon?.sales || 0)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Orders</span>
                      <span className="font-medium text-gray-900">{selectedData.channels.amazon?.orders || 0}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Ad Spend</span>
                      <span className="font-medium text-gray-900">{formatCurrency(selectedData.channels.amazon?.spend || 0)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-600">Amazon ROAS</span>
                      <span className={cn('font-medium', getRoasColor(selectedData.channels.amazon?.roas || 0))}>
                        {(selectedData.channels.amazon?.roas || 0).toFixed(2)}x
                      </span>
                    </div>
                  </div>
                  <div className="mt-4 pt-3 border-t border-orange-200">
                    <div className="flex items-start gap-2">
                      <Info className="text-orange-500 flex-shrink-0 mt-0.5" size={14} />
                      <p className="text-xs text-orange-700">
                        {selectedData.channels.amazon?.data_source === 'api'
                          ? 'Sales and orders from Amazon Seller Central API in real-time.'
                          : 'Customers see Meta/Google ads, then buy on Amazon. Track this as indirect attribution.'}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Problem Campaigns */}
              {selectedData.problem_campaigns.length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-6 mb-8">
                  <div className="flex items-center gap-2 mb-4">
                    <AlertTriangle className="text-red-500" size={24} />
                    <h3 className="text-lg font-semibold text-red-800">
                      Problem Campaigns ({selectedData.problem_campaigns.length})
                    </h3>
                  </div>
                  <p className="text-red-600 text-sm mb-4">
                    ROAS below 1.5x with significant spend
                  </p>
                  <div className="space-y-3">
                    {selectedData.problem_campaigns.map((camp, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between bg-white rounded-lg p-3 border border-red-100"
                      >
                        <div>
                          <p className="font-medium text-gray-900 truncate max-w-md">{camp.name}</p>
                          <p className="text-sm text-gray-500">{camp.channel}</p>
                        </div>
                        <div className="text-right">
                          <p className="font-medium text-red-600">{camp.roas.toFixed(2)}x ROAS</p>
                          <p className="text-sm text-gray-500">{formatCurrency(camp.spend)} spent</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Winning Campaigns */}
              {selectedData.winning_campaigns.length > 0 && (
                <div className="bg-green-50 border border-green-200 rounded-xl p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <CheckCircle className="text-green-500" size={24} />
                    <h3 className="text-lg font-semibold text-green-800">
                      Winning Campaigns ({selectedData.winning_campaigns.length})
                    </h3>
                  </div>
                  <p className="text-green-600 text-sm mb-4">
                    ROAS above 3x - consider scaling
                  </p>
                  <div className="space-y-3">
                    {selectedData.winning_campaigns.map((camp, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between bg-white rounded-lg p-3 border border-green-100"
                      >
                        <div>
                          <p className="font-medium text-gray-900 truncate max-w-md">{camp.name}</p>
                          <p className="text-sm text-gray-500">{camp.channel}</p>
                        </div>
                        <div className="text-right">
                          <p className="font-medium text-green-600">{camp.roas.toFixed(2)}x ROAS</p>
                          <p className="text-sm text-gray-500">{formatCurrency(camp.revenue)} revenue</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* No campaigns found */}
              {selectedData.problem_campaigns.length === 0 && selectedData.winning_campaigns.length === 0 && (
                <div className="bg-gray-50 border border-gray-200 rounded-xl p-6 text-center">
                  <p className="text-gray-600">
                    Not enough campaign data with significant spend to identify clear winners or problems.
                  </p>
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}
