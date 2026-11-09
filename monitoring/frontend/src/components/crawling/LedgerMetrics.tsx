import { CheckCircle2, AlertCircle, Clock, RotateCcw, XCircle, Layers } from 'lucide-react'

import type { useCrawlingState } from './useCrawlingState'
type Props = Pick<ReturnType<typeof useCrawlingState>, 'statusFilter' | 'setStatusFilter' | 'enumSummary' | 'weeklySchedule' | 'cloudSync'>
const formatSlot = (iso: string | null): string => {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

export function LedgerMetrics({ statusFilter, setStatusFilter, enumSummary, weeklySchedule, cloudSync }: Props) {
 return <>
      {/* 5. BIG KPI HERO CARDS */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl bg-panel border border-line text-center">
          <p className="text-xs text-ink-soft uppercase tracking-wider font-bold mb-2">Total URLs in Ledger</p>
          <p className="text-4xl font-extrabold font-mono text-ink">{enumSummary?.total?.toLocaleString() || '—'}</p>
          <p className="text-xs text-ink-soft mt-1">Discovered Catalog</p>
        </div>
        <div className="p-5 rounded-2xl bg-panel border border-line text-center">
          <p className="text-xs text-ink-soft uppercase tracking-wider font-bold mb-2">Raw Objects in R2</p>
          <p className="text-4xl font-extrabold font-mono text-indigo-300">{cloudSync?.total_cloud_raw?.toLocaleString() ?? '—'}</p>
          <p className="text-xs text-ink-soft mt-1">Stored in Bucket</p>
        </div>
        <div className="p-5 rounded-2xl bg-panel border border-line text-center">
          <p className="text-xs text-ink-soft uppercase tracking-wider font-bold mb-2">Pending Extraction</p>
          <p className="text-4xl font-extrabold font-mono text-amber-400">{weeklySchedule?.total_uncrawled_pending?.toLocaleString() ?? enumSummary?.pending?.count?.toLocaleString() ?? '—'}</p>
          <p className="text-xs text-ink-soft mt-1">Queued for Phase 2</p>
        </div>
        <div className="p-5 rounded-2xl bg-panel border border-line text-center">
          <p className="text-xs text-ink-soft uppercase tracking-wider font-bold mb-2">Ca detail kế tiếp</p>
          <p className="text-2xl font-extrabold font-mono text-violet-400">{formatSlot(weeklySchedule?.next_detail_slot ?? null)}</p>
          <p className="text-xs text-ink-soft mt-1">Giờ Việt Nam, theo adaptive router</p>
        </div>
      </div>

      {/* 6. 5-STATE ENUM LIFECYCLE BREAKDOWN */}
      <div className="p-5 rounded-2xl bg-panel border border-line space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-line pb-3">
          <div>
            <h3 className="text-sm font-bold text-ink flex items-center space-x-2">
              <Layers className="w-4 h-4 text-indigo-400" />
              <span>5-State Enum Lifecycle Breakdown</span>
            </h3>
            <p className="text-xs text-ink-soft mt-0.5">
              Total <span className="text-ink font-bold font-mono">{enumSummary?.total?.toLocaleString() || '—'}</span> URLs across the entire URL Ledger system. Click a card to filter.
            </p>
          </div>
          {statusFilter !== 'ALL' && (
            <button
              onClick={() => setStatusFilter('ALL')}
              className="text-xs text-indigo-400 hover:underline flex items-center space-x-1 font-semibold"
            >
              <span>Clear filter (Filtering: {statusFilter})</span>
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {[
            { key: 'PENDING', label: 'PENDING', data: enumSummary?.pending, icon: <Clock className="w-5 h-5 text-amber-400" />, color: 'amber', desc: 'Queued for Phase 2' },
            { key: 'DONE', label: 'DONE', data: enumSummary?.done, icon: <CheckCircle2 className="w-5 h-5 text-emerald-400" />, color: 'emerald', desc: 'Raw As-Is Extracted & Hashed' },
            { key: 'RECHECK_DUE', label: 'RECHECK_DUE', data: enumSummary?.recheck_due, icon: <RotateCcw className="w-5 h-5 text-indigo-400" />, color: 'indigo', desc: 'Re-crawl due (≥21 days)' },
            { key: 'CLOSED', label: 'CLOSED', data: enumSummary?.closed, icon: <XCircle className="w-5 h-5 text-ink-soft" />, color: 'slate', desc: 'Expired / 404 / Removed' },
            { key: 'FAILED', label: 'FAILED', data: enumSummary?.failed, icon: <AlertCircle className="w-5 h-5 text-rose-400" />, color: 'rose', desc: 'Network / Bot blocked' },
          ].map((st) => (
            <div
              key={st.key}
              onClick={() => setStatusFilter(statusFilter === st.key ? 'ALL' : st.key)}
              className={`p-4 rounded-xl cursor-pointer border transition-all ${
                statusFilter === st.key
                  ? `bg-${st.color}-500/20 border-${st.color}-500 ring-2 ring-${st.color}-500/40`
                  : `bg-panel border-line hover:border-${st.color}-500/50 hover:bg-panel`
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className={`text-xs font-bold uppercase tracking-wider text-${st.color}-400`}>{st.label}</span>
                {st.icon}
              </div>
              <p className="text-3xl font-extrabold font-mono text-ink">{st.data?.count?.toLocaleString() || 0}</p>
              <div className="flex items-center justify-between mt-1">
                <span className="text-[10px] text-ink-soft">{st.desc}</span>
                <span className={`text-xs font-semibold text-${st.color}-400`}>{st.data?.pct || 0}%</span>
              </div>
            </div>
          ))}
        </div>

        {/* Multi-segment visual progress bar */}
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center justify-between text-[11px] text-ink-soft">
            <span>URL Lifecycle Distribution Across All Portals:</span>
            <span className="font-mono text-ink">100% Surveyed</span>
          </div>
          <div className="h-3 w-full rounded-full bg-panel overflow-hidden flex border border-line">
            <div style={{ width: `${enumSummary?.done?.pct || 0}%` }} title={`DONE: ${enumSummary?.done?.pct}%`} className="bg-emerald-500 h-full transition-all" />
            <div style={{ width: `${enumSummary?.pending?.pct || 0}%` }} title={`PENDING: ${enumSummary?.pending?.pct}%`} className="bg-amber-500 h-full transition-all" />
            <div style={{ width: `${enumSummary?.recheck_due?.pct || 0}%` }} title={`RECHECK_DUE: ${enumSummary?.recheck_due?.pct}%`} className="bg-indigo-500 h-full transition-all" />
            <div style={{ width: `${enumSummary?.closed?.pct || 0}%` }} title={`CLOSED: ${enumSummary?.closed?.pct}%`} className="bg-ground h-full transition-all" />
            <div style={{ width: `${enumSummary?.failed?.pct || 0}%` }} title={`FAILED: ${enumSummary?.failed?.pct}%`} className="bg-rose-500 h-full transition-all" />
          </div>
        </div>
      </div>


 </>
}
