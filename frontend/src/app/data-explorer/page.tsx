'use client';

import { useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { Search, RefreshCw, ChevronDown, ChevronRight } from 'lucide-react';

export default function DataExplorer() {
  const [data, setData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [expanded, setExpanded] = useState<Set<string>>(new Set(['report', 'signals']));

  const fetchData = async () => {
    try {
      setLoading(true);
      const [report, signals, blended, attribution] = await Promise.all([
        api.getReport().catch(() => null),
        api.getSignals().catch(() => null),
        api.getBlended().catch(() => null),
        api.getAttribution().catch(() => null),
      ]);
      setData({ report, signals, blended, attribution });
    } catch (err) {
      console.error('Failed to load data:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const toggleExpand = (key: string) => {
    setExpanded((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(key)) {
        newSet.delete(key);
      } else {
        newSet.add(key);
      }
      return newSet;
    });
  };

  const JsonViewer = ({ data, path = '' }: { data: any; path?: string }) => {
    if (data === null || data === undefined) {
      return <span className="text-gray-400">null</span>;
    }

    if (typeof data !== 'object') {
      if (typeof data === 'string') {
        return <span className="text-green-600">"{data}"</span>;
      }
      if (typeof data === 'number') {
        return <span className="text-blue-600">{data}</span>;
      }
      if (typeof data === 'boolean') {
        return <span className="text-purple-600">{data.toString()}</span>;
      }
      return <span>{String(data)}</span>;
    }

    const isArray = Array.isArray(data);
    const entries = Object.entries(data);
    const isExpanded = expanded.has(path);

    if (entries.length === 0) {
      return <span className="text-gray-400">{isArray ? '[]' : '{}'}</span>;
    }

    return (
      <div className="ml-4">
        <button
          onClick={() => toggleExpand(path)}
          className="flex items-center gap-1 text-gray-500 hover:text-gray-700"
        >
          {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          <span className="text-xs">
            {isArray ? `[${entries.length} items]` : `{${entries.length} keys}`}
          </span>
        </button>
        {isExpanded && (
          <div className="border-l border-gray-200 ml-2 pl-2">
            {entries.map(([key, value]) => (
              <div key={key} className="my-1">
                <span className="text-gray-700 font-medium">{key}:</span>{' '}
                <JsonViewer data={value} path={`${path}.${key}`} />
              </div>
            ))}
          </div>
        )}
      </div>
    );
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Data Explorer</h1>
          <p className="text-gray-500 mt-1">Explore raw marketing data</p>
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
        <div className="space-y-6">
          {Object.entries(data).map(([key, value]) => (
            <div key={key} className="bg-white rounded-xl border border-gray-200 p-6">
              <button
                onClick={() => toggleExpand(key)}
                className="flex items-center gap-2 text-lg font-semibold text-gray-900 hover:text-primary-600"
              >
                {expanded.has(key) ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
                {key}
              </button>
              {expanded.has(key) && (
                <div className="mt-4 font-mono text-sm overflow-x-auto">
                  <JsonViewer data={value} path={key} />
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
