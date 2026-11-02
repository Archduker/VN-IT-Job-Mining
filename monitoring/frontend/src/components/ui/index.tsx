import React, { useEffect, useState } from 'react'
import { AlertCircle, FlaskConical, Inbox, Loader2 } from 'lucide-react'
import { RunStatus } from '../../types'
import { SOURCES } from '../../constants/sources'

export const Card: React.FC<{ className?: string; children: React.ReactNode }> = ({
  className = '',
  children,
}) => (
  <section className={`bg-white rounded-2xl border border-line p-6 flex flex-col gap-4 min-w-0 ${className}`}>
    {children}
  </section>
)

export const SectionTitle: React.FC<{ title: React.ReactNode; hint?: React.ReactNode }> = ({ title, hint }) => (
  <div>
    <h2 className="text-lg font-semibold text-ink">{title}</h2>
    {hint && <p className="mt-1 text-ink-muted">{hint}</p>}
  </div>
)

export const StatCard: React.FC<{
  label: string
  value: React.ReactNode
  sub?: React.ReactNode
  children?: React.ReactNode
}> = ({ label, value, sub, children }) => (
  <div className="bg-white rounded-2xl border border-line p-5 flex flex-col gap-2 min-w-0">
    <span className="text-[13px] text-ink-muted">{label}</span>
    <span className="text-3xl font-bold tabular-nums text-ink">{value}</span>
    {sub && <span className="text-[13px] text-ink-muted">{sub}</span>}
    {children}
  </div>
)

export const STATUS_META: Record<Exclude<RunStatus, null>, { text: string; cls: string }> = {
  done: { text: 'Xong', cls: 'bg-state-done-bg text-state-done-fg' },
  partial: { text: 'Xong một phần', cls: 'bg-state-partial-bg text-state-partial-fg' },
  fail: { text: 'Lỗi', cls: 'bg-state-fail-bg text-state-fail-fg' },
  running: { text: 'Đang chạy', cls: 'bg-state-running-bg text-state-running-fg' },
}

export const StatusBadge: React.FC<{ status: RunStatus; emptyText?: string }> = ({
  status,
  emptyText = 'Chưa có dữ liệu',
}) => {
  const meta = status ? STATUS_META[status] : null
  return (
    <span
      className={`inline-block px-2 py-0.5 rounded-md text-xs font-semibold whitespace-nowrap ${
        meta ? meta.cls : 'bg-state-idle-bg text-state-idle-fg'
      }`}
    >
      {meta ? meta.text : emptyText}
    </span>
  )
}

export const SourcePills: React.FC<{
  selected: string | null
  onSelect: (id: string) => void
  label: string
}> = ({ selected, onSelect, label }) => (
  <div role="group" aria-label={label} className="flex flex-wrap gap-2">
    {SOURCES.map((s) => {
      const on = selected === s.id
      return (
        <button
          key={s.id}
          type="button"
          aria-pressed={on}
          onClick={() => onSelect(s.id)}
          style={{ borderColor: on ? s.color : undefined }}
          className={`inline-flex items-center gap-2 min-h-9 px-3 rounded-full text-[13px] border bg-white text-ink ${
            on ? 'font-semibold border-2' : 'font-medium border-line-strong'
          }`}
        >
          <span className="w-2.5 h-2.5 rounded-sm" style={{ background: s.color }} />
          {s.name}
        </button>
      )
    })}
  </div>
)

export const ChartTooltipBox: React.FC<{ children: React.ReactNode; className?: string }> = ({
  children,
  className = '',
}) => (
  <div className={`bg-ink text-white rounded-xl px-3.5 py-3 text-[13px] shadow-xl ${className}`}>{children}</div>
)

export const EmptyState: React.FC<{ message: string; className?: string }> = ({ message, className = '' }) => (
  <div className={`flex flex-col items-center justify-center gap-2 py-10 px-4 text-center text-ink-muted ${className}`}>
    <Inbox className="w-6 h-6 text-ink-faint" aria-hidden="true" />
    <p className="max-w-md">{message}</p>
  </div>
)

export const LoadingState: React.FC<{ message?: string }> = ({ message = 'Đang tải dữ liệu…' }) => (
  <div role="status" className="flex items-center justify-center gap-2 py-10 text-ink-muted">
    <Loader2 className="w-5 h-5 animate-spin" aria-hidden="true" />
    {message}
  </div>
)

export const ErrorState: React.FC<{ message?: string }> = ({
  message = 'Không gọi được API monitoring. Kiểm tra backend ở cổng 8000.',
}) => (
  <div role="alert" className="flex items-center gap-2 p-4 rounded-xl bg-state-fail-bg text-state-fail-fg">
    <AlertCircle className="w-5 h-5 shrink-0" aria-hidden="true" />
    {message}
  </div>
)

export const SampleDataNotice: React.FC = () => (
  <div className="mb-5 flex items-center gap-2 p-3 rounded-xl bg-state-partial-bg text-state-partial-fg font-medium">
    <FlaskConical className="w-4 h-4 shrink-0" aria-hidden="true" />
    Số liệu mẫu: trang này còn dùng số minh họa, chưa phản ánh dữ liệu thật.
  </div>
)

export const useAsync = <T,>(load: () => Promise<T>, deps: React.DependencyList) => {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState(false)
  const [loading, setLoading] = useState(true)
  useEffect(() => {
    let alive = true
    setLoading(true)
    setError(false)
    load()
      .then((value) => {
        if (alive) setData(value)
      })
      .catch(() => {
        if (alive) setError(true)
      })
      .finally(() => {
        if (alive) setLoading(false)
      })
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return { data, error, loading }
}

export const fmt = (n: number | null | undefined): string =>
  n === null || n === undefined ? '—' : Math.round(n).toLocaleString('vi-VN')

export const dayMonth = (iso: string): string => `${iso.slice(8, 10)}/${iso.slice(5, 7)}`
