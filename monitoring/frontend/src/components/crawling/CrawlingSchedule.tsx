import { AlertCircle, Clock, Check, XCircle, Calendar, RefreshCw, Layers } from 'lucide-react'

import type { useCrawlingState } from './useCrawlingState'
type Props = Pick<ReturnType<typeof useCrawlingState>, 'phase1Data' | 'phase2Data' | 'engine' | 'weeklySchedule'>
const formatSlot = (iso: string | null): string => {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', weekday: 'short', day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' })
}

  const renderStatusBadge = (status: string) => {
    const s = status.toUpperCase()
    if (s === 'SUCCESS' || s === 'COMPLETED')
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
          <Check className="w-3 h-3" />
          <span>SUCCESS</span>
        </span>
      )
    if (s === 'RUNNING' || s === 'ACTIVE_QUEUE')
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-blue-500/15 text-blue-400 border border-blue-500/20">
          <RefreshCw className="w-3 h-3 animate-spin" />
          <span>RUNNING</span>
        </span>
      )
    if (s === 'FAILED')
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-500/15 text-rose-400 border border-rose-500/20">
          <XCircle className="w-3 h-3" />
          <span>FAILED</span>
        </span>
      )
    if (s === 'UNKNOWN')
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-state-idle-bg text-state-idle-fg">
          <AlertCircle className="w-3 h-3" />
          <span>KHÔNG RÕ</span>
        </span>
      )
    return (
      <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-ground text-ink-soft">
        <Clock className="w-3 h-3" />
        <span>SCHEDULED</span>
      </span>
    )
  }

export function CrawlingSchedule({ phase1Data, phase2Data, engine, weeklySchedule }: Props) {
 return <>
      {/* 3.1: PHASE 1 — DAILY URL DISCOVERY SCHEDULE */}
      {phase1Data.length > 0 && (
        <div className="p-5 rounded-2xl bg-panel border border-line space-y-4">
          <div className="border-b border-line pb-3">
            <h3 className="text-sm font-bold text-ink flex items-center space-x-2">
              <Layers className="w-4 h-4 text-indigo-400" />
              <span>3.1 Phase 1: Daily URL Discovery Schedule (05:00 hằng ngày)</span>
            </h3>
            <p className="text-xs text-ink-soft mt-0.5">
              Sweep catalog pages across all 8 portals and ingest new URLs into Ledger with PENDING status.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-panel text-ink-soft uppercase text-[10px] tracking-wider border-b border-line">
                <tr>
                  <th className="py-2.5 px-3">Portal</th>
                  <th className="py-2.5 px-3">Airflow DAG ID</th>
                  <th className="py-2.5 px-3">Task ID</th>
                  <th className="py-2.5 px-3">Run Time</th>
                  <th className="py-2.5 px-3">Pages Quota</th>
                  <th className="py-2.5 px-3">Total URLs Discovered</th>
                  <th className="py-2.5 px-3 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {phase1Data.map((d) => (
                  <tr key={`p1-${d.focal_source}`} className="hover:bg-ground transition">
                    <td className="py-2.5 px-3 font-semibold text-indigo-300 uppercase">{d.focal_source}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-ink">{d.dag_id}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-ink">{d.task_id}</td>
                    <td className="py-2.5 px-3 text-ink">{d.scheduled_time}</td>
                    <td className="py-2.5 px-3 text-ink font-mono font-bold">{d.quota_pages} Pages</td>
                    <td className="py-2.5 px-3 text-emerald-400 font-mono font-bold">{d.total_discovered.toLocaleString()} URLs</td>
                    <td className="py-2.5 px-3 text-right">{renderStatusBadge(d.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 3.2: PHASE 2 — ADAPTIVE DETAIL EXTRACTION SCHEDULE */}
      <div className="p-5 rounded-2xl bg-panel border border-line space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-line pb-3">
          <div>
            <h3 className="text-sm font-bold text-ink flex items-center space-x-2">
              <Calendar className="w-4 h-4 text-indigo-400" />
              <span>3.2 Phase 2: Adaptive Detail Extraction Schedule</span>
            </h3>
            <p className="text-xs text-ink-soft mt-0.5">
              Router chạy tối đa <strong className="text-indigo-300 font-mono">{weeklySchedule?.batch_limit ?? 30}</strong> tin mỗi ca,
              nghỉ {weeklySchedule?.cooldown_minutes ?? 55} phút giữa các ca và bỏ qua khi hàng đợi rỗng
              • Backlog <strong className="text-amber-400 font-mono">{weeklySchedule?.total_uncrawled_pending?.toLocaleString() ?? 0}</strong> tin
              {weeklySchedule && !weeklySchedule.airflow_available && ' • Chưa kết nối Airflow nên chưa có trạng thái lần chạy'}
            </p>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-panel text-ink-soft uppercase text-[10px] tracking-wider border-b border-line">
              <tr>
                <th className="py-2.5 px-3">Portal</th>
                <th className="py-2.5 px-3">Detail DAG ID</th>
                <th className="py-2.5 px-3">Run Time</th>
                <th className="py-2.5 px-3">Crawled</th>
                <th className="py-2.5 px-3">Backlog</th>
                <th className="py-2.5 px-3">Ca cần để xả</th>
                <th className="py-2.5 px-3">Lần chạy gần nhất</th>
                <th className="py-2.5 px-3">Engine</th>
                <th className="py-2.5 px-3 text-right">Airflow State</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {phase2Data.map((day) => (
                <tr key={`p2-${day.focal_source}`} className="hover:bg-ground transition">
                  <td className="py-2.5 px-3 font-semibold text-indigo-300 uppercase">{day.focal_source}</td>
                  <td className="py-2.5 px-3 font-mono text-[11px] text-ink">{day.dag_id}</td>
                  <td className="py-2.5 px-3 text-ink">{day.scheduled_time}</td>
                  <td className="py-2.5 px-3 font-mono text-emerald-400 font-bold">{day.actual_crawled.toLocaleString()} items</td>
                  <td className="py-2.5 px-3 font-mono font-bold">
                    <span className={day.uncrawled_pending > 0 ? 'text-amber-400' : 'text-ink-soft'}>
                      {day.uncrawled_pending.toLocaleString()} items
                    </span>
                  </td>
                  <td className="py-2.5 px-3 font-mono text-ink">{day.batches_needed} ca</td>
                  <td className="py-2.5 px-3 text-ink whitespace-nowrap">{formatSlot(day.last_run_start)}</td>
                  <td className="py-2.5 px-3 text-[11px] text-ink">{day.engine}</td>
                  <td className="py-2.5 px-3 text-right">{renderStatusBadge(day.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>


 </>
}
