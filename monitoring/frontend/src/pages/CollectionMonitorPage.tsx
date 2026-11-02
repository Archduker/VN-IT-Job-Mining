import React, { useEffect, useState } from 'react'
import { api } from '../api/client'
import { DailyChart } from '../components/collection/DailyChart'
import { ProgressChart } from '../components/collection/ProgressChart'
import { ScheduleGrid } from '../components/collection/ScheduleGrid'
import { SourceDailyChart } from '../components/collection/SourceDailyChart'
import { TodayPanel } from '../components/collection/TodayPanel'
import { ErrorState, LoadingState, StatCard, fmt, useAsync } from '../components/ui'

const POLL_MS = 60000

export const CollectionMonitorPage: React.FC = () => {
  const [days, setDays] = useState<7 | 14>(14)
  const [tick, setTick] = useState(0)
  const { data, error, loading } = useAsync(() => api.collection(days), [days, tick])

  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), POLL_MS)
    return () => clearInterval(id)
  }, [])

  if (error && !data) return <ErrorState />
  if (loading && !data) return <LoadingState />
  if (!data) return null

  const { kpi, queue } = data
  const delta = kpi.today - kpi.yesterday
  const uniquePct = kpi.unique_total === null ? 0 : Math.min(100, (100 * kpi.unique_total) / data.progress.target)
  const rate = kpi.runs_total ? Math.round((100 * (kpi.runs_ok ?? 0)) / kpi.runs_total) : null

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {data.unavailable_reason ? (
          <p className="m-0 px-3 py-2 rounded-lg bg-state-partial-bg text-state-partial-fg">{data.unavailable_reason}</p>
        ) : (
          <span />
        )}
        <div role="group" aria-label="Khoảng thời gian" className="flex bg-white border border-line-strong rounded-xl p-1 gap-1">
          {([7, 14] as const).map((d) => (
            <button
              key={d}
              type="button"
              aria-pressed={days === d}
              onClick={() => setDays(d)}
              className={`min-h-9 px-3.5 rounded-lg text-[13px] font-semibold ${
                days === d ? 'bg-brand-500 text-white' : 'text-[#4E4C5E]'
              }`}
            >
              {d} ngày
            </button>
          ))}
        </div>
      </div>

      <section aria-label="Chỉ số chính" className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label="Tin cào hôm nay"
          value={fmt(kpi.today)}
          sub={`${delta >= 0 ? '+' : '−'}${fmt(Math.abs(delta))} so với hôm qua`}
        />
        <StatCard
          label={`Tổng tin trong ${days} ngày`}
          value={fmt(kpi.total)}
          sub={`Trung bình ${fmt(kpi.avg_per_day)} tin/ngày · ${fmt(queue.pending)} URL chờ · ${fmt(queue.recheck_due)} đến hạn cào lại`}
        />
        <StatCard
          label="Lần chạy thành công"
          value={rate === null ? '—' : `${rate}%`}
          sub={kpi.runs_total === null ? 'Chưa có dữ liệu Airflow' : `${fmt(kpi.runs_ok)}/${fmt(kpi.runs_total)} lần chạy Crawl chi tiết`}
        />
        <StatCard
          label="Mẫu unique tích lũy"
          value={fmt(kpi.unique_total)}
          sub={kpi.unique_reason ?? `Mục tiêu ${fmt(data.progress.target)} mẫu`}
        >
          <div className="h-2 rounded-full bg-line overflow-hidden">
            <div className="h-2 rounded-full bg-brand-500" style={{ width: `${uniquePct}%` }} />
          </div>
        </StatCard>
      </section>

      <DailyChart days={data.days} hasData={data.has_data} />
      <SourceDailyChart days={data.days} />
      <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)] gap-6">
        <ScheduleGrid days={data.days.slice(-7)} schedule={data.schedule} airflowAvailable={data.airflow_available} />
        <TodayPanel steps={data.today_steps} queue={queue} />
      </div>
      <ProgressChart progress={data.progress} hasData={data.has_data} />
    </div>
  )
}
