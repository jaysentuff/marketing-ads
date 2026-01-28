'use client';

import Link from 'next/link';
import { ArrowLeft, Activity, Target, TrendingUp, TrendingDown, DollarSign, Users, CheckCircle, XCircle, HelpCircle } from 'lucide-react';

export default function TriSignalHelp() {
  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <Link
          href="/trisignal"
          className="inline-flex items-center gap-2 text-gray-600 hover:text-gray-900 mb-4"
        >
          <ArrowLeft size={18} />
          Back to TriSignal
        </Link>
        <h1 className="text-3xl font-bold text-gray-900">Understanding TriSignal</h1>
        <p className="text-gray-500 mt-2">
          How to read the data and make decisions
        </p>
      </div>

      {/* What is TriSignal */}
      <section className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-primary-100 rounded-lg">
            <Activity className="text-primary-600" size={24} />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">What is TriSignal?</h2>
        </div>
        <p className="text-gray-700 mb-4">
          TriSignal measures what <strong>actually happened</strong> to your business when ad spend changed.
          Unlike platform attribution (which can double-count or miss sales), TriSignal looks at real outcomes:
        </p>
        <ul className="list-disc list-inside text-gray-700 space-y-2 ml-4">
          <li>Did Shopify revenue go up or down?</li>
          <li>Did you get more or fewer new customers?</li>
          <li>Did Amazon sales follow the same pattern?</li>
          <li>Did branded search interest change?</li>
        </ul>
        <p className="text-gray-700 mt-4">
          By comparing these signals to your spend changes, you can see if your marketing is actually working.
        </p>
      </section>

      {/* Signal Agreement */}
      <section className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-blue-100 rounded-lg">
            <Target className="text-blue-600" size={24} />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">Signal Agreement Analysis</h2>
        </div>
        <p className="text-gray-700 mb-4">
          This section answers: <strong>"When I change my ad spend, do business results follow?"</strong>
        </p>

        <div className="space-y-4">
          <div className="flex items-start gap-3 p-4 bg-green-50 rounded-lg">
            <CheckCircle className="text-green-500 flex-shrink-0 mt-1" size={20} />
            <div>
              <p className="font-medium text-green-800">Agrees (Correlated)</p>
              <p className="text-green-700 text-sm">
                The metric moved in the same direction as your spend. If you spent more and revenue went up,
                that's agreement. If you spent less and revenue went down, that's also agreement.
                <strong> This proves the connection between your ads and results.</strong>
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 p-4 bg-red-50 rounded-lg">
            <XCircle className="text-red-500 flex-shrink-0 mt-1" size={20} />
            <div>
              <p className="font-medium text-red-800">Conflicts (Uncorrelated)</p>
              <p className="text-red-700 text-sm">
                The metric moved opposite to your spend. If you spent more but revenue went down,
                that's a conflict. This suggests your marketing may not be the main driver, or
                there's a problem with your campaigns.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-3 p-4 bg-gray-50 rounded-lg">
            <HelpCircle className="text-gray-500 flex-shrink-0 mt-1" size={20} />
            <div>
              <p className="font-medium text-gray-800">Neutral</p>
              <p className="text-gray-700 text-sm">
                The change was too small to be meaningful (less than 5% change).
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Efficiency Metrics */}
      <section className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-purple-100 rounded-lg">
            <DollarSign className="text-purple-600" size={24} />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">Efficiency Metrics</h2>
        </div>

        <div className="space-y-6">
          <div>
            <h3 className="font-semibold text-gray-900 mb-2">MER (Marketing Efficiency Ratio)</h3>
            <p className="text-gray-700 mb-2">
              <code className="bg-gray-100 px-2 py-1 rounded">MER = Total Revenue ÷ Total Ad Spend</code>
            </p>
            <p className="text-gray-600 text-sm">
              Higher is better. A 3.0x MER means you get $3 in revenue for every $1 spent on ads.
              This is an "ungameable" metric because it uses actual Shopify revenue, not platform-reported conversions.
            </p>
            <div className="mt-2 text-sm">
              <span className="text-green-600 font-medium">3.0x+ = Good</span>
              <span className="mx-2 text-gray-400">|</span>
              <span className="text-yellow-600 font-medium">2.0-3.0x = Okay</span>
              <span className="mx-2 text-gray-400">|</span>
              <span className="text-red-600 font-medium">&lt;2.0x = Concerning</span>
            </div>
          </div>

          <div>
            <h3 className="font-semibold text-gray-900 mb-2">True NCAC (New Customer Acquisition Cost)</h3>
            <p className="text-gray-700 mb-2">
              <code className="bg-gray-100 px-2 py-1 rounded">NCAC = Total Ad Spend ÷ New Customers</code>
            </p>
            <p className="text-gray-600 text-sm">
              Lower is better. This tells you how much you're paying to acquire each new customer.
              Unlike platform CAC, this uses real Shopify customer data.
            </p>
            <div className="mt-2 text-sm">
              <span className="text-green-600 font-medium">&lt;$30 = Great</span>
              <span className="mx-2 text-gray-400">|</span>
              <span className="text-yellow-600 font-medium">$30-50 = Good</span>
              <span className="mx-2 text-gray-400">|</span>
              <span className="text-red-600 font-medium">&gt;$50 = High</span>
            </div>
          </div>
        </div>
      </section>

      {/* How to Use */}
      <section className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-yellow-100 rounded-lg">
            <TrendingUp className="text-yellow-600" size={24} />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">How to Make Decisions</h2>
        </div>

        <div className="space-y-4">
          <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
            <h3 className="font-semibold text-green-800 mb-2">When to Scale (Increase Budget)</h3>
            <ul className="text-green-700 text-sm space-y-1 list-disc list-inside">
              <li>3+ signals agree (revenue, customers, Amazon all follow spend)</li>
              <li>NCAC is below target (you have headroom)</li>
              <li>MER is above 3.0x (efficient spending)</li>
            </ul>
          </div>

          <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-lg">
            <h3 className="font-semibold text-yellow-800 mb-2">When to Hold</h3>
            <ul className="text-yellow-700 text-sm space-y-1 list-disc list-inside">
              <li>Mixed signals (some agree, some conflict)</li>
              <li>NCAC at or near target</li>
              <li>Need more data to be confident</li>
            </ul>
          </div>

          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <h3 className="font-semibold text-red-800 mb-2">When to Cut</h3>
            <ul className="text-red-700 text-sm space-y-1 list-disc list-inside">
              <li>Most signals conflict (spend up, results down)</li>
              <li>NCAC exceeds target significantly</li>
              <li>MER dropping below 2.0x</li>
            </ul>
          </div>
        </div>
      </section>

      {/* Recommended Actions */}
      <section className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-orange-100 rounded-lg">
            <Users className="text-orange-600" size={24} />
          </div>
          <h2 className="text-xl font-semibold text-gray-900">Recommended Actions</h2>
        </div>
        <p className="text-gray-700 mb-4">
          Based on your signal data and efficiency metrics, TriSignal generates specific budget recommendations:
        </p>
        <ul className="text-gray-700 space-y-2 list-disc list-inside">
          <li><strong>HIGH priority</strong> (red): Actions that should be taken soon</li>
          <li><strong>MEDIUM priority</strong> (yellow): Actions to consider this week</li>
          <li><strong>LOW priority</strong> (gray): Optional optimizations</li>
        </ul>
        <p className="text-gray-700 mt-4">
          When you click <strong>"Complete"</strong>, the action is logged to your Activity Log and
          removed from recommendations. Actions already completed in the last 3 days won't appear again.
        </p>
      </section>

      {/* Tips */}
      <section className="bg-blue-50 border border-blue-200 rounded-xl p-6">
        <h2 className="text-lg font-semibold text-blue-900 mb-3">Pro Tips</h2>
        <ul className="text-blue-800 space-y-2">
          <li>
            <strong>Use 7-day view</strong> for tactical decisions (what to do this week)
          </li>
          <li>
            <strong>Use 14-day view</strong> to confirm trends before bigger changes
          </li>
          <li>
            <strong>Use 30-day view</strong> for strategic planning
          </li>
          <li>
            <strong>Don't panic</strong> over 1-2 days of data — look for consistent patterns
          </li>
          <li>
            <strong>Check the Activity Log</strong> to see what changes you made and when
          </li>
        </ul>
      </section>

      <div className="mt-8 text-center">
        <Link
          href="/trisignal"
          className="inline-flex items-center gap-2 px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors"
        >
          <ArrowLeft size={18} />
          Back to TriSignal
        </Link>
      </div>
    </div>
  );
}
