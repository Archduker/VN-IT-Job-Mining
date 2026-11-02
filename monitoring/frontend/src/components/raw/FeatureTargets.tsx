import React from 'react'
import { sourceName } from '../../constants/sources'
import { FeatureTarget } from '../../types'
import { Card, SectionTitle } from '../ui'

export const FeatureTargets: React.FC<{ source: string; targets: FeatureTarget[] }> = ({ source, targets }) => (
  <Card>
    <SectionTitle
      title="8 Feature Target"
      hint={`8 trường đích mà mọi nguồn đều phải chuẩn hóa về, kèm trường thô tương ứng trong bản cào của ${sourceName(source)}.`}
    />
    <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3">
      {targets.map((t) => (
        <div key={t.code} className="border border-line-strong rounded-xl p-4 flex flex-col gap-2.5">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded-md bg-brand-50 text-brand-700 text-xs font-bold">{t.code}</span>
            <span className="font-semibold text-[15px]">{t.name}</span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-ink-faint">Dùng cho</span>
            <span className="text-[13px]">{t.use}</span>
          </div>
          <div className="flex flex-col gap-0.5">
            <span className="text-xs text-ink-faint">Trường thô ở {sourceName(source)}</span>
            <span className={`text-[13px] font-semibold break-words ${t.raw_key ? '' : 'text-state-partial-fg'}`}>
              {t.raw_key ?? 'Flattener chưa lấy trường này'}
            </span>
          </div>
          <div className="flex flex-col gap-0.5 mt-auto pt-2.5 border-t border-line">
            <span className="text-xs text-ink-faint">Chuẩn hóa thành</span>
            <span className="text-[13px]">{t.std}</span>
          </div>
        </div>
      ))}
    </div>
  </Card>
)
