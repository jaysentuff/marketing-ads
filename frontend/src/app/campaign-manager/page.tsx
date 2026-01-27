'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { formatCurrency } from '@/lib/utils';
import { ListChecks, RefreshCw } from 'lucide-react';

export default function CampaignManager() {
  const [googleCampaigns, setGoogleCampaigns] = useState<any[]>([]);
  const [metaCampaigns, setMetaCampaigns] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      setLoading(true);
      const [google, meta] = await Promise.all([
        api.getChannel('google'),
        api.getChannel('meta'),
      ]);
      setGoogleCampaigns(google.campaigns || []);
      setMetaCampaigns(meta.campaigns || []);
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const CampaignTable = ({ campaigns, title }: { campaigns: any[]; title: string }) => (
    <div className="mb-8">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">{title}</h2>
      {campaigns.length === 0 ? (
        <p className="text-gray-500">No campaign data available</p>
      ) : (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Campaign</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Orders</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">Revenue</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">ROAS</th>
                <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase">New Customer %</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {campaigns.map((c, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-sm text-gray-900 max-w-xs truncate">{c.name}</td>
                  <td className="px-6 py-4 text-sm text-gray-900 text-right">{c.orders}</td>
                  <td className="px-6 py-4 text-sm text-gray-900 text-right">{formatCurrency(c.revenue || 0)}</td>
                  <td className="px-6 py-4 text-sm text-right">
                    <span className={`font-medium ${
                      c.roas >= 3 ? 'text-green-600' :
                      c.roas >= 2 ? 'text-yellow-600' :
                      'text-red-600'
                    }`}>
                      {(c.roas || 0).toFixed(2)}x
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900 text-right">
                    {((c.nc_pct || 0) * 100).toFixed(0)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Campaign Manager</h1>
          <p className="text-gray-500 mt-1">View and manage campaigns across channels</p>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <RefreshCw size={18} />
          Refresh
        </button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
        </div>
      ) : (
        <>
          <CampaignTable campaigns={googleCampaigns} title="Google Ads Campaigns" />
          <CampaignTable campaigns={metaCampaigns} title="Meta Ads Campaigns" />
        </>
      )}
    </div>
  );
}
