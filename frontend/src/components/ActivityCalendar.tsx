'use client';

import { useState } from 'react';
import { ChevronLeft, ChevronRight, TrendingUp, TrendingDown, ArrowRightLeft, Pencil, Trash2, X, Check } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/utils';
import { api, type ChangelogEntry } from '@/lib/api';

interface ActivityCalendarProps {
  entries: ChangelogEntry[];
  onRefresh: () => void;
}

export function ActivityCalendar({ entries, onRefresh }: ActivityCalendarProps) {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({
    description: '',
    amount: '',
    percent_change: '',
    notes: '',
    original_budget: '',
  });
  const [saving, setSaving] = useState(false);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const firstDayOfMonth = new Date(year, month, 1);
  const lastDayOfMonth = new Date(year, month + 1, 0);
  const daysInMonth = lastDayOfMonth.getDate();
  const startingDay = firstDayOfMonth.getDay();

  const entriesByDate: Record<string, ChangelogEntry[]> = {};
  entries.forEach((entry) => {
    const date = new Date(entry.timestamp).toDateString();
    if (!entriesByDate[date]) {
      entriesByDate[date] = [];
    }
    entriesByDate[date].push(entry);
  });

  const prevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
    setSelectedDate(null);
    setEditingId(null);
  };

  const nextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
    setSelectedDate(null);
    setEditingId(null);
  };

  const goToToday = () => {
    setCurrentDate(new Date());
    setSelectedDate(new Date());
  };

  const startEditing = (entry: ChangelogEntry) => {
    setEditingId(entry.id);
    // Use saved original_budget if available, otherwise calculate from amount/percent
    let originalBudget = '';
    if (entry.original_budget) {
      originalBudget = entry.original_budget.toString();
    } else if (entry.amount && entry.percent_change && entry.percent_change !== 0) {
      originalBudget = (entry.amount / (entry.percent_change / 100)).toFixed(0);
    }
    setEditForm({
      description: entry.description,
      amount: entry.amount?.toString() || '',
      percent_change: entry.percent_change?.toString() || '',
      notes: entry.notes || '',
      original_budget: originalBudget,
    });
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditForm({ description: '', amount: '', percent_change: '', notes: '', original_budget: '' });
  };

  const handleAmountChange = (newAmount: string) => {
    setEditForm((prev) => {
      const updated = { ...prev, amount: newAmount };
      // Auto-calculate percent if we have an original budget
      const baseBudget = parseFloat(prev.original_budget);
      if (baseBudget && newAmount) {
        const amountNum = parseFloat(newAmount);
        if (!isNaN(amountNum) && amountNum > 0 && !isNaN(baseBudget)) {
          updated.percent_change = ((amountNum / baseBudget) * 100).toFixed(1);
        }
      }
      return updated;
    });
  };

  const handleOriginalBudgetChange = (newBudget: string) => {
    setEditForm((prev) => {
      const updated = { ...prev, original_budget: newBudget };
      // Recalculate percent if we have an amount
      const amountNum = parseFloat(prev.amount);
      const baseBudget = parseFloat(newBudget);
      if (!isNaN(amountNum) && amountNum > 0 && !isNaN(baseBudget) && baseBudget > 0) {
        updated.percent_change = ((amountNum / baseBudget) * 100).toFixed(1);
      }
      return updated;
    });
  };

  const saveEdit = async () => {
    if (!editingId) return;

    try {
      setSaving(true);
      await api.updateChangelogEntry(editingId, {
        description: editForm.description,
        amount: editForm.amount ? parseFloat(editForm.amount) : undefined,
        percent_change: editForm.percent_change ? parseFloat(editForm.percent_change) : undefined,
        original_budget: editForm.original_budget ? parseFloat(editForm.original_budget) : undefined,
        notes: editForm.notes || undefined,
      });
      setEditingId(null);
      onRefresh();
    } catch (err) {
      console.error('Failed to save:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm('Delete this entry?')) return;
    try {
      await api.deleteChangelogEntry(id);
      onRefresh();
    } catch (err) {
      console.error('Failed to delete:', err);
    }
  };

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  const getActionIcon = (type: string) => {
    switch (type) {
      case 'spend_increase':
        return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'spend_decrease':
        return <TrendingDown className="h-4 w-4 text-red-500" />;
      case 'budget_shift':
        return <ArrowRightLeft className="h-4 w-4 text-purple-500" />;
      default:
        return <div className="h-4 w-4 rounded-full bg-gray-400" />;
    }
  };

  const getActionColor = (type: string) => {
    switch (type) {
      case 'spend_increase':
        return 'bg-green-100 border-green-300 text-green-800';
      case 'spend_decrease':
        return 'bg-red-100 border-red-300 text-red-800';
      case 'budget_shift':
        return 'bg-purple-100 border-purple-300 text-purple-800';
      case 'campaign_paused':
        return 'bg-gray-100 border-gray-300 text-gray-800';
      case 'campaign_launched':
        return 'bg-blue-100 border-blue-300 text-blue-800';
      default:
        return 'bg-gray-100 border-gray-300 text-gray-800';
    }
  };

  const selectedDateEntries = selectedDate
    ? entriesByDate[selectedDate.toDateString()] || []
    : [];

  const calendarDays = [];
  for (let i = 0; i < startingDay; i++) {
    calendarDays.push(null);
  }
  for (let day = 1; day <= daysInMonth; day++) {
    calendarDays.push(day);
  }

  const today = new Date();

  return (
    <div className="grid grid-cols-3 gap-6">
      {/* Calendar */}
      <div className="col-span-2 bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-4">
            <button
              onClick={prevMonth}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ChevronLeft size={20} />
            </button>
            <h2 className="text-xl font-semibold text-gray-900 min-w-[200px] text-center">
              {monthNames[month]} {year}
            </h2>
            <button
              onClick={nextMonth}
              className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
            >
              <ChevronRight size={20} />
            </button>
          </div>
          <button
            onClick={goToToday}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          >
            Today
          </button>
        </div>

        <div className="grid grid-cols-7 gap-1 mb-2">
          {dayNames.map((day) => (
            <div key={day} className="text-center text-sm font-medium text-gray-500 py-2">
              {day}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7 gap-1">
          {calendarDays.map((day, index) => {
            if (!day) {
              return <div key={`empty-${index}`} className="h-24" />;
            }

            const date = new Date(year, month, day);
            const dateString = date.toDateString();
            const dayEntries = entriesByDate[dateString] || [];
            const isToday = date.toDateString() === today.toDateString();
            const isSelected = selectedDate?.toDateString() === dateString;
            const hasEntries = dayEntries.length > 0;

            return (
              <button
                key={day}
                onClick={() => { setSelectedDate(date); setEditingId(null); }}
                className={cn(
                  'h-24 p-2 rounded-lg border text-left transition-all flex flex-col',
                  isSelected
                    ? 'border-primary-500 bg-primary-50 ring-2 ring-primary-200'
                    : hasEntries
                    ? 'border-gray-200 bg-white hover:border-primary-300 hover:bg-gray-50'
                    : 'border-transparent hover:bg-gray-50'
                )}
              >
                <span
                  className={cn(
                    'text-sm font-medium',
                    isToday
                      ? 'bg-primary-600 text-white rounded-full w-7 h-7 flex items-center justify-center'
                      : 'text-gray-900'
                  )}
                >
                  {day}
                </span>
                {hasEntries && (
                  <div className="mt-1 flex-1 overflow-hidden">
                    {dayEntries.slice(0, 2).map((entry) => (
                      <div
                        key={entry.id}
                        className={cn(
                          'text-xs px-1.5 py-0.5 rounded mb-0.5 truncate border',
                          getActionColor(entry.action_type)
                        )}
                      >
                        {entry.action_type === 'spend_increase' ? '+' : entry.action_type === 'spend_decrease' ? '-' : ''}
                        {entry.amount ? `$${Math.round(entry.amount)}` : entry.description.slice(0, 15)}
                      </div>
                    ))}
                    {dayEntries.length > 2 && (
                      <div className="text-xs text-gray-500 px-1">
                        +{dayEntries.length - 2} more
                      </div>
                    )}
                  </div>
                )}
              </button>
            );
          })}
        </div>

        <div className="mt-6 pt-4 border-t border-gray-200 flex gap-6">
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-green-400" />
            <span className="text-sm text-gray-600">Budget Increase</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-red-400" />
            <span className="text-sm text-gray-600">Budget Decrease</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-purple-400" />
            <span className="text-sm text-gray-600">Budget Shift</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded bg-blue-400" />
            <span className="text-sm text-gray-600">Campaign Launch</span>
          </div>
        </div>
      </div>

      {/* Selected Day Details */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          {selectedDate
            ? selectedDate.toLocaleDateString('en-US', {
                weekday: 'long',
                month: 'long',
                day: 'numeric',
                year: 'numeric',
              })
            : 'Select a day'}
        </h3>

        {!selectedDate ? (
          <p className="text-gray-500 text-sm">
            Click on a day to see activity details
          </p>
        ) : selectedDateEntries.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-500">No activity on this day</p>
          </div>
        ) : (
          <div className="space-y-4">
            {selectedDateEntries.map((entry) => (
              <div
                key={entry.id}
                className={cn(
                  'p-4 rounded-lg border',
                  getActionColor(entry.action_type)
                )}
              >
                {editingId === entry.id ? (
                  /* Edit Form */
                  <div className="space-y-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
                      <input
                        type="text"
                        value={editForm.description}
                        onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                        className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                      />
                    </div>
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Orig. Budget</label>
                        <input
                          type="number"
                          value={editForm.original_budget}
                          onChange={(e) => handleOriginalBudgetChange(e.target.value)}
                          placeholder="e.g. 300"
                          className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">Amount ($)</label>
                        <input
                          type="number"
                          value={editForm.amount}
                          onChange={(e) => handleAmountChange(e.target.value)}
                          className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-medium text-gray-700 mb-1">% Change</label>
                        <input
                          type="number"
                          value={editForm.percent_change}
                          onChange={(e) => setEditForm({ ...editForm, percent_change: e.target.value })}
                          className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500 bg-gray-50"
                          title="Auto-calculates from Original Budget and Amount"
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Notes</label>
                      <textarea
                        value={editForm.notes}
                        onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })}
                        rows={2}
                        className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500"
                      />
                    </div>
                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        onClick={cancelEditing}
                        className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900"
                      >
                        <X size={16} />
                      </button>
                      <button
                        onClick={saveEdit}
                        disabled={saving}
                        className="px-3 py-1.5 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50"
                      >
                        <Check size={16} />
                      </button>
                    </div>
                  </div>
                ) : (
                  /* Display Mode */
                  <div className="flex items-start gap-3">
                    {getActionIcon(entry.action_type)}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <p className="font-medium text-gray-900">{entry.description}</p>
                        <div className="flex gap-1">
                          <button
                            onClick={() => startEditing(entry)}
                            className="p-1 text-gray-400 hover:text-gray-600 rounded"
                            title="Edit"
                          >
                            <Pencil size={14} />
                          </button>
                          <button
                            onClick={() => handleDelete(entry.id)}
                            className="p-1 text-gray-400 hover:text-red-600 rounded"
                            title="Delete"
                          >
                            <Trash2 size={14} />
                          </button>
                        </div>
                      </div>
                      {entry.campaign && (
                        <p className="text-sm text-gray-600 mt-1 truncate">{entry.campaign}</p>
                      )}
                      {entry.channel && (
                        <span className="inline-block mt-2 text-xs px-2 py-1 bg-white/50 rounded">
                          {entry.channel}
                        </span>
                      )}
                      {(entry.amount || entry.percent_change) && (
                        <div className="mt-2 text-sm font-medium">
                          {entry.amount && <span>{formatCurrency(entry.amount)}</span>}
                          {entry.amount && entry.percent_change && <span> / </span>}
                          {entry.percent_change && <span>{entry.percent_change}%</span>}
                        </div>
                      )}
                      {entry.notes && (
                        <p className="text-sm text-gray-500 mt-2 border-t border-gray-200/50 pt-2">
                          {entry.notes}
                        </p>
                      )}
                      {entry.metrics_snapshot && (
                        <div className="mt-3 pt-3 border-t border-gray-200/50 grid grid-cols-2 gap-2 text-xs">
                          <div>
                            <span className="text-gray-500">CMAM/Order:</span>{' '}
                            <span className="font-medium">{formatCurrency(entry.metrics_snapshot.cam_per_order)}</span>
                          </div>
                          <div>
                            <span className="text-gray-500">Orders:</span>{' '}
                            <span className="font-medium">{entry.metrics_snapshot.total_orders}</span>
                          </div>
                        </div>
                      )}
                      <p className="text-xs text-gray-400 mt-2">
                        {new Date(entry.timestamp).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
