import React, { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, TooltipProps, XAxis, YAxis } from 'recharts'
import { SOURCES, sourceName } from '../../constants/sources'
import { CollectionDay } from '../../types'
import { Card, ChartTooltipBox, EmptyState, SectionTitle, SourcePills, StatusBadge, dayMonth, fmt } from '../ui'

const OneTooltip: React.FC<TooltipProps<number, string> & { source: string; days: CollectionDay[] }> = ({
  active,
  label,
  source,
  days,
}) => {
  const day = days.find((d) => d.date === label)
  const cell = day?.by_source[source]
  if (!active || !day || !cell) return null
  return (
    <ChartTooltipBox className="w-56">
      <div className="font-semibold">
        {sourceName(source)} · {day.dow} {dayMonth(day.date)}
      </div>
      <div className="my-1.5">
        <StatusBadge status={cell.status} emptyText="Không có lần chạy" />
      </div>
      <div className="leading-loose">
        <b className="tabular-nums">{fmt(cell.count)}</b> tin · {cell.failed_runs} lần lỗi
      </div>
      {cell.first_start && (
        <div className="leading-loose">
          {cell.runs} lần chạy · {cell.first_start}
          {cell.last_end ? ` – ${cell.last_end}` : ''}
        </div>
      )}
    </ChartTooltipBox>
  )
}

export const SourceDailyChart: React.FC<{ days: CollectionDay[] }> = ({ days }) => {
  const [source, setSource] = useState<string>('careerviet')
  const color = SOURCES.find((s) => s.id === source)?.color
  const rows = days.map((d) => ({ date: d.date, count: d.by_source[source]?.count ?? 0 }))
  const total = rows.reduce((sum, r) => sum + r.count, 0)
  const failDays = days.filter((d) => d.by_source[source]?.status === 'fail').length
  return (
    <Card>
      <div className="flex flex-wrap justify-between items-start gap-4">
        <SectionTitle title="Tin cào theo ngày của từng nguồn" hint="Chọn một nguồn. Di chuột vào cột để xem trạng thái, số tin và giờ chạy." />
        <div className="flex gap-3">
          <div className="px-3.5 py-2.5 rounded-xl bg-panel flex flex-col">
            <span className="text-xs text-ink-muted">Tổng {days.length} ngày</span>
            <span className="text-xl font-bold tabular-nums">{fmt(total)}</span>
          </div>
          <div className="px-3.5 py-2.5 rounded-xl bg-panel flex flex-col">
            <span className="text-xs text-ink-muted">Ngày lỗi</span>
            <span className={`text-xl font-bold tabular-nums ${failDays ? 'text-state-fail-fg' : ''}`}>{failDays}</span>
          </div>
        </div>
      </div>
      <SourcePills label="Chọn nguồn" selected={source} onSelect={setSource} />
      {total > 0 ? (
        <div className="h-60">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#EFEEF4" />
              <XAxis dataKey="date" tickFormatter={dayMonth} tick={{ fill: '#6B6980', fontSize: 12 }} axisLine={{ stroke: '#D9D8E2' }} tickLine={false} />
              <YAxis width={44} allowDecimals={false} tick={{ fill: '#6B6980', fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: '#F1EFFD' }} content={<OneTooltip source={source} days={days} />} />
              <Bar dataKey="count" fill={color} radius={[5, 5, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <EmptyState message={`${sourceName(source)} không có tin nào trong khoảng thời gian này.`} />
      )}
    </Card>
  )
}
