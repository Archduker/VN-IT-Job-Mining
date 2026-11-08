import { Terminal } from 'lucide-react'

import type { useCrawlingState } from './useCrawlingState'
type Props = Pick<ReturnType<typeof useCrawlingState>, 'logTerminalRef' | 'isCrawling' | 'logs' | 'setLogs'>
export function RealtimeLogStream({ logTerminalRef, isCrawling, logs, setLogs }: Props) {
 return <>
      {/* Live Terminal Stream */}
      <div className="p-4 rounded-2xl bg-panel border border-line space-y-2">
        <div className="flex items-center justify-between border-b border-line pb-2">
          <div className="flex items-center space-x-2 text-xs font-bold text-ink">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <span>Live Console Stream (Server-Sent Events)</span>
            {isCrawling && (
              <span className="flex items-center space-x-1 text-[11px] font-semibold text-emerald-400 ml-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Streaming...</span>
              </span>
            )}
          </div>
          <button onClick={() => setLogs([])} className="text-xs text-ink-soft hover:text-ink transition">
            Clear
          </button>
        </div>
        <div
          ref={logTerminalRef}
          className="h-48 overflow-y-auto font-mono text-xs text-ink space-y-1 p-2 bg-panel rounded-xl select-text"
        >
          {logs.length === 0 ? (
            <div className="text-ink-soft italic">
              No logs yet. Click &quot;START BATCH CRAWL&quot; to stream execution logs from CLI run.py...
            </div>
          ) : (
            logs.map((line, idx) => (
              <div key={idx} className="whitespace-pre-wrap leading-tight">{line}</div>
            ))
          )}
        </div>
      </div>


 </>
}
