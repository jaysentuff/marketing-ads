'use client';

import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/utils';
import { ArrowUp, ArrowDown, Minus } from 'lucide-react';

interface MetricCardProps {
  label: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  format?: 'currency' | 'number' | 'percent' | 'none';
  help?: string;
}

export function MetricCard({
  label,
  value,
  change,
  changeLabel,
  format = 'none',
  help,
}: MetricCardProps) {
  const formattedValue =
    format === 'currency' && typeof value === 'number'
      ? formatCurrency(value)
      : format === 'number' && typeof value === 'number'
        ? value.toLocaleString()
        : format === 'percent' && typeof value === 'number'
          ? `${value.toFixed(1)}%`
          : value;

  const changeDirection = change ? (change > 0 ? 'up' : change < 0 ? 'down' : 'flat') : null;

  return (
    <div className="bg-white rounded-xl p-6 shadow-sm border border-gray-100">
      <p className="text-gray-500 text-sm font-medium">{label}</p>
      <p className="text-3xl font-bold text-gray-900 mt-1">{formattedValue}</p>

      {(change !== undefined || changeLabel) && (
        <div className="flex items-center gap-1 mt-2">
          {changeDirection === 'up' && (
            <ArrowUp className="h-4 w-4 text-green-500" />
          )}
          {changeDirection === 'down' && (
            <ArrowDown className="h-4 w-4 text-red-500" />
          )}
          {changeDirection === 'flat' && (
            <Minus className="h-4 w-4 text-gray-400" />
          )}
          <span
            className={cn(
              'text-sm',
              changeDirection === 'up' && 'text-green-600',
              changeDirection === 'down' && 'text-red-600',
              changeDirection === 'flat' && 'text-gray-500',
              !changeDirection && 'text-gray-500'
            )}
          >
            {change !== undefined && `${change > 0 ? '+' : ''}${change.toFixed(2)}`}
            {changeLabel && ` ${changeLabel}`}
          </span>
        </div>
      )}

      {help && (
        <p className="text-gray-400 text-xs mt-2">{help}</p>
      )}
    </div>
  );
}
