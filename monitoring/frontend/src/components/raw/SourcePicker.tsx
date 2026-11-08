import React from 'react'
import { SOURCES } from '../../constants/sources'
import { SourceOverviewItem } from '../../types'

export const SourcePicker: React.FC<{
  items: SourceOverviewItem[]
  selected: string
  onSelect: (id: string) => void
}> = ({ items, selected, onSelect }) => (
  <div role="group" aria-label="Chọn nguồn" className="grid grid-cols-2 sm:grid-cols-4 xl:grid-cols-8 gap-2.5">
    {SOURCES.map((s) => {
      const on = s.id === selected
      const pct = items.find((i) => i.source === s.id)?.completeness_pct ?? null
      return (
        <button
          key={s.id}
          type="button"
          aria-pressed={on}
          onClick={() => onSelect(s.id)}
          style={{ borderColor: on ? s.color : undefined }}
          className={`flex flex-col items-start gap-1 min-h-16 px-3 py-2.5 rounded-xl text-left min-w-0 ${
            on ? 'bg-white border-2 shadow-md' : 'bg-[#FBFBFD] border border-line-strong'
          }`}
        >
          <span className="flex items-center gap-2 font-semibold truncate max-w-full">
            <span className="w-2.5 h-2.5 rounded-sm shrink-0" style={{ background: s.color }} />
            {s.name}
          </span>
          <span className="text-xs text-ink-muted">Độ đầy đủ {pct === null ? '—' : `${pct}%`}</span>
        </button>
      )
    })}
  </div>
)
