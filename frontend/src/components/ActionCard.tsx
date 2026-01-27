'use client';

import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, ArrowRightLeft, Search, CheckCircle, ExternalLink } from 'lucide-react';
import type { ActionItem } from '@/lib/api';

function extractCampaignId(actionText: string): string | null {
  const match = actionText.match(/\(ID:\s*(\d+)\)/);
  return match ? match[1] : null;
}

function getCampaignUrl(channel: string, campaignId: string): string {
  if (channel === 'Meta Ads') {
    return `https://adsmanager.facebook.com/adsmanager/manage/campaigns?act=&selected_campaign_ids=${campaignId}`;
  } else if (channel === 'Google Ads') {
    return `https://ads.google.com/aw/campaigns/settings?campaignId=${campaignId}`;
  }
  return '';
}

const iconMap: Record<string, React.ComponentType<{ className?: string }>> = {
  TrendingUp,
  TrendingDown,
  ArrowRightLeft,
  Search,
  CheckCircle,
};

interface ActionCardProps {
  action: ActionItem;
  checked: boolean;
  onToggle: () => void;
}

export function ActionCard({ action, checked, onToggle }: ActionCardProps) {
  const Icon = iconMap[action.icon] || TrendingUp;
  const campaignId = extractCampaignId(action.action);
  const campaignUrl = campaignId ? getCampaignUrl(action.channel, campaignId) : null;

  const priorityColors = {
    HIGH: {
      border: 'border-l-green-500',
      bg: 'bg-green-50',
      badge: 'bg-green-500',
    },
    MEDIUM: {
      border: 'border-l-yellow-500',
      bg: 'bg-yellow-50',
      badge: 'bg-yellow-500',
    },
    LOW: {
      border: 'border-l-blue-500',
      bg: 'bg-blue-50',
      badge: 'bg-blue-500',
    },
  };

  const colors = priorityColors[action.priority] || priorityColors.MEDIUM;

  return (
    <div
      className={cn(
        'border-l-4 rounded-lg p-4 mb-3 transition-all',
        colors.border,
        colors.bg,
        checked && 'opacity-60'
      )}
    >
      <div className="flex items-start gap-4">
        <input
          type="checkbox"
          checked={checked}
          onChange={onToggle}
          className="mt-1 h-5 w-5 rounded border-gray-300 text-primary-600 focus:ring-primary-500 cursor-pointer"
        />

        <div className="flex-1">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Icon className="h-5 w-5 text-gray-600" />
              <span className={cn('font-semibold text-gray-900', checked && 'line-through')}>
                {action.action}
              </span>
              <span className="text-xs px-2 py-1 rounded bg-gray-200 text-gray-600">
                {action.channel}
              </span>
              {campaignUrl && (
                <a
                  href={campaignUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded bg-primary-100 text-primary-700 hover:bg-primary-200 transition-colors"
                  title="Open campaign in ads manager"
                  onClick={(e) => e.stopPropagation()}
                >
                  <ExternalLink className="h-3 w-3" />
                  Open
                </a>
              )}
            </div>

            <span
              className={cn(
                'px-3 py-1 rounded text-white text-sm font-medium',
                colors.badge
              )}
            >
              {action.budget_change}
            </span>
          </div>

          <p className="text-gray-600 text-sm mt-2">{action.reason}</p>

          {action.new_budget && (
            <p className="text-gray-500 text-xs mt-1">
              {action.new_budget}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
