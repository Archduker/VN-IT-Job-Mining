import React from 'react'
import { SOURCES } from '../../constants/sources'
import { CollectionDay, RunStatus, ScheduleItem, SourceDayCell } from '../../types'
import { Card, STATUS_META, SectionTitle, dayMonth, fmt } from '../ui'

const LEGEND: Exclude<RunStatus, null>[] = ['done', 'partial', 'fail', 'running']

const Cell: React.FC<{ cell: SourceDayCell; title: string; alignRight: boolean }> = ({ cell, title, alignRight }) => {
  const meta = cell.status ? STATUS_META[cell.status] : null
  const statusText = meta?.text ?? 'Không có lần chạy'
  return (
    <button
      type="button"
      aria-label={`${title}: ${statusText}, ${fmt(cell.count)} tin`}
      className={`group relative h-10 rounded-lg text-xs font-semibold ${meta?.cls ?? 'bg-panel text-ink-faint'}`}
    >
      {cell.status === 'fail' ? 'Lỗi' : fmt(cell.count)}
      <span
        role="tooltip"
        className={`hidden group-hover:block group-focus:block absolute bottom-full mb-2 w-60 bg-ink text-white rounded-xl px-3.5 py-3 text-left font-normal z-20 shadow-xl pointer-events-none ${
          alignRight ? 'right-0' : 'left-0'
        }`}
      >
        <span className="block font-semibold">{title}</span>
        <span className="block text-[13px] leading-relaxed mt-1">{statusText}</span>
        <span className="block text-[13px] leading-relaxed">
          {fmt(cell.count)} tin · {cell.failed_runs} lần lỗi
        </span>
        {cell.first_start && (
          <span className="block text-[13px] leading-relaxed">
            {cell.runs} lần chạy · {cell.first_start}
            {cell.last_end ? ` – ${cell.last_end}` : ''}
          </span>
        )}
      </span>
    </button>
  )
}

export const ScheduleGrid: React.FC<{
  days: CollectionDay[]
  schedule: ScheduleItem[]
  airflowAvailable: boolean
}> = ({ days, schedule, airflowAvailable }) => (
  <Card>
    <SectionTitle
      title="Lịch cào 7 ngày gần nhất"
      hint={
        airflowAvailable
          ? 'Mỗi ô là số tin của một nguồn trong ngày, màu theo kết quả các lần chạy. Di chuột vào ô để xem chi tiết.'
          : 'Mỗi ô là số tin của một nguồn trong ngày. Trạng thái lần chạy sẽ hiện khi kết nối được Airflow.'
      }
    />
    <div className="flex flex-wrap gap-2">
      {schedule.map((item) => (
        <span key={item.label} className="text-[13px] px-2.5 py-1.5 rounded-lg bg-ground">
          <b className="font-semibold">{item.label}</b> · {item.times.join(', ')} · {item.note}
        </span>
      ))}
    </div>
    <div className="overflow-x-auto pt-28 -mt-28">
      <div className="min-w-[640px] grid grid-cols-[130px_repeat(7,minmax(0,1fr))] gap-1.5">
        <div />
        {days.map((d) => (
          <div key={d.date} className={`text-center text-xs pb-1 leading-tight ${d.is_today ? 'text-brand-900 font-bold' : 'text-ink-faint font-medium'}`}>
            {d.dow}
            <br />
            {dayMonth(d.date)}
          </div>
        ))}
        {SOURCES.map((s) => (
          <React.Fragment key={s.id}>
            <div className="flex items-center gap-2 font-semibold">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ background: s.color }} />
              {s.name}
            </div>
            {days.map((d, k) => (
              <Cell key={d.date} cell={d.by_source[s.id]} title={`${s.name} · ${d.dow} ${dayMonth(d.date)}`} alignRight={k > 3} />
            ))}
          </React.Fragment>
        ))}
      </div>
    </div>
    <div className="flex flex-wrap gap-4 text-[13px] text-[#4E4C5E]">
      {LEGEND.map((key) => (
        <span key={key} className="inline-flex items-center gap-1.5">
          <span className={`w-3 h-3 rounded ${STATUS_META[key].cls.split(' ')[0]}`} />
          {STATUS_META[key].text}
        </span>
      ))}
    </div>
  </Card>
)
