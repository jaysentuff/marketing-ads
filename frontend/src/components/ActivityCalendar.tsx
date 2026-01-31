'use client';

import { useState } from 'react';
import { ChevronLeft, ChevronRight, TrendingUp, TrendingDown, ArrowRightLeft, Pencil, Trash2, X, Check, GripVertical } from 'lucide-react';
import { cn } from '@/lib/utils';
import { formatCurrency } from '@/lib/utils';
import { api, type ChangelogEntry } from '@/lib/api';
import {
  DndContext,
  DragOverlay,
  useDraggable,
  useDroppable,
  DragStartEvent,
  DragEndEvent,
  DragOverEvent,
  PointerSensor,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
} from '@dnd-kit/core';

interface ActivityCalendarProps {
  entries: ChangelogEntry[];
  onRefresh: () => void;
}

// Draggable Entry Component
function DraggableEntry({ entry, onClick, getActionColor, getPlatformIcon }: {
  entry: ChangelogEntry;
  onClick: () => void;
  getActionColor: (type: string) => string;
  getPlatformIcon: (channel: string | undefined) => React.ReactNode;
}) {
  const { attributes, listeners, setNodeRef, isDragging, transform } = useDraggable({
    id: `entry-${entry.id}`,
    data: { entry },
  });

  const style = transform ? {
    transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
  } : undefined;

  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation(); // Prevent DroppableDay from also handling the click
    // Only trigger click if not dragging
    if (!isDragging) {
      onClick();
    }
  };

  return (
    <div
      ref={setNodeRef}
      {...listeners}
      {...attributes}
      onClick={handleClick}
      style={style}
      className={cn(
        'text-xs px-1.5 py-0.5 rounded mb-0.5 truncate border flex items-center gap-1',
        'cursor-grab active:cursor-grabbing touch-none select-none',
        getActionColor(entry.action_type),
        isDragging && 'opacity-50 z-50'
      )}
    >
      <GripVertical size={12} className="flex-shrink-0 text-gray-400" />
      {getPlatformIcon(entry.channel)}
      <span className="truncate">
        {entry.action_type === 'spend_increase' ? '+' : entry.action_type === 'spend_decrease' ? '-' : ''}
        {entry.amount ? `$${Math.round(entry.amount)}` : entry.description.slice(0, 12)}
      </span>
    </div>
  );
}

// Droppable Day Cell Component
function DroppableDay({ day, date, isToday, hasEntries, children, isOver, onDayClick }: {
  day: number;
  date: Date;
  isToday: boolean;
  hasEntries: boolean;
  children: React.ReactNode;
  isOver: boolean;
  onDayClick: () => void;
}) {
  const { setNodeRef, isOver: isDropOver } = useDroppable({
    id: `day-${date.toISOString()}`,
    data: { date },
  });

  const handleClick = (e: React.MouseEvent) => {
    // Only open modal if clicking directly on the day cell, not on entries
    if (e.target === e.currentTarget || (e.target as HTMLElement).closest('[data-day-number]')) {
      onDayClick();
    }
  };

  return (
    <div
      ref={setNodeRef}
      onClick={handleClick}
      className={cn(
        'h-28 p-2 rounded-lg border text-left transition-all flex flex-col cursor-pointer',
        isOver || isDropOver
          ? 'border-primary-500 bg-primary-100 ring-2 ring-primary-300'
          : hasEntries
          ? 'border-gray-200 bg-white hover:border-primary-300'
          : 'border-transparent hover:bg-gray-50'
      )}
    >
      <span
        data-day-number
        className={cn(
          'text-sm font-medium',
          isToday
            ? 'bg-primary-600 text-white rounded-full w-7 h-7 flex items-center justify-center'
            : 'text-gray-900'
        )}
      >
        {day}
      </span>
      {children}
    </div>
  );
}

