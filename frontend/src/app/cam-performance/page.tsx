'use client';

import { useEffect, useState } from 'react';
import { MetricCard } from '@/components/MetricCard';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/utils';
import { DollarSign, RefreshCw } from 'lucide-react';

export default function CAMPerformance() {
  const [report, setReport] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      setLoading(true);
      const data = await api.getReport();
      setReport(data);
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

  const r = report?.report || {};
  const summary = r.summary || {};
  const channels = r.channels || {};

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">CMAM Performance</h1>
          <p className="text-gray-500 mt-1">Contribution Margin After Marketing breakdown</p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <RefreshCw size={18} />
          Refresh
        </button>
      </div>

      {/* CAM Formula */}
      <div className="bg-blue-50 border border-blue-200 rounded-xl p-6 mb-8">
        <h2 className="text-lg font-semibold text-blue-900 mb-2">CMAM Formula</h2>
        <p className="text-blue-800 font-mono">
          CMAM = Revenue - COGS - Shipping - Ad Spend
        </p>
        <p className="text-blue-700 text-sm mt-2">
          Target: $20 CMAM per order. This is the PRIMARY metric for marketing health.
        </p>
      </div>

      {/* Overall CAM */}
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Overall CMAM (Last 30 Days)</h2>
      <div className="grid grid-cols-4 gap-4 mb-8">
        <MetricCard
          label="Total CMAM"
          value={summary.blended_cam || 0}
          format="currency"
        />
        <MetricCard
          label="CMAM per Order"
          value={summary.blended_cam_per_order || 0}
          format="currency"
          change={(summary.blended_cam_per_order || 0) - 20}
          changeLabel="vs $20 target"
        />
        <MetricCard
          label="Total Revenue"
          value={summary.total_revenue || 0}
          format="currency"
        />
        <MetricCard
          label="Total Ad Spend"
          value={summary.total_ad_spend || 0}
          format="currency"
        />
      </div>

      {/* Channel CAM */}
      <h2 className="text-lg font-semibold text-gray-900 mb-4">CMAM by Channel</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {Object.entries(channels).map(([name, data]: [string, any]) => (
          <div key={name} className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
            <div className="flex items-center gap-3 mb-4">
              <DollarSign className="h-6 w-6 text-primary-600" />
              <h3 className="text-lg font-semibold">{name}</h3>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-gray-500 text-sm">CMAM</p>
                <p className="text-2xl font-bold">{formatCurrency(data.cam || 0)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">ROAS</p>
                <p className="text-2xl font-bold">{(data.roas || 0).toFixed(2)}x</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">Orders</p>
                <p className="text-xl font-semibold">{(data.orders || 0).toLocaleString()}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">Revenue</p>
                <p className="text-xl font-semibold">{formatCurrency(data.revenue || 0)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">Spend</p>
                <p className="text-xl font-semibold">{formatCurrency(data.spend || 0)}</p>
              </div>
              <div>
                <p className="text-gray-500 text-sm">New Customers</p>
                <p className="text-xl font-semibold">{((data.new_customer_pct || 0) * 100).toFixed(0)}%</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
