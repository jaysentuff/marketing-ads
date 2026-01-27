'use client';

import { useEffect, useState } from 'react';
import { MetricCard } from '@/components/MetricCard';
import { api } from '@/lib/api';
import { formatCurrency, getHealthStatus } from '@/lib/utils';
import { TrendingUp, TrendingDown, Pause, AlertTriangle, RefreshCw } from 'lucide-react';

export default function CommandCenter() {
  const [report, setReport] = useState<any>(null);
  const [signals, setSignals] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [reportData, signalsData] = await Promise.all([
        api.getReport(),
        api.getSignals(),
      ]);
      setReport(reportData);
      setSignals(signalsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data');
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

  if (error || !report) {
    return (
      <div className="bg-red-50 border border-red-200 rounded-xl p-8 text-center">
        <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-semibold text-red-800">No data available</h2>
        <p className="text-red-600 mt-2">{error || 'Run the daily data pull first'}</p>
      </div>
    );
  }

  const r = report.report || {};
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

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Command Center</h1>
          <p className="text-gray-500 mt-1">Daily decision dashboard</p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <RefreshCw size={18} />
          Refresh
        </button>
      </div>

      {/* Health Status */}
      <div className={`${health.bgColor} border-l-4 border-l-current ${health.color} rounded-lg p-6 mb-6`}>
        <h2 className={`text-2xl font-bold ${health.color}`}>
          Overall Status: {health.status}
        </h2>
        <p className="text-gray-700 mt-2">
          CMAM per Order: <strong>{formatCurrency(camPerOrder)}</strong> (Target: $20)
        </p>
      </div>

      {/* Action Card */}
      <div className={`${spend.color} border-2 rounded-lg p-6 mb-8 text-center`}>
        <SpendIcon className={`h-12 w-12 mx-auto ${spend.text}`} />
        <h3 className={`text-xl font-bold mt-2 ${spend.text}`}>TODAY'S ACTION: {spend.label}</h3>
        <p className="text-gray-700 mt-1">{spend.detail}</p>
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

      <p className="text-gray-400 text-sm">Report generated: {report.generated_at}</p>
    </div>
  );
}
