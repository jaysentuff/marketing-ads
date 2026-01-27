'use client';

import { useEffect, useState } from 'react';
import { MetricCard } from '@/components/MetricCard';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/utils';
import { Target, RefreshCw, Info, ShoppingCart, TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { HaloEffectChart } from '@/components/HaloEffectChart';

export default function TOFAnalysis() {
  const [signals, setSignals] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      setLoading(true);
      const data = await api.getSignals();
      setSignals(data);
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  const tof = signals?.tof_assessment;

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">TOF Analysis</h1>
          <p className="text-gray-500 mt-1">Top-of-Funnel campaign performance</p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <RefreshCw size={18} />
          Refresh
        </button>
      </div>

      {/* TOF Explanation */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 mb-8">
        <div className="flex items-start gap-3">
          <Info className="h-6 w-6 text-blue-600 flex-shrink-0 mt-0.5" />
          <div>
            <h2 className="text-lg font-semibold text-blue-900">Why TOF is Measured Differently</h2>
            <p className="text-blue-800 mt-2">
              TOF (Top-of-Funnel) campaigns create awareness. Customers don't buy immediately -
              they see your ad, then Google your brand later. Direct ROAS will look bad, but that
              doesn't mean TOF isn't working.
            </p>
            <p className="text-blue-800 mt-2">
              <strong>Measure TOF by:</strong> First-click attribution, branded search trends,
              blended NCAC (New Customer Acquisition Cost), and Amazon halo effect.
            </p>
          </div>
        </div>
      </div>

      {tof ? (
        <>
          {/* TOF Metrics */}
          <h2 className="text-lg font-semibold text-gray-900 mb-4">TOF Metrics (Last 7 Days)</h2>
          <div className="grid grid-cols-4 gap-4 mb-8">
            <MetricCard
              label="Meta First-Click Revenue"
              value={tof.meta_first_click_7d || 0}
              format="currency"
              help="Revenue attributed to Meta as first touch"
            />
            <MetricCard
              label="Blended NCAC"
              value={tof.ncac_7d_avg || 0}
              format="currency"
              help="Target: <$50"
            />
            <MetricCard
              label="Branded Search %"
              value={tof.branded_search_pct || 0}
              format="percent"
              help="Higher = more brand awareness"
            />
            <MetricCard
              label="Amazon Sales"
              value={tof.amazon_sales_7d || 0}
              format="currency"
              help="Halo effect from brand awareness"
            />
          </div>

          {/* Amazon Halo Effect Section */}
          <div className="bg-orange-50 border border-orange-200 rounded-xl p-6 mb-8">
            <div className="flex items-start gap-3 mb-4">
              <ShoppingCart className="h-6 w-6 text-orange-600 flex-shrink-0 mt-0.5" />
              <div>
                <h2 className="text-lg font-semibold text-orange-900">Amazon Halo Effect</h2>
                <p className="text-orange-700 text-sm mt-1">
                  Customers see your Meta/Google ads, then search for your product on Amazon.
                  Track Amazon sales alongside ad spend to measure indirect attribution.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 mt-4">
              <div className="bg-white rounded-lg p-4 border border-orange-100">
                <p className="text-sm text-gray-500">Amazon Sales (7d)</p>
                <p className="text-2xl font-bold text-orange-700">{formatCurrency(tof.amazon_sales_7d || 0)}</p>
                {tof.amazon_trend !== undefined && (
                  <div className="flex items-center gap-1 mt-1">
                    {tof.amazon_trend > 5 ? (
                      <TrendingUp className="text-green-500" size={16} />
                    ) : tof.amazon_trend < -5 ? (
                      <TrendingDown className="text-red-500" size={16} />
                    ) : (
                      <Minus className="text-gray-400" size={16} />
                    )}
                    <span className={`text-sm ${
                      tof.amazon_trend > 5 ? 'text-green-600' :
                      tof.amazon_trend < -5 ? 'text-red-600' :
                      'text-gray-500'
                    }`}>
                      {tof.amazon_trend >= 0 ? '+' : ''}{(tof.amazon_trend || 0).toFixed(1)}% WoW
                    </span>
                  </div>
                )}
              </div>

              <div className="bg-white rounded-lg p-4 border border-orange-100">
                <p className="text-sm text-gray-500">Meta First-Click (7d)</p>
                <p className="text-2xl font-bold text-blue-700">{formatCurrency(tof.meta_first_click_7d || 0)}</p>
                <p className="text-xs text-gray-400 mt-1">Revenue from Meta as first touch</p>
              </div>

              <div className="bg-white rounded-lg p-4 border border-orange-100">
                <p className="text-sm text-gray-500">Correlation Signal</p>
                <p className="text-lg font-semibold text-gray-900 mt-1">
                  {(tof.amazon_sales_7d || 0) > 0 && (tof.meta_first_click_7d || 0) > 0 ? (
                    tof.amazon_trend > 0 ? (
                      <span className="text-green-600">Positive Halo</span>
                    ) : tof.amazon_trend < -10 ? (
                      <span className="text-red-600">Declining</span>
                    ) : (
                      <span className="text-yellow-600">Stable</span>
                    )
                  ) : (
                    <span className="text-gray-500">Insufficient data</span>
                  )}
                </p>
                <p className="text-xs text-gray-400 mt-1">
                  Meta ads driving Amazon purchases
                </p>
              </div>
            </div>
          </div>

          {/* Halo Effect Correlation Chart */}
          <div className="mb-8">
            <HaloEffectChart days={30} />
          </div>

          {/* TOF Verdict */}
          <div className={`rounded-xl p-6 mb-8 ${
            tof.verdict === 'healthy' ? 'bg-green-50 border border-green-200' :
            tof.verdict === 'working' ? 'bg-blue-50 border border-blue-200' :
            'bg-yellow-50 border border-yellow-200'
          }`}>
            <h2 className={`text-lg font-semibold ${
              tof.verdict === 'healthy' ? 'text-green-900' :
              tof.verdict === 'working' ? 'text-blue-900' :
              'text-yellow-900'
            }`}>
              TOF Status: {(tof.verdict || 'Unknown').toUpperCase()}
            </h2>
            <p className={`mt-2 ${
              tof.verdict === 'healthy' ? 'text-green-800' :
              tof.verdict === 'working' ? 'text-blue-800' :
              'text-yellow-800'
            }`}>
              {tof.message || 'No assessment available'}
            </p>
          </div>

          {/* TOF Campaigns */}
          {tof.campaigns?.length > 0 && (
            <>
              <h2 className="text-lg font-semibold text-gray-900 mb-4">TOF Campaigns</h2>
              <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                <table className="w-full">
                  <thead className="bg-gray-50 border-b border-gray-200">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Campaign</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Channel</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Orders</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Revenue</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">New Customer %</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {tof.campaigns.map((c: any, i: number) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="px-6 py-4 text-sm text-gray-900">{c.name}</td>
                        <td className="px-6 py-4 text-sm text-gray-500">{c.channel}</td>
                        <td className="px-6 py-4 text-sm text-gray-900">{c.orders}</td>
                        <td className="px-6 py-4 text-sm text-gray-900">{formatCurrency(c.revenue || 0)}</td>
                        <td className="px-6 py-4 text-sm text-gray-900">{((c.nc_pct || 0) * 100).toFixed(0)}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="bg-gray-50 px-6 py-3 border-t border-gray-200">
                  <p className="text-gray-500 text-sm">
                    Note: Direct ROAS not shown for TOF campaigns - it's not the right metric
                  </p>
                </div>
              </div>
            </>
          )}
        </>
      ) : (
        <div className="bg-gray-50 rounded-xl p-8 text-center">
          <Target className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h2 className="text-xl font-semibold text-gray-700">No TOF Data Available</h2>
          <p className="text-gray-500 mt-2">
            TOF campaigns are identified by keywords like "prospecting", "awareness", "tof", etc.
          </p>
        </div>
      )}
    </div>
  );
}
