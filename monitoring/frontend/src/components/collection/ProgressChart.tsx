import React from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, TooltipProps, XAxis, YAxis } from 'recharts'
import { CollectionMonitor } from '../../types'
import { Card, ChartTooltipBox, EmptyState, SectionTitle, dayMonth, fmt } from '../ui'

const ProgressTooltip: React.FC<TooltipProps<number, string> & { points: CollectionMonitor['progress']['points'] }> = ({
  active,
  label,
  points,
}) => {
  const index = points.findIndex((p) => p.date === label)
  if (!active || index < 0) return null
  const point = points[index]
  const gap = point.plan === null ? null : point.actual - point.plan
  const added = index > 0 ? point.actual - points[index - 1].actual : null
  return (
    <ChartTooltipBox className="w-52">
      <div className="font-semibold mb-1.5">{dayMonth(point.date)}</div>
      <div className="flex justify-between leading-loose">
        <span>Thực tế</span>
        <b className="tabular-nums">{fmt(point.actual)}</b>
      </div>
      <div className="flex justify-between leading-loose">
        <span>Kế hoạch</span>
        <span className="tabular-nums">{fmt(point.plan)}</span>
      </div>
      {added !== null && (
        <div className="flex justify-between leading-loose">
          <span>Mới trong ngày</span>
          <span className="tabular-nums">+{fmt(added)}</span>
        </div>
      )}
      {gap !== null && (
        <div className={`mt-1.5 ${gap >= 0 ? 'text-[#8FD9B0]' : 'text-[#F39C94]'}`}>
          {gap >= 0 ? `Vượt kế hoạch ${fmt(gap)}` : `Chậm ${fmt(-gap)} so với kế hoạch`}
        </div>
      )}
    </ChartTooltipBox>
  )
}

export const ProgressChart: React.FC<{ progress: CollectionMonitor['progress']; hasData: boolean }> = ({
  progress,
  hasData,
}) => (
  <Card>
    <div className="flex flex-wrap justify-between gap-3">
      <SectionTitle
        title="Tiến độ thu thập so với kế hoạch"
        hint={`Số tin đã cào tích lũy trước khử trùng lặp. Kế hoạch: đạt ${fmt(progress.target)} mẫu vào ${dayMonth(progress.target_date)}.`}
      />
      <div className="flex gap-4 items-center text-[13px] text-[#4E4C5E]">
        <span className="inline-flex items-center gap-1.5">
          <span className="w-[18px] h-[3px] rounded bg-brand-500" />
          Thực tế
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="w-[18px] border-t-2 border-dashed border-[#8C8A9C]" />
          Kế hoạch
        </span>
      </div>
    </div>
    {hasData ? (
      <div className="h-[220px]">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={progress.points} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
            <CartesianGrid vertical={false} stroke="#EFEEF4" />
            <XAxis dataKey="date" tickFormatter={dayMonth} tick={{ fill: '#6B6980', fontSize: 12 }} axisLine={{ stroke: '#D9D8E2' }} tickLine={false} />
            <YAxis width={52} tick={{ fill: '#6B6980', fontSize: 12 }} axisLine={false} tickLine={false} />
            <Tooltip content={<ProgressTooltip points={progress.points} />} />
            <Line dataKey="plan" stroke="#8C8A9C" strokeWidth={2} strokeDasharray="6 6" dot={false} isAnimationActive={false} />
            <Line dataKey="actual" stroke="#5B4CE6" strokeWidth={3} dot={false} activeDot={{ r: 6 }} isAnimationActive={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    ) : (
      <EmptyState message="Chưa có dữ liệu cào để tính tiến độ." />
    )}
  </Card>
)
