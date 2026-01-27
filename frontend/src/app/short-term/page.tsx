'use client';

import { useEffect, useState } from 'react';
import { api, type TimeframeSummary } from '@/lib/api';
import { formatCurrency } from '@/lib/utils';
import {
  AlertTriangle,
  TrendingDown,
  TrendingUp,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  XCircle,
  ShoppingCart,
  Info,
} from 'lucide-react';
import { cn } from '@/lib/utils';

interface TimeframeData {
  yesterday: TimeframeSummary | null;
  threeDays: TimeframeSummary | null;
  sevenDays: TimeframeSummary | null;
}

export default function ShortTermAnalysis() {
  const [data, setData] = useState<TimeframeData>({
    yesterday: null,
    threeDays: null,
    sevenDays: null,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedTimeframe, setSelectedTimeframe] = useState<1 | 3 | 7>(1);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [yesterday, threeDays, sevenDays] = await Promise.all([
        api.getTimeframeSummary(1),
        api.getTimeframeSummary(3),
        api.getTimeframeSummary(7),
      ]);
      setData({ yesterday, threeDays, sevenDays });
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
        <h1 className="text-3xl font-bold text-gray-900 mb-4">Short-Term Analysis</h1>
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

  const timeframes = [
    { key: 1 as const, label: 'Yesterday', data: data.yesterday },
    { key: 3 as const, label: '3 Days', data: data.threeDays },
    { key: 7 as const, label: '7 Days', data: data.sevenDays },
  ];

  const selectedData = timeframes.find(t => t.key === selectedTimeframe)?.data;

  return (
    <div>
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Short-Term Analysis</h1>
          <p className="text-gray-500 mt-1">
            Compare performance across timeframes - catch problems early
          </p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <RefreshCw size={18} />
          Refresh
        </button>
      </div>

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

            {/* Amazon Halo Effect */}
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
    </div>
  );
}
