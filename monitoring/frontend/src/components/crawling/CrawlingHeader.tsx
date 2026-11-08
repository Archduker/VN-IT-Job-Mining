import { Radio } from 'lucide-react'

import type { useCrawlingState } from './useCrawlingState'
type Props = Pick<ReturnType<typeof useCrawlingState>, 'selectedSource'>
export function CrawlingHeader({ selectedSource }: Props) {
 return <>
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-5 rounded-2xl bg-panel border border-line">
        <div>
          <div className="flex items-center space-x-2">
            <Radio className="w-4 h-4 text-indigo-400" />
            <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">
              Operations Module • Crawling Operations
            </span>
          </div>
          <h2 className="text-xl font-bold text-ink mt-1">
            Batch Crawler Orchestrator & URL Ledger ({selectedSource.toUpperCase()})
          </h2>
          <p className="text-xs text-ink-soft">
            Two-Phase Decoupled Crawler Architecture with Enum Lifecycle Tracking and Cloudflare R2 Sync.
          </p>
        </div>
      </div>


 </>
}
