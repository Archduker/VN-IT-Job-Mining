import { Search, ExternalLink, FileCode2 } from 'lucide-react'

import type { useCrawlingState } from './useCrawlingState'
type Props = Pick<ReturnType<typeof useCrawlingState>, 'selectedSource' | 'ledgerItems' | 'ledgerTotal' | 'ledgerCounts' | 'ledgerPage' | 'setLedgerPage' | 'searchLedger' | 'setSearchLedger' | 'statusFilter' | 'setStatusFilter'>
export function LedgerStatusTable({ selectedSource, ledgerItems, ledgerTotal, ledgerCounts, ledgerPage, setLedgerPage, searchLedger, setSearchLedger, statusFilter, setStatusFilter }: Props) {
 return <>
      {/* 7. URL LEDGER MANIFEST (ID & STATUS FOCUS) */}
      <div className="p-5 rounded-2xl bg-panel border border-line space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-ink flex items-center space-x-2">
              <FileCode2 className="w-4 h-4 text-indigo-400" />
              <span>URL Ledger Manifest ({selectedSource.toUpperCase()})</span>
            </h3>
            <p className="text-xs text-ink-soft mt-0.5">
              Total: <span className="font-bold text-ink">{ledgerTotal}</span> URLs
              • Done: <span className="text-emerald-400 font-semibold">{ledgerCounts['DONE'] || ledgerCounts['SCRAPED'] || 0}</span>
              • Pending: <span className="text-amber-400 font-semibold">{ledgerCounts['PENDING'] || ledgerCounts['NEW'] || 0}</span>
              • Failed: <span className="text-rose-400 font-semibold">{ledgerCounts['ERROR'] || ledgerCounts['FAILED'] || 0}</span>
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2 w-full sm:w-auto">
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setLedgerPage(1) }}
              className="bg-panel border border-line text-xs rounded-xl px-3 py-2 text-ink focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Status</option>
              <option value="DONE">DONE (Extracted)</option>
              <option value="PENDING">PENDING (Queued)</option>
              <option value="RECHECK_DUE">RECHECK_DUE (21-Day)</option>
              <option value="CLOSED">CLOSED (Expired)</option>
              <option value="FAILED">FAILED (Error)</option>
            </select>
            <div className="relative flex-1 min-w-0 sm:flex-none">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-ink-soft" />
              <input
                type="text"
                placeholder="Search Job ID, URL Hash..."
                value={searchLedger}
                onChange={(e) => { setSearchLedger(e.target.value); setLedgerPage(1) }}
                className="bg-panel border border-line text-xs rounded-xl pl-9 pr-3 py-2 text-ink placeholder-slate-400 w-full sm:w-56 focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-panel text-ink-soft uppercase text-[10px] tracking-wider border-b border-line">
              <tr>
                <th className="py-2.5 px-3">Job ID</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">HTTP</th>
                <th className="py-2.5 px-3">Content Hash (SHA-256)</th>
                <th className="py-2.5 px-3">Scraped At</th>
                <th className="py-2.5 px-3 text-right">URL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {ledgerItems.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-ink-soft">
                    No URL Ledger records found.
                  </td>
                </tr>
              ) : (
                ledgerItems.map((item, idx) => {
                  const st = String(item.status || 'NEW').toUpperCase()
                  const isDone = st === 'DONE' || st === 'SCRAPED'
                  const isPending = st === 'PENDING' || st === 'NEW'
                  const isDue = st === 'RECHECK_DUE'
                  const isFailed = st === 'FAILED' || st === 'ERROR'

                  return (
                    <tr key={idx} className="hover:bg-ground transition">
                      <td className="py-2.5 px-3 font-mono font-bold text-ink">
                        {item.job_id || item.url_hash?.slice(0, 12) || 'N/A'}
                      </td>
                      <td className="py-2.5 px-3">
                        <span
                          className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                            isDone
                              ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/20'
                              : isPending
                              ? 'bg-amber-500/15 text-amber-300 border border-amber-500/20'
                              : isDue
                              ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/20'
                              : isFailed
                              ? 'bg-rose-500/15 text-rose-300 border border-rose-500/20'
                              : 'bg-ground text-ink'
                          }`}
                        >
                          {st}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-ink-soft">
                        {item.http_status || '—'}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-ink max-w-xs truncate">
                        {item.content_hash ? item.content_hash.slice(0, 24) + '...' : isPending ? '(Awaiting Phase 2)' : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-ink-soft text-[11px]">
                        {item.scraped_at ? item.scraped_at.slice(0, 16).replace('T', ' ') : 'N/A'}
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        {item.url ? (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center space-x-1 text-indigo-400 hover:text-indigo-300 transition"
                          >
                            <span className="text-[10px]">Open</span>
                            <ExternalLink className="w-3 h-3" />
                          </a>
                        ) : (
                          <span className="text-ink-soft text-[10px]">—</span>
                        )}
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-between text-xs text-ink-soft pt-3 border-t border-line">
          <span>Page {ledgerPage}</span>
          <div className="flex space-x-2">
            <button
              disabled={ledgerPage <= 1}
              onClick={() => setLedgerPage((p) => p - 1)}
              className="px-3 py-1 rounded-lg bg-panel border border-line hover:bg-ground disabled:opacity-40 transition"
            >
              Previous
            </button>
            <button
              disabled={ledgerItems.length < 15}
              onClick={() => setLedgerPage((p) => p + 1)}
              className="px-3 py-1 rounded-lg bg-panel border border-line hover:bg-ground disabled:opacity-40 transition"
            >
              Next
            </button>
          </div>
        </div>
      </div>

 </>
}
