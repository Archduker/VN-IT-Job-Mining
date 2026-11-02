import React from 'react'
import { CollectionMonitor, TodayStep } from '../../types'
import { Card, SectionTitle, StatusBadge, fmt } from '../ui'

export const TodayPanel: React.FC<{ steps: TodayStep[]; queue: CollectionMonitor['queue'] }> = ({ steps, queue }) => (
  <Card>
    <SectionTitle title="Hôm nay" hint="Các bước của pipeline thu thập" />
    {steps.map((step) => (
      <div key={step.name} className="flex gap-3.5">
        <span className="w-12 shrink-0 font-semibold tabular-nums pt-3">{step.time ?? '—'}</span>
        <div className="flex-1 min-w-0 px-3.5 py-3 rounded-xl bg-panel flex flex-col gap-1.5">
          <div className="flex justify-between items-center gap-2">
            <span className="font-semibold">{step.name}</span>
            <StatusBadge status={step.status} />
          </div>
          <span className="text-[13px] text-ink-muted">{step.detail}</span>
        </div>
      </div>
    ))}
    <div className="mt-auto p-3.5 rounded-xl bg-brand-50 text-brand-900">
      <b className="font-semibold">Hàng đợi:</b> {fmt(queue.pending)} URL mới · {fmt(queue.recheck_due)} URL đến hạn cào lại sau 21 ngày ·{' '}
      {fmt(queue.failed)} lỗi
    </div>
  </Card>
)
