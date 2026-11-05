import React from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, TooltipProps, XAxis, YAxis } from 'recharts'
import { Info } from 'lucide-react'
import { ChartTooltipBox, EmptyState, fmt } from '../ui'

/** Giờ chạy pipeline của báo cáo, để người xem biết số liệu cũ hay mới. */
export const ReportStamp: React.FC<{ generatedAt: string | null; reason?: string | null }> = ({ generatedAt, reason }) => {
  if (reason) {
    return <p className="m-0 px-3 py-2 rounded-lg bg-state-partial-bg text-state-partial-fg">{reason}</p>
  }
  if (!generatedAt) return null
  const when = new Date(generatedAt).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' })
  return (
    <p className="m-0 flex items-center gap-2 text-ink-muted">
      <Info className="w-4 h-4 shrink-0" aria-hidden="true" />
      Số liệu từ lần chạy pipeline lúc {when}. Chạy lại pipeline để cập nhật.
    </p>
  )
}

export const pct = (value: number | null | undefined): string =>
  value === null || value === undefined ? '—' : `${value.toLocaleString('vi-VN', { maximumFractionDigits: 2 })}%`

const RankTooltip: React.FC<TooltipProps<number, string> & { unit: string }> = ({ active, payload, unit }) => {
  const row = payload?.[0]
  if (!active || !row) return null
  return (
    <ChartTooltipBox>
      <div className="font-semibold">{(row.payload as { label: string }).label}</div>
      <div className="tabular-nums">
        {fmt(row.value ?? null)} {unit}
      </div>
    </ChartTooltipBox>
  )
}

/** Biểu đồ cột ngang cho danh sách xếp hạng (nhóm nghề, thành phố, kỹ năng...). */
export const RankBars: React.FC<{
  items: { label: string; count: number; color?: string }[]
  unit?: string
  empty: string
  labelWidth?: number
}> = ({ items, unit = 'tin', empty, labelWidth = 140 }) => {
  if (!items.length) return <EmptyState message={empty} />
  return (
    <div style={{ height: Math.max(160, items.length * 30 + 24) }}>
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={items} layout="vertical" margin={{ top: 4, right: 16, left: 0, bottom: 0 }}>
          <CartesianGrid horizontal={false} stroke="#EFEEF4" />
          <XAxis type="number" allowDecimals={false} tick={{ fill: '#6B6980', fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="label" width={labelWidth} tick={{ fill: '#3A3850', fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: '#F1EFFD' }} content={<RankTooltip unit={unit} />} />
          <Bar dataKey="count" radius={[0, 5, 5, 0]}>
            {items.map((item) => (
              <Cell key={item.label} fill={item.color ?? '#5B4CE6'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Thanh phần trăm nhỏ dùng trong bảng. */
export const PctBar: React.FC<{ value: number | null }> = ({ value }) => (
  <div className="flex items-center gap-2 min-w-[140px]">
    <div className="flex-1 h-2 rounded-full bg-line overflow-hidden">
      <div className="h-2 rounded-full bg-brand-500" style={{ width: `${Math.min(100, value ?? 0)}%` }} />
    </div>
    <span className="w-14 text-right tabular-nums text-ink-soft">{pct(value)}</span>
  </div>
)

export const TableShell: React.FC<{ head: string[]; children: React.ReactNode; alignRightFrom?: number }> = ({
  head,
  children,
  alignRightFrom = 1,
}) => (
  <div className="overflow-x-auto -mx-6 px-6">
    <table className="w-full text-left text-[13px] border-collapse">
      <thead>
        <tr className="text-ink-muted border-b border-line">
          {head.map((h, i) => (
            <th key={h} scope="col" className={`py-2.5 pr-4 font-medium whitespace-nowrap ${i >= alignRightFrom ? 'text-right' : ''}`}>
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-line">{children}</tbody>
    </table>
  </div>
)
