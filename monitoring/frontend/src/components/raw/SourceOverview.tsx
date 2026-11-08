import React from 'react'
import { SOURCES } from '../../constants/sources'
import { SourceReport } from '../../types'
import { fmt } from '../ui'

const Tile: React.FC<{ label: string; value: string; sub?: string; warn?: boolean }> = ({ label, value, sub, warn }) => (
  <div className={`rounded-xl p-3.5 flex flex-col gap-1 min-w-0 ${warn ? 'bg-[#FCEEEC] text-state-fail-fg' : 'bg-panel'}`}>
    <span className={`text-[13px] ${warn ? '' : 'text-ink-muted'}`}>{label}</span>
    <span className="text-lg font-bold tabular-nums truncate">{value}</span>
    {sub && <span className={`text-xs ${warn ? '' : 'text-ink-muted'}`}>{sub}</span>}
  </div>
)

export const SourceOverview: React.FC<{ report: SourceReport }> = ({ report }) => {
  const source = SOURCES.find((s) => s.id === report.source)
  const { overview } = report
  return (
    <section className="bg-white rounded-2xl border border-line p-6 flex flex-wrap gap-6 items-center">
      <div className="flex-[1_1_240px] flex flex-col gap-2">
        <div className="flex items-center gap-2.5">
          <span className="w-3.5 h-3.5 rounded" style={{ background: source?.color }} />
          <h2 className="m-0 text-[22px] font-bold">{source?.name}</h2>
        </div>
        <span className="text-ink-muted">{report.domain}</span>
        {report.unavailable_reason && <p className="m-0 text-state-partial-fg">{report.unavailable_reason}</p>}
      </div>
      <div className="flex-[2_1_480px] grid grid-cols-2 lg:grid-cols-4 gap-3">
        <Tile label="Bản ghi đã tích hợp" value={fmt(overview.integrated_records)} sub={overview.clean_records === null ? undefined : `${fmt(overview.clean_records)} sau làm sạch`} />
        <Tile label="URL Ledger" value={fmt(overview.ledger?.total ?? null)} sub={overview.ledger ? `${fmt(overview.ledger.pending)} chờ · ${fmt(overview.ledger.failed)} lỗi` : 'Chưa có ledger trên máy này'} />
        <Tile label="Độ đầy đủ trung bình" value={overview.completeness_pct === null ? '—' : `${overview.completeness_pct}%`} sub="8 feature target" />
        <Tile label="Feature yếu nhất" value={overview.weakest ?? '—'} sub={overview.weakest_pct === null ? undefined : `${overview.weakest_pct}% đầy đủ`} warn={overview.weakest !== null} />
      </div>
    </section>
  )
}