export function ActivityCalendar({ entries, onRefresh }: ActivityCalendarProps) {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<Date | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({
    description: '',
    amount: '',
    percent_change: '',
    notes: '',
    original_budget: '',
    date: '',
  });
  const [saving, setSaving] = useState(false);
  const [activeEntry, setActiveEntry] = useState<ChangelogEntry | null>(null);
  const [overId, setOverId] = useState<string | null>(null);

  // Configure sensors with activation constraints
  const mouseSensor = useSensor(MouseSensor, {
    activationConstraint: {
      distance: 5, // 5px movement required before drag starts
    },
  });
  const touchSensor = useSensor(TouchSensor, {
    activationConstraint: {
      delay: 200, // 200ms delay for touch to differentiate from scroll
      tolerance: 5,
    },
  });
  const pointerSensor = useSensor(PointerSensor, {
    activationConstraint: {
      distance: 5,
    },
  });
  const sensors = useSensors(mouseSensor, touchSensor, pointerSensor);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  const daysInMonth = new Date(year, month + 1, 0).getDate();
  const startingDay = new Date(year, month, 1).getDay();

  const entriesByDate: Record<string, ChangelogEntry[]> = {};
  entries.forEach((entry) => {
    const date = new Date(entry.timestamp).toDateString();
    if (!entriesByDate[date]) {
      entriesByDate[date] = [];
    }
    entriesByDate[date].push(entry);
  });

  const prevMonth = () => setCurrentDate(new Date(year, month - 1, 1));
  const nextMonth = () => setCurrentDate(new Date(year, month + 1, 1));
  const goToToday = () => setCurrentDate(new Date());

  const openModal = (date: Date) => {
    setSelectedDate(date);
    setShowModal(true);
    setEditingId(null);
  };

  const closeModal = () => {
    setShowModal(false);
    setSelectedDate(null);
    setEditingId(null);
  };

  const startEditing = (entry: ChangelogEntry) => {
    setEditingId(entry.id);
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
      date: entry.timestamp.split('T')[0],
    });
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditForm({ description: '', amount: '', percent_change: '', notes: '', original_budget: '', date: '' });
  };

  const handleAmountChange = (newAmount: string) => {
    setEditForm((prev) => {
      const updated = { ...prev, amount: newAmount };
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
        timestamp: editForm.date ? `${editForm.date}T12:00:00.000000` : undefined,
      });
      setEditingId(null);
      closeModal();
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

  // Drag handlers
  const handleDragStart = (event: DragStartEvent) => {
    const { active } = event;
    const entry = active.data.current?.entry as ChangelogEntry;
    setActiveEntry(entry);
  };

  const handleDragOver = (event: DragOverEvent) => {
    setOverId(event.over?.id?.toString() || null);
  };

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveEntry(null);
    setOverId(null);

    if (!over) return;

    const entry = active.data.current?.entry as ChangelogEntry;
    const newDate = over.data.current?.date as Date;

    if (!entry || !newDate) return;

    // Check if dropped on same date
    const oldDate = new Date(entry.timestamp).toDateString();
    const targetDate = newDate.toDateString();
    if (oldDate === targetDate) return;

    // Update the entry's timestamp
    const year = newDate.getFullYear();
    const month = String(newDate.getMonth() + 1).padStart(2, '0');
    const day = String(newDate.getDate()).padStart(2, '0');
    const timestamp = `${year}-${month}-${day}T12:00:00.000000`;

    try {
      await api.updateChangelogEntry(entry.id, { timestamp });
      onRefresh();
    } catch (err) {
      console.error('Failed to move entry:', err);
    }
  };

  const monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  const dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  const getActionIcon = (type: string) => {
    switch (type) {
      case 'spend_increase': return <TrendingUp className="h-4 w-4 text-green-500" />;
      case 'spend_decrease': return <TrendingDown className="h-4 w-4 text-red-500" />;
      case 'budget_shift': return <ArrowRightLeft className="h-4 w-4 text-purple-500" />;
      default: return <div className="h-4 w-4 rounded-full bg-gray-400" />;
    }
  };

  const getPlatformIcon = (channel: string | undefined) => {
    if (!channel) return null;
    const lowerChannel = channel.toLowerCase();

    if (lowerChannel.includes('meta') || lowerChannel.includes('facebook')) {
      return (
        <svg className="h-3 w-3 flex-shrink-0" viewBox="0 0 24 24" fill="#1877F2">
          <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
        </svg>
      );
    }
    if (lowerChannel.includes('google')) {
      return (
        <svg className="h-3 w-3 flex-shrink-0" viewBox="0 0 24 24">
          <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
          <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
          <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
          <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
        </svg>
      );
    }
    if (lowerChannel.includes('tiktok')) {
      return (
        <svg className="h-3 w-3 flex-shrink-0" viewBox="0 0 24 24" fill="#000000">
          <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-5.2 1.74 2.89 2.89 0 012.31-4.64 2.93 2.93 0 01.88.13V9.4a6.84 6.84 0 00-1-.05A6.33 6.33 0 005 20.1a6.34 6.34 0 0010.86-4.43v-7a8.16 8.16 0 004.77 1.52v-3.4a4.85 4.85 0 01-1-.1z"/>
        </svg>
      );
    }
    return null;
  };

  const getActionColor = (type: string) => {
    switch (type) {
      case 'spend_increase': return 'bg-green-100 border-green-300 text-green-800';
      case 'spend_decrease': return 'bg-red-100 border-red-300 text-red-800';
      case 'budget_shift': return 'bg-purple-100 border-purple-300 text-purple-800';
      case 'campaign_paused': return 'bg-gray-100 border-gray-300 text-gray-800';
      case 'campaign_launched': return 'bg-blue-100 border-blue-300 text-blue-800';
      default: return 'bg-gray-100 border-gray-300 text-gray-800';
    }
  };

  const selectedDateEntries = selectedDate
    ? entriesByDate[selectedDate.toDateString()] || []
    : [];

  const calendarDays: (number | null)[] = [];
  for (let i = 0; i < startingDay; i++) calendarDays.push(null);
  for (let day = 1; day <= daysInMonth; day++) calendarDays.push(day);

  const today = new Date();

  return (
    <>
      <DndContext
        sensors={sensors}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
      >
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              <button onClick={prevMonth} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
                <ChevronLeft size={20} />
              </button>
              <h2 className="text-xl font-semibold text-gray-900 min-w-[200px] text-center">
                {monthNames[month]} {year}
              </h2>
              <button onClick={nextMonth} className="p-2 hover:bg-gray-100 rounded-lg transition-colors">
                <ChevronRight size={20} />
              </button>
            </div>
            <button onClick={goToToday} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors">
              Today
            </button>
          </div>

          <div className="grid grid-cols-7 gap-1 mb-2">
            {dayNames.map((day) => (
              <div key={day} className="text-center text-sm font-medium text-gray-500 py-2">{day}</div>
            ))}
          </div>

          <div className="grid grid-cols-7 gap-1">
            {calendarDays.map((day, index) => {
              if (!day) return <div key={`empty-${index}`} className="h-28" />;

              const date = new Date(year, month, day);
              const dateString = date.toDateString();
              const dayEntries = entriesByDate[dateString] || [];
              const isToday = date.toDateString() === today.toDateString();
              const hasEntries = dayEntries.length > 0;
              const isOver = overId === `day-${date.toISOString()}`;

              return (
                <DroppableDay
                  key={day}
                  day={day}
                  date={date}
                  isToday={isToday}
                  hasEntries={hasEntries}
                  isOver={isOver}
                  onDayClick={() => openModal(date)}
                >
                  {hasEntries && (
                    <div className="mt-1 flex-1 overflow-hidden">
                      {dayEntries.slice(0, 3).map((entry) => (
                        <DraggableEntry
                          key={entry.id}
                          entry={entry}
                          onClick={() => openModal(date)}
                          getActionColor={getActionColor}
                          getPlatformIcon={getPlatformIcon}
                        />
                      ))}
                      {dayEntries.length > 3 && (
                        <div className="text-xs text-gray-500 px-1">+{dayEntries.length - 3} more</div>
                      )}
                    </div>
                  )}
                </DroppableDay>
              );
            })}
          </div>

          <div className="mt-6 pt-4 border-t border-gray-200 flex flex-wrap gap-6">
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

        {/* Drag Overlay - shows what's being dragged */}
        <DragOverlay>
          {activeEntry && (
            <div className={cn(
              'text-xs px-2 py-1 rounded border shadow-lg',
              getActionColor(activeEntry.action_type)
            )}>
              {getPlatformIcon(activeEntry.channel)}
              <span className="ml-1">
                {activeEntry.amount ? `$${Math.round(activeEntry.amount)}` : activeEntry.description.slice(0, 20)}
              </span>
            </div>
          )}
        </DragOverlay>
      </DndContext>

      {/* Modal Popup */}
      {showModal && selectedDate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={closeModal}>
          <div className="bg-white rounded-xl border border-gray-200 p-6 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">
                {selectedDate.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
              </h3>
              <button onClick={closeModal} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
            </div>

            {selectedDateEntries.length === 0 ? (
              <div className="text-center py-8"><p className="text-gray-500">No activity on this day</p></div>
            ) : (
              <div className="space-y-4">
                {selectedDateEntries.map((entry) => (
                  <div key={entry.id} className={cn('p-4 rounded-lg border', getActionColor(entry.action_type))}>
                    {editingId === entry.id ? (
                      <div className="space-y-3">
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
                          <input type="text" value={editForm.description} onChange={(e) => setEditForm({ ...editForm, description: e.target.value })} className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500" />
                        </div>
                        <div className="grid grid-cols-3 gap-2">
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">Orig. Budget</label>
                            <input type="number" value={editForm.original_budget} onChange={(e) => handleOriginalBudgetChange(e.target.value)} placeholder="e.g. 300" className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500" />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">Amount ($)</label>
                            <input type="number" value={editForm.amount} onChange={(e) => handleAmountChange(e.target.value)} className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500" />
                          </div>
                          <div>
                            <label className="block text-xs font-medium text-gray-700 mb-1">% Change</label>
                            <input type="number" value={editForm.percent_change} onChange={(e) => setEditForm({ ...editForm, percent_change: e.target.value })} className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500 bg-gray-50" />
                          </div>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">Date</label>
                          <input type="date" value={editForm.date} onChange={(e) => setEditForm({ ...editForm, date: e.target.value })} className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-gray-700 mb-1">Notes</label>
                          <textarea value={editForm.notes} onChange={(e) => setEditForm({ ...editForm, notes: e.target.value })} rows={2} className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:outline-none focus:ring-1 focus:ring-primary-500" />
                        </div>
                        <div className="flex justify-end gap-2 pt-2">
                          <button onClick={cancelEditing} className="px-3 py-1.5 text-sm text-gray-600 hover:text-gray-900">Cancel</button>
                          <button onClick={saveEdit} disabled={saving} className="px-4 py-1.5 text-sm bg-primary-600 text-white rounded hover:bg-primary-700 disabled:opacity-50">{saving ? 'Saving...' : 'Save'}</button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex items-start gap-3">
                        {getActionIcon(entry.action_type)}
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between gap-2">
                            <p className="font-medium text-gray-900">{entry.description}</p>
                            <div className="flex gap-1">
                              <button onClick={() => startEditing(entry)} className="p-1 text-gray-400 hover:text-gray-600 rounded" title="Edit"><Pencil size={14} /></button>
                              <button onClick={() => handleDelete(entry.id)} className="p-1 text-gray-400 hover:text-red-600 rounded" title="Delete"><Trash2 size={14} /></button>
                            </div>
                          </div>
                          {entry.campaign && <p className="text-sm text-gray-600 mt-1 truncate">{entry.campaign}</p>}
                          {entry.channel && (
                            <span className="inline-flex items-center gap-1.5 mt-2 text-xs px-2 py-1 bg-white/50 rounded">
                              {getPlatformIcon(entry.channel)}
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
                          {entry.notes && <p className="text-sm text-gray-500 mt-2 border-t border-gray-200/50 pt-2">{entry.notes}</p>}
                          {entry.metrics_snapshot && Object.keys(entry.metrics_snapshot).length > 0 && (
                            <div className="mt-3 pt-3 border-t border-gray-200/50 grid grid-cols-2 gap-2 text-xs">
                              <div><span className="text-gray-500">CMAM/Order:</span> <span className="font-medium">{formatCurrency(entry.metrics_snapshot.cam_per_order)}</span></div>
                              <div><span className="text-gray-500">Orders:</span> <span className="font-medium">{entry.metrics_snapshot.total_orders}</span></div>
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
