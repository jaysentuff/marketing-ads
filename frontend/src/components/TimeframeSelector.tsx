'use client';

import { Calendar } from 'lucide-react';

const TIMEFRAMES = [
  { days: 1, label: 'Yesterday' },
  { days: 2, label: '2 Days' },
  { days: 3, label: '3 Days' },
  { days: 7, label: '7 Days' },
  { days: 14, label: '14 Days' },
  { days: 30, label: '30 Days' },
];

interface TimeframeSelectorProps {
  value: number;
  onChange: (days: number) => void;
  className?: string;
}

export default function TimeframeSelector({ value, onChange, className = '' }: TimeframeSelectorProps) {
  return (
    <div className={`flex items-center gap-2 ${className}`}>
      <Calendar size={18} className="text-gray-500" />
      <div className="flex bg-gray-100 rounded-lg p-1">
        {TIMEFRAMES.map((tf) => (
          <button
            key={tf.days}
            onClick={() => onChange(tf.days)}
            className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
              value === tf.days
                ? 'bg-white text-primary-600 shadow-sm'
                : 'text-gray-600 hover:text-gray-900'
            }`}
          >
            {tf.label}
          </button>
        ))}
      </div>
    </div>
  );
}
