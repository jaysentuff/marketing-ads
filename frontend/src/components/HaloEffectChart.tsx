'use client';

import { useEffect, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { api, HaloEffectResponse } from '@/lib/api';
import { formatCurrency } from '@/lib/utils';
import { RefreshCw, TrendingUp, TrendingDown, Minus, Info } from 'lucide-react';

interface HaloEffectChartProps {
  days?: number;
}

export function HaloEffectChart({ days = 30 }: HaloEffectChartProps) {
  const [data, setData] = useState<HaloEffectResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedDays, setSelectedDays] = useState(days);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await api.getHaloEffect(selectedDays);
      setData(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [selectedDays]);

  // Format chart data with short date labels
  const chartData = data?.data.map((d) => ({
    ...d,
    dateLabel: new Date(d.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  })) || [];

  // Custom tooltip
  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white p-3 shadow-lg rounded-lg border border-gray-200">
          <p className="font-medium text-gray-900 mb-2">{label}</p>
          {payload.map((entry: any, index: number) => (
            <p key={index} className="text-sm" style={{ color: entry.color }}>
              {entry.name}: {formatCurrency(entry.value)}
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  // Get correlation indicator
  const getCorrelationIndicator = () => {
    if (!data?.summary) return null;
    const corr = data.summary.spend_amazon_correlation;
    if (corr > 0.4) {
      return { icon: TrendingUp, color: 'text-green-600', bg: 'bg-green-50' };
    } else if (corr < -0.4) {
      return { icon: TrendingDown, color: 'text-red-600', bg: 'bg-red-50' };
    }
    return { icon: Minus, color: 'text-yellow-600', bg: 'bg-yellow-50' };
  };

  const indicator = getCorrelationIndicator();

  if (loading) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-orange-600"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="text-center text-red-600 py-8">
          <p>{error}</p>
          <button
            onClick={fetchData}
            className="mt-4 px-4 py-2 bg-orange-600 text-white rounded-lg hover:bg-orange-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="px-6 py-4 border-b border-gray-200">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Ad Spend vs Amazon Sales</h3>
            <p className="text-sm text-gray-500">Track the halo effect correlation over time</p>
          </div>
          <div className="flex items-center gap-3">
            {/* Time range selector */}
            <select
              value={selectedDays}
              onChange={(e) => setSelectedDays(Number(e.target.value))}
              className="px-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-orange-500"
            >
              <option value={7}>Last 7 days</option>
              <option value={14}>Last 14 days</option>
              <option value={30}>Last 30 days</option>
            </select>
            <button
              onClick={fetchData}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <RefreshCw size={18} />
            </button>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="p-6">
        <div className="h-80">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="dateLabel"
                tick={{ fontSize: 12, fill: '#6b7280' }}
                tickLine={false}
              />
              <YAxis
                yAxisId="left"
                tick={{ fontSize: 12, fill: '#6b7280' }}
                tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                tickLine={false}
                axisLine={false}
              />
              <YAxis
                yAxisId="right"
                orientation="right"
                tick={{ fontSize: 12, fill: '#6b7280' }}
                tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Line
                yAxisId="left"
                type="monotone"
                dataKey="total_spend"
                name="Total Ad Spend"
                stroke="#3b82f6"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6 }}
              />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="amazon_sales"
                name="Amazon Sales"
                stroke="#f97316"
                strokeWidth={2}
                dot={false}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Summary stats */}
      {data?.summary && (
        <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
          <div className="grid grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Total Ad Spend</p>
              <p className="text-lg font-semibold text-blue-600">
                {formatCurrency(data.summary.total_ad_spend)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Amazon Sales</p>
              <p className="text-lg font-semibold text-orange-600">
                {formatCurrency(data.summary.total_amazon_sales)}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Correlation</p>
              <div className="flex items-center gap-2">
                {indicator && (
                  <span className={`p-1 rounded ${indicator.bg}`}>
                    <indicator.icon size={16} className={indicator.color} />
                  </span>
                )}
                <p className="text-lg font-semibold text-gray-900">
                  {data.summary.spend_amazon_correlation.toFixed(2)}
                </p>
              </div>
            </div>
            <div>
              <p className="text-xs text-gray-500 uppercase tracking-wide">Signal</p>
              <p className={`text-lg font-semibold ${
                data.summary.correlation_strength.includes('positive') ? 'text-green-600' :
                data.summary.correlation_strength.includes('negative') ? 'text-red-600' :
                'text-yellow-600'
              }`}>
                {data.summary.correlation_strength}
              </p>
            </div>
          </div>

          {/* Interpretation help */}
          <div className="mt-4 flex items-start gap-2 text-sm text-gray-600">
            <Info size={16} className="flex-shrink-0 mt-0.5" />
            <p>
              {data.summary.spend_amazon_correlation > 0.4 ? (
                <>
                  <span className="font-medium text-green-700">Good sign!</span> Ad spend and Amazon sales are moving together.
                  This suggests your ads are driving brand awareness that converts on Amazon.
                </>
              ) : data.summary.spend_amazon_correlation < -0.4 ? (
                <>
                  <span className="font-medium text-red-700">Needs review.</span> Ad spend and Amazon sales are moving in opposite directions.
                  Check if there are external factors affecting Amazon performance.
                </>
              ) : (
                <>
                  <span className="font-medium text-yellow-700">Neutral correlation.</span> No strong relationship between ad spend and Amazon sales in this period.
                  Consider a longer timeframe or review campaign targeting.
                </>
              )}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
