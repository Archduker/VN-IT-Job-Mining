import { Play, Square } from 'lucide-react'

import type { useCrawlingState } from './useCrawlingState'
type Props = Pick<ReturnType<typeof useCrawlingState>, 'handleStartCrawl' | 'handleStopCrawl' | 'selectedSource' | 'phase' | 'setPhase' | 'maxItems' | 'setMaxItems' | 'engine' | 'setEngine' | 'syncR2' | 'setSyncR2' | 'isCrawling'>
export function CrawlTriggerCard({ handleStartCrawl, handleStopCrawl, selectedSource, phase, setPhase, maxItems, setMaxItems, engine, setEngine, syncR2, setSyncR2, isCrawling }: Props) {
 return <>
      {/* Crawl Control Deck */}
      <div className="p-5 rounded-2xl bg-panel border border-line space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <label className="text-[11px] uppercase tracking-wider text-ink-soft font-bold block mb-1">
                Crawl Phase
              </label>
              <select
                value={phase}
                onChange={(e) => setPhase(e.target.value)}
                className="bg-panel border border-line text-ink text-xs rounded-xl px-3 py-2 font-medium focus:outline-none focus:border-indigo-500"
              >
                <option value="all">Full Pipeline (Phase 1 + Phase 2)</option>
                <option value="discover">Phase 1: URL Discovery</option>
                <option value="detail">Phase 2: Detail Extraction</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-wider text-ink-soft font-bold block mb-1">
                Batch Limit
              </label>
              <input
                type="number"
                min="1"
                max="100"
                value={maxItems}
                onChange={(e) => setMaxItems(Number(e.target.value))}
                className="w-28 bg-panel border border-line text-ink text-xs rounded-xl px-3 py-2 font-mono focus:outline-none focus:border-indigo-500"
              />
            </div>
            {(selectedSource === 'topcv' || selectedSource === 'jobsgo') && (
              <div>
                <label className="text-[11px] uppercase tracking-wider text-ink-soft font-bold block mb-1">
                  Cloudflare Bypass Engine
                </label>
                <select
                  value={engine}
                  onChange={(e) => setEngine(e.target.value)}
                  className="bg-panel border border-line text-ink text-xs rounded-xl px-3 py-2 font-medium focus:outline-none focus:border-indigo-500"
                >
                  <option value="curl_cffi">curl_cffi (JA3/TLS Chrome 124)</option>
                  <option value="playwright">playwright (Headless Browser Fallback)</option>
                </select>
              </div>
            )}
            <div>
              <label className="flex items-center gap-2 text-xs text-ink-soft cursor-pointer select-none pb-2">
                <input
                  type="checkbox"
                  checked={syncR2}
                  onChange={(e) => setSyncR2(e.target.checked)}
                  className="h-4 w-4 accent-brand-500"
                />
                <span className="font-semibold">Đồng bộ R2</span>
              </label>
              {!syncR2 && (
                <p className="text-[11px] text-state-partial-fg max-w-[220px]">
                  Raw và ledger chỉ lưu trên máy. Nhớ đẩy lên bằng push_raw_to_r2.py.
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center space-x-3">
            {isCrawling ? (
              <button
                onClick={handleStopCrawl}
                className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition shadow-lg shadow-rose-600/30"
              >
                <Square className="w-4 h-4 fill-current" />
                <span>STOP PROCESS</span>
              </button>
            ) : (
              <button
                onClick={handleStartCrawl}
                className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-ink text-xs font-bold transition shadow-lg shadow-indigo-600/30"
              >
                <Play className="w-4 h-4 fill-current" />
                <span>START BATCH CRAWL</span>
              </button>
            )}
          </div>
        </div>
      </div>


 </>
}
