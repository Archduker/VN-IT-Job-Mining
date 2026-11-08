import { Cpu } from 'lucide-react'

import type { useCrawlingState } from './useCrawlingState'
type Props = Pick<ReturnType<typeof useCrawlingState>, 'sources' | 'selectedSource' | 'setSelectedSource' | 'setLogs' | 'setLedgerPage' | 'cloudSync'>
export function SourceSelector({ sources, selectedSource, setSelectedSource, setLogs, setLedgerPage, cloudSync }: Props) {
 return <>
      {/* 4. DATA SOURCE SELECTION MATRIX (8 PORTALS) */}
      <div className="p-5 rounded-2xl bg-panel border border-line space-y-4">
        <h3 className="text-sm font-bold text-ink flex items-center space-x-2">
          <Cpu className="w-4 h-4 text-indigo-400" />
          <span>Data Source Selection Matrix (8 Portals)</span>
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
          {sources.map((s) => {
            const isSelected = selectedSource === s.id
            const isRunning = s.status === 'running'
            const cloudCount = cloudSync?.sources?.[s.id]?.cloud_raw_count
            return (
              <button
                key={s.id}
                onClick={() => {
                  setSelectedSource(s.id)
                  setLogs([])
                  setLedgerPage(1)
                }}
                className={`p-3 rounded-xl border text-center transition-all ${
                  isSelected
                    ? 'bg-indigo-600/20 border-indigo-500/50 ring-2 ring-indigo-500/30'
                    : 'bg-panel border-line hover:border-line hover:bg-panel'
                }`}
              >
                <div className="flex items-center justify-center space-x-1.5 mb-1">
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${
                      isRunning ? 'bg-emerald-400 animate-pulse' : 'bg-ground'
                    }`}
                  />
                  <span className="text-xs font-bold uppercase text-ink truncate">{s.name}</span>
                </div>
                <p className="text-lg font-extrabold font-mono text-indigo-300">{cloudCount?.toLocaleString() ?? '—'}</p>
                <p className="text-[10px] text-ink-soft">in R2</p>
              </button>
            )
          })}
        </div>
      </div>


 </>
}
