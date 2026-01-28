'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import {
  LayoutDashboard,
  MessageSquare,
  FileText,
  Target,
  Activity,
  Brain,
} from 'lucide-react';

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/acmo', label: 'AI CMO', icon: Brain, highlight: true },
  { href: '/trisignal', label: 'TriSignal', icon: Activity },
  { href: '/ai-chat', label: 'AI Chat', icon: MessageSquare },
  { href: '/activity-log', label: 'Activity Log', icon: FileText },
  { href: '/tof-analysis', label: 'TOF Analysis', icon: Target },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 bg-gray-900 text-white min-h-screen flex flex-col">
      <div className="p-6">
        <h1 className="text-xl font-bold">TuffWraps</h1>
        <p className="text-gray-400 text-sm">Marketing Attribution</p>
      </div>

      <nav className="flex-1 px-3">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;
          const isHighlight = 'highlight' in item && (item as { highlight?: boolean }).highlight;

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                'flex items-center gap-3 px-4 py-3 rounded-lg mb-1 transition-colors',
                isActive
                  ? 'bg-primary-600 text-white'
                  : isHighlight
                  ? 'text-yellow-400 hover:bg-gray-800 hover:text-yellow-300 border border-yellow-500/30'
                  : 'text-gray-300 hover:bg-gray-800 hover:text-white'
              )}
            >
              <Icon size={20} />
              <span>{item.label}</span>
              {isHighlight && !isActive && (
                <span className="ml-auto text-xs bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded">
                  NEW
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      <div className="p-4 border-t border-gray-800">
        <p className="text-gray-400 text-xs">Last Updated</p>
        <p className="text-gray-300 text-sm">Data pulls daily at 8:00 AM EST</p>
      </div>
    </aside>
  );
}
