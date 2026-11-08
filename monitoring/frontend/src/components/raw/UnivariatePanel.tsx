import React, { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, TooltipProps, XAxis, YAxis } from 'recharts'
import { api } from '../../api/client'
import { SOURCES, sourceName } from '../../constants/sources'
import { UnivariateItem } from '../../types'
import { Card, ChartTooltipBox, EmptyState, ErrorState, LoadingState, SectionTitle, fmt, useAsync } from '../ui'

const TABS = ['F1 Title', 'F2 Company', 'F3 Location', 'F4 Salary', 'F5 Experience', 'F6 Level', 'F7 Skills', 'F8 Posted']

const BinTooltip: React.FC<TooltipProps<number, string> & { unit?: string }> = ({ active, payload, unit }) => {
  const item = payload?.[0]?.payload as UnivariateItem | undefined
  if (!active || !item) return null
  return (
    <ChartTooltipBox className="w-48">
      <div className="font-semibold">
        {item.label} {unit}
      </div>
      <div className="leading-loose">
        <b className="tabular-nums">{fmt(item.count)}</b> tin
      </div>
      <div className="leading-loose text-nav-text">{item.pct}% số tin có giá trị</div>
    </ChartTooltipBox>
  )
}

export const UnivariatePanel: React.FC<{ source: string }> = ({ source }) => {
  const [code, setCode] = useState('F4')
  const { data, error, loading } = useAsync(() => api.univariate(source, code), [source, code])
  const color = SOURCES.find((s) => s.id === source)?.color
  const items = data?.items ?? []
  const max = Math.max(1, ...items.map((i) => i.count))

  return (
    <Card>
      <SectionTitle
        title={`Phân tích đơn biến · ${sourceName(source)}`}
        hint="Phân bố giá trị của từng feature sau chuẩn hóa. Chọn một feature; di chuột vào cột để xem số tin và tỉ lệ."
      />
      <div role="tablist" aria-label="Chọn feature" className="flex flex-wrap gap-2">
        {TABS.map((label) => {
          const id = label.slice(0, 2)
          const on = id === code
          return (
            <button
              key={id}
              type="button"
              role="tab"
              aria-selected={on}
              onClick={() => setCode(id)}
              className={`min-h-10 px-3.5 rounded-full text-[13px] font-semibold border ${
                on ? 'bg-brand-500 border-brand-500 text-white' : 'bg-white border-line-strong text-ink-soft'
              }`}
            >
              {label}
            </button>
          )
        })}
      </div>
      {error && <ErrorState />}
      {loading && <LoadingState />}
      {!loading && data?.kind === 'empty' && <EmptyState message={data.unavailable_reason ?? 'Chưa có dữ liệu.'} />}
      {!loading && data && data.kind !== 'empty' && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            {data.stats?.map((s) => (
              <div key={s.k} className="bg-panel rounded-xl px-3.5 py-3 flex flex-col gap-0.5 min-w-0">
                <span className="text-xs text-ink-muted">{s.k}</span>
                <span className="text-xl font-bold tabular-nums truncate">{s.v ?? '—'}</span>
              </div>
            ))}
          </div>
          <div className="flex justify-between items-baseline gap-3">
            <span className="font-semibold">{data.title}</span>
            <span className="text-[13px] text-ink-muted">{fmt(data.base)} tin</span>
          </div>
          {data.kind === 'num' ? (
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={items} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="#EFEEF4" />
                  <XAxis dataKey="label" tick={{ fill: '#4E4C5E', fontSize: 12 }} axisLine={{ stroke: '#D9D8E2' }} tickLine={false} />
                  <YAxis width={44} allowDecimals={false} tick={{ fill: '#6B6980', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: '#F1EFFD' }} content={<BinTooltip unit={data.unit} />} />
                  <Bar dataKey="count" fill={color} radius={[5, 5, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex flex-col gap-1.5">
              {items.map((item) => (
                <div key={item.label} title={`${item.label}: ${fmt(item.count)} tin · ${item.pct}%`} className="grid grid-cols-[minmax(0,170px)_minmax(0,1fr)_110px] items-center gap-3 min-h-10 px-2 rounded-[10px] hover:bg-[#F1EFFD]">
                  <span className="font-medium truncate">{item.label}</span>
                  <span className="h-[18px] rounded-[5px] bg-ground overflow-hidden">
                    <span className="block h-[18px] rounded-[5px]" style={{ width: `${(100 * item.count) / max}%`, background: color }} />
                  </span>
                  <span className="text-[13px] text-right tabular-nums">
                    <b>{fmt(item.count)}</b> · {item.pct}%
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </Card>
  )
}
