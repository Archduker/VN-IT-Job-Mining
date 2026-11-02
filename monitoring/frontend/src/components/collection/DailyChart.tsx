import React, { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, TooltipProps, XAxis, YAxis } from 'recharts'
import { SOURCES } from '../../constants/sources'
import { CollectionDay } from '../../types'
import { Card, ChartTooltipBox, EmptyState, SectionTitle, SourcePills, dayMonth, fmt } from '../ui'

const DayTooltip: React.FC<TooltipProps<number, string> & { focus: string | null; days: CollectionDay[] }> = ({
  active,
  label,
  focus,
  days,
}) => {
  const index = days.findIndex((d) => d.date === label)
  if (!active || index < 0) return null
  const day = days[index]
  const prev = days[index - 1]
  const diff = prev ? day.total - prev.total : null
  return (
    <ChartTooltipBox className="w-60">
      <div className="flex justify-between items-baseline gap-2 mb-2">
        <span className="font-semibold">
          {day.dow} {dayMonth(day.date)}
        </span>
        {diff !== null && (
          <span className={`text-xs ${diff >= 0 ? 'text-[#8FD9B0]' : 'text-[#F39C94]'}`}>
            {diff >= 0 ? '+' : '−'}
            {fmt(Math.abs(diff))} so với hôm trước
          </span>
        )}
      </div>
      {SOURCES.map((s) => (
        <div key={s.id} className={`flex items-center gap-2 leading-loose ${focus && focus !== s.id ? 'opacity-50' : ''}`}>
          <span className="w-2 h-2 rounded-sm" style={{ background: s.color }} />
          <span className="flex-1">{s.name}</span>
          <span className="font-semibold tabular-nums">{fmt(day.by_source[s.id]?.count)}</span>
        </div>
      ))}
      <div className="flex justify-between border-t border-[#3A3850] mt-2 pt-2">
        <span>Tổng</span>
        <span className="font-bold tabular-nums">{fmt(day.total)}</span>
      </div>
    </ChartTooltipBox>
  )
}

export const DailyChart: React.FC<{ days: CollectionDay[]; hasData: boolean }> = ({ days, hasData }) => {
  const [focus, setFocus] = useState<string | null>(null)
  const rows = days.map((d) => ({
    date: d.date,
    ...Object.fromEntries(SOURCES.map((s) => [s.id, d.by_source[s.id]?.count ?? 0])),
  }))
  return (
    <Card>
      <SectionTitle
        title="Tin cào được theo ngày"
        hint="Mỗi cột là một ngày, chia màu theo nguồn. Di chuột vào cột để xem chi tiết; bấm vào tên nguồn để làm nổi bật nguồn đó."
      />
      <SourcePills label="Làm nổi bật nguồn" selected={focus} onSelect={(id) => setFocus(focus === id ? null : id)} />
      {hasData ? (
        <div className="h-[300px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid vertical={false} stroke="#EFEEF4" />
              <XAxis dataKey="date" tickFormatter={dayMonth} tick={{ fill: '#6B6980', fontSize: 12 }} axisLine={{ stroke: '#D9D8E2' }} tickLine={false} />
              <YAxis width={44} allowDecimals={false} tick={{ fill: '#6B6980', fontSize: 12 }} axisLine={false} tickLine={false} />
              <Tooltip cursor={{ fill: '#F1EFFD' }} content={<DayTooltip focus={focus} days={days} />} />
              {SOURCES.map((s) => (
                <Bar key={s.id} dataKey={s.id} stackId="a" fill={s.color} fillOpacity={focus && focus !== s.id ? 0.18 : 1} />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <EmptyState message="Chưa có URL Ledger hay file raw trên máy này. Chạy python scripts/sync_cloud_lakehouse.py --download để lấy dữ liệu từ R2." />
      )}
    </Card>
  )
}
