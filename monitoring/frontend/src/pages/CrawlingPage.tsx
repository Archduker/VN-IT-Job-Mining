import React, { useEffect, useState, useRef } from 'react'
import axios from 'axios'
import {
  Briefcase,
  Play,
  Square,
  Terminal,
  Radio,
  Search,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
  FileCode2,
  Clock,
  RotateCcw,
  Check,
  XCircle,
  Calendar,
  Cloud,
  UploadCloud,
  RefreshCw,
  Layers,
  Sparkles,
  Activity,
  Cpu,
} from 'lucide-react'
import {
  SourceStatus,
  EnumStatusSummary,
  WeeklyScheduleResponse,
  CloudSyncOverview,
  Phase1DiscoveryItem,
  Phase2DetailItem,
  LedgerItem,
} from '../types'

export const CrawlingPage: React.FC = () => {
  const [sources, setSources] = useState<SourceStatus[]>([])
  const [selectedSource, setSelectedSource] = useState<string>('topcv')
  const [activeSubTab, setActiveSubTab] = useState<
    'ledger' | 'schedules' | 'cloud_sync' | 'crawler' | 'cockpit'
  >('ledger')

  // Crawler Controls state
  const [phase, setPhase] = useState<string>('all')
  const [maxItems, setMaxItems] = useState<number>(10)
  const [engine, setEngine] = useState<string>('curl_cffi')
  const [isCrawling, setIsCrawling] = useState<boolean>(false)

  // Live Logs state
  const [logs, setLogs] = useState<string[]>([])
  const logTerminalRef = useRef<HTMLDivElement>(null)
  const eventSourceRef = useRef<EventSource | null>(null)

  // Ledger state
  const [ledgerItems, setLedgerItems] = useState<LedgerItem[]>([])
  const [ledgerTotal, setLedgerTotal] = useState<number>(0)
  const [ledgerCounts, setLedgerCounts] = useState<Record<string, number>>({})
  const [ledgerPage, setLedgerPage] = useState<number>(1)
  const [searchLedger, setSearchLedger] = useState<string>('')
  const [statusFilter, setStatusFilter] = useState<string>('ALL')

  // Enum Status Breakdown & Weekly Schedule & Cloud Sync state
  const [enumSummary, setEnumSummary] = useState<EnumStatusSummary | null>(null)
  const [weeklySchedule, setWeeklySchedule] = useState<WeeklyScheduleResponse | null>(null)
  const [cloudSync, setCloudSync] = useState<CloudSyncOverview | null>(null)
  const [loadingCloudSync, setLoadingCloudSync] = useState<boolean>(true)
  const [isSyncingSource, setIsSyncingSource] = useState<boolean>(false)
  const [isSyncingAll, setIsSyncingAll] = useState<boolean>(false)
  const [syncFeedback, setSyncFeedback] = useState<string | null>(null)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const fetchSources = async () => {
    try {
      const res = await axios.get<SourceStatus[]>('/api/v1/crawling/sources')
      setSources(res.data)
      const current = res.data.find((s) => s.id === selectedSource)
      if (current) setIsCrawling(current.status === 'running')
    } catch (e) {
      console.error(e)
    }
  }

  const fetchEnumSummary = async () => {
    try {
      const res = await axios.get<EnumStatusSummary>('/api/v1/crawling/enum-summary')
      setEnumSummary(res.data)
    } catch (e) {
      console.error('Failed to fetch enum summary', e)
    }
  }

  const fetchWeeklySchedule = async () => {
    try {
      const res = await axios.get<WeeklyScheduleResponse>('/api/v1/crawling/weekly-schedule')
      setWeeklySchedule(res.data)
    } catch (e) {
      console.error('Failed to fetch weekly schedule', e)
    }
  }

  const fetchCloudSync = async () => {
    try {
      setLoadingCloudSync(true)
      const res = await axios.get<CloudSyncOverview>('/api/v1/crawling/cloud-sync-status')
      setCloudSync(res.data)
    } catch (e) {
      console.error('Failed to fetch cloud sync status', e)
    } finally {
      setLoadingCloudSync(false)
    }
  }

  const fetchLedger = async () => {
    try {
      const res = await axios.get(`/api/v1/crawling/${selectedSource}/ledger`, {
        params: {
          page: ledgerPage,
          page_size: 15,
          search: searchLedger || undefined,
          status: statusFilter !== 'ALL' ? statusFilter : undefined,
        },
      })
      setLedgerItems(res.data.items || [])
      setLedgerTotal(res.data.total || 0)
      setLedgerCounts(res.data.counts || {})
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    fetchSources()
    fetchEnumSummary()
    fetchWeeklySchedule()
    fetchCloudSync()
  }, [])

  useEffect(() => {
    fetchLedger()
  }, [selectedSource, ledgerPage, searchLedger, statusFilter])

  const startLogStream = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }
    const es = new EventSource(`/api/v1/crawling/${selectedSource}/logs/stream`)
    es.onmessage = (event) => {
      setLogs((prev) => [...prev, event.data])
      if (logTerminalRef.current) {
        logTerminalRef.current.scrollTop = logTerminalRef.current.scrollHeight
      }
    }
    es.onerror = () => {
      es.close()
    }
    eventSourceRef.current = es
  }

  const handleStartCrawl = async () => {
    try {
      setIsCrawling(true)
      setLogs([`[Client] Starting crawler for ${selectedSource.toUpperCase()} (Phase: ${phase})...`])
      await axios.post(`/api/v1/crawling/${selectedSource}/trigger`, {
        phase,
        max_items: maxItems,
        engine: selectedSource === 'topcv' || selectedSource === 'jobsgo' ? engine : undefined,
      })
      startLogStream()
      fetchSources()
      fetchEnumSummary()
      fetchWeeklySchedule()
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Crawler start error'
      setErrorMessage(errMsg)
      setIsCrawling(false)
    }
  }

  const handleStopCrawl = async () => {
    try {
      await axios.post(`/api/v1/crawling/${selectedSource}/stop`)
      if (eventSourceRef.current) eventSourceRef.current.close()
      setIsCrawling(false)
      fetchSources()
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Crawler stop error'
      setErrorMessage(errMsg)
    }
  }

  const handleSyncSourceToCloud = async () => {
    try {
      setIsSyncingSource(true)
      setSyncFeedback(null)
      await axios.post(`/api/v1/crawling/${selectedSource}/sync-cloud`)
      setSyncFeedback(`Successfully synced ${selectedSource.toUpperCase()} to Cloudflare R2!`)
      await Promise.all([fetchCloudSync(), fetchSources()])
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Sync error'
      setSyncFeedback(`Sync error for ${selectedSource}: ${errMsg}`)
    } finally {
      setIsSyncingSource(false)
    }
  }

  const handleSyncAllToCloud = async () => {
    try {
      setIsSyncingAll(true)
      setSyncFeedback(null)
      await axios.post('/api/v1/crawling/sync-all-cloud')
      setSyncFeedback('Successfully synced all 8 portals to Cloudflare R2 bucket vn-it-jobs!')
      await Promise.all([fetchCloudSync(), fetchSources()])
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : 'Sync error'
      setSyncFeedback(`Full sync error: ${errMsg}`)
    } finally {
      setIsSyncingAll(false)
    }
  }

  const currentSourceCloud = cloudSync?.sources?.[selectedSource]
  const activeSource = sources.find((s) => s.status === 'running')
  const phase1Data: Phase1DiscoveryItem[] = weeklySchedule?.phase1_discovery || []
  const phase2Data: Phase2DetailItem[] = weeklySchedule?.phase2_detail || weeklySchedule?.days || []

  const renderStatusBadge = (status: string) => {
    const s = status.toUpperCase()
    if (s === 'SUCCESS' || s === 'COMPLETED')
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/20">
          <Check className="w-3 h-3" />
          <span>SUCCESS</span>
        </span>
      )
    if (s === 'RUNNING' || s === 'ACTIVE_QUEUE')
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-blue-500/15 text-blue-400 border border-blue-500/20">
          <RefreshCw className="w-3 h-3 animate-spin" />
          <span>RUNNING</span>
        </span>
      )
    if (s === 'FAILED')
      return (
        <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-rose-500/15 text-rose-400 border border-rose-500/20">
          <XCircle className="w-3 h-3" />
          <span>FAILED</span>
        </span>
      )
    return (
      <span className="inline-flex items-center space-x-1 px-2.5 py-1 rounded-lg text-xs font-bold bg-slate-800 text-slate-400">
        <Clock className="w-3 h-3" />
        <span>SCHEDULED</span>
      </span>
    )
  }

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* LEFT SUB-SIDEBAR (Matching Image 2 left navigation) */}
      <aside className="w-full lg:w-64 shrink-0 space-y-4">
        {/* Stage Header Card */}
        <div className="p-4 rounded-2xl bg-[#131b2e] border border-slate-800 space-y-1">
          <h2 className="text-base font-bold text-white tracking-wide">Jobs</h2>
          <p className="text-xs text-slate-400 leading-snug">
            Find and apply for job opportunities
          </p>
        </div>

        {/* Navigation Buttons (Image 2 style with warm orange active background) */}
        <nav className="space-y-1.5">
          <button
            onClick={() => setActiveSubTab('ledger')}
            className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-xs md:text-sm font-semibold transition-all ${
              activeSubTab === 'ledger'
                ? 'bg-[#f97316] text-white shadow-lg shadow-orange-500/20'
                : 'text-slate-300 hover:text-white hover:bg-slate-900 border border-transparent'
            }`}
          >
            <Briefcase className="w-4 h-4 shrink-0" />
            <span>All Jobs</span>
          </button>

          <button
            onClick={() => setActiveSubTab('schedules')}
            className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-xs md:text-sm font-semibold transition-all ${
              activeSubTab === 'schedules'
                ? 'bg-[#f97316] text-white shadow-lg shadow-orange-500/20'
                : 'text-slate-300 hover:text-white hover:bg-slate-900 border border-transparent'
            }`}
          >
            <Calendar className="w-4 h-4 shrink-0" />
            <span>Weekly Schedules</span>
          </button>

          <button
            onClick={() => setActiveSubTab('cloud_sync')}
            className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-xs md:text-sm font-semibold transition-all ${
              activeSubTab === 'cloud_sync'
                ? 'bg-[#f97316] text-white shadow-lg shadow-orange-500/20'
                : 'text-slate-300 hover:text-white hover:bg-slate-900 border border-transparent'
            }`}
          >
            <Cloud className="w-4 h-4 shrink-0" />
            <span>Cloudflare R2 Sync</span>
          </button>

          <button
            onClick={() => setActiveSubTab('crawler')}
            className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-xs md:text-sm font-semibold transition-all ${
              activeSubTab === 'crawler'
                ? 'bg-[#f97316] text-white shadow-lg shadow-orange-500/20'
                : 'text-slate-300 hover:text-white hover:bg-slate-900 border border-transparent'
            }`}
          >
            <Terminal className="w-4 h-4 shrink-0" />
            <span>Live Crawler & Logs</span>
          </button>

          <button
            onClick={() => setActiveSubTab('cockpit')}
            className={`w-full flex items-center space-x-3 px-3.5 py-2.5 rounded-xl text-xs md:text-sm font-semibold transition-all ${
              activeSubTab === 'cockpit'
                ? 'bg-[#f97316] text-white shadow-lg shadow-orange-500/20'
                : 'text-slate-300 hover:text-white hover:bg-slate-900 border border-transparent'
            }`}
          >
            <Activity className="w-4 h-4 shrink-0" />
            <span>Dual Status Cockpit</span>
          </button>
        </nav>

        {/* Portal Picker Pill */}
        <div className="p-3 rounded-2xl bg-[#131b2e] border border-slate-800 space-y-2">
          <label className="text-[11px] font-bold text-slate-400 uppercase tracking-wider block">
            Focal Portal Target
          </label>
          <div className="grid grid-cols-2 gap-1.5">
            {sources.map((s) => (
              <button
                key={s.id}
                onClick={() => {
                  setSelectedSource(s.id)
                  setLedgerPage(1)
                }}
                className={`px-2 py-1.5 rounded-lg text-[11px] font-semibold transition truncate text-left ${
                  selectedSource === s.id
                    ? 'bg-orange-500/20 text-orange-400 border border-orange-500/30'
                    : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                }`}
              >
                {s.name}
              </button>
            ))}
          </div>
        </div>
      </aside>

      {/* RIGHT MAIN CONTENT AREA (Matching Image 2) */}
      <main className="flex-1 min-w-0 space-y-5">
        {/* Header (Exact Title & Subtitle from Image 2) */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white tracking-tight">
              Find Your Dream Job
            </h1>
            <p className="text-xs md:text-sm text-slate-400 mt-0.5">
              Browse available positions and apply with your CV
            </p>
          </div>

          <button
            onClick={() => {
              fetchSources()
              fetchEnumSummary()
              fetchWeeklySchedule()
              fetchCloudSync()
              fetchLedger()
            }}
            className="p-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition shadow-sm"
            title="Refresh Ledger"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {/* Top Search & Filter Bar (Matching Image 2 search bar + dropdown) */}
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="w-4 h-4 absolute left-3.5 top-3 text-slate-500" />
            <input
              type="text"
              placeholder="Search jobs by title, description..."
              value={searchLedger}
              onChange={(e) => {
                setSearchLedger(e.target.value)
                setLedgerPage(1)
              }}
              className="w-full bg-[#131b2e] border border-slate-800 text-xs md:text-sm rounded-xl pl-10 pr-4 py-2.5 text-white placeholder-slate-500 focus:outline-none focus:border-orange-500 transition"
            />
          </div>

          <div className="flex items-center space-x-2 w-full sm:w-auto">
            <select
              value={selectedSource}
              onChange={(e) => {
                setSelectedSource(e.target.value)
                setLedgerPage(1)
              }}
              className="bg-[#131b2e] border border-slate-800 text-xs md:text-sm rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-orange-500"
            >
              {sources.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>

            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setLedgerPage(1)
              }}
              className="bg-[#131b2e] border border-slate-800 text-xs md:text-sm rounded-xl px-3.5 py-2.5 text-white focus:outline-none focus:border-orange-500"
            >
              <option value="ALL">All Types</option>
              <option value="DONE">DONE (Extracted)</option>
              <option value="PENDING">PENDING (Queued)</option>
              <option value="RECHECK_DUE">RECHECK_DUE</option>
              <option value="CLOSED">CLOSED</option>
              <option value="FAILED">FAILED</option>
            </select>
          </div>
        </div>

        {/* SUBTAB 1: ALL JOBS / URL LEDGER (Matching Image 2 content card) */}
        {activeSubTab === 'ledger' && (
          <div className="p-6 rounded-2xl bg-[#131b2e] border border-slate-800 shadow-sm min-h-[400px] flex flex-col justify-between">
            {ledgerItems.length === 0 ? (
              /* Empty state matching Image 2 suitcase icon */
              <div className="flex-1 flex flex-col items-center justify-center py-20 text-center space-y-2">
                <div className="w-14 h-14 rounded-2xl bg-slate-900 border border-slate-800 flex items-center justify-center text-slate-500">
                  <Briefcase className="w-7 h-7" />
                </div>
                <h3 className="text-base font-bold text-white mt-2">No jobs found</h3>
                <p className="text-xs text-slate-400">
                  Try adjusting your search or filters
                </p>
              </div>
            ) : (
              /* Ledger Records Table */
              <div className="space-y-4">
                <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800 pb-3">
                  <span>
                    Showing {ledgerItems.length} of {ledgerTotal} jobs in{' '}
                    <span className="font-bold text-white uppercase">{selectedSource}</span>
                  </span>
                  <span>Page {ledgerPage}</span>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                      <tr>
                        <th className="py-2.5 px-3">Job ID</th>
                        <th className="py-2.5 px-3">Job Title / Company</th>
                        <th className="py-2.5 px-3">Status</th>
                        <th className="py-2.5 px-3">HTTP</th>
                        <th className="py-2.5 px-3">Content Hash</th>
                        <th className="py-2.5 px-3">Scraped At</th>
                        <th className="py-2.5 px-3 text-right">URL</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-800/60">
                      {ledgerItems.map((item, idx) => {
                        const st = String(item.status || 'NEW').toUpperCase()
                        const isDone = st === 'DONE' || st === 'SCRAPED'
                        const isPending = st === 'PENDING' || st === 'NEW'
                        const isDue = st === 'RECHECK_DUE'
                        const isFailed = st === 'FAILED' || st === 'ERROR'

                        return (
                          <tr key={idx} className="hover:bg-slate-900/60 transition">
                            <td className="py-3 px-3 font-mono font-bold text-white">
                              {item.job_id || item.url_hash?.slice(0, 12) || 'N/A'}
                            </td>
                            <td className="py-3 px-3 text-slate-300 font-medium">
                              <div>{item.job_title || 'Software Engineer / IT Position'}</div>
                              <div className="text-[10px] text-slate-400">{item.company || selectedSource.toUpperCase()}</div>
                            </td>
                            <td className="py-3 px-3">
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                                  isDone
                                    ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/20'
                                    : isPending
                                    ? 'bg-orange-500/15 text-orange-300 border border-orange-500/20'
                                    : isDue
                                    ? 'bg-indigo-500/15 text-indigo-300 border border-indigo-500/20'
                                    : isFailed
                                    ? 'bg-rose-500/15 text-rose-300 border border-rose-500/20'
                                    : 'bg-slate-800 text-slate-300'
                                }`}
                              >
                                {st}
                              </span>
                            </td>
                            <td className="py-3 px-3 font-mono text-slate-400">
                              {item.http_status || '200'}
                            </td>
                            <td className="py-3 px-3 font-mono text-[11px] text-slate-400 max-w-xs truncate">
                              {item.content_hash ? item.content_hash.slice(0, 20) + '...' : isPending ? '(Awaiting Phase 2)' : '—'}
                            </td>
                            <td className="py-3 px-3 text-slate-400 text-[11px]">
                              {item.scraped_at ? item.scraped_at.slice(0, 16).replace('T', ' ') : 'N/A'}
                            </td>
                            <td className="py-3 px-3 text-right">
                              {item.url ? (
                                <a
                                  href={item.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex items-center space-x-1 text-orange-400 hover:text-orange-300 transition"
                                >
                                  <span className="text-[10px]">Open</span>
                                  <ExternalLink className="w-3 h-3" />
                                </a>
                              ) : (
                                <span className="text-slate-500 text-[10px]">—</span>
                              )}
                            </td>
                          </tr>
                        )
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                <div className="flex items-center justify-between pt-4 border-t border-slate-800">
                  <button
                    disabled={ledgerPage <= 1}
                    onClick={() => setLedgerPage((p) => Math.max(1, p - 1))}
                    className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-semibold text-slate-300 disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <span className="text-xs text-slate-400">Page {ledgerPage}</span>
                  <button
                    disabled={ledgerItems.length < 15}
                    onClick={() => setLedgerPage((p) => p + 1)}
                    className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-xs font-semibold text-slate-300 disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* SUBTAB 2: TWO-PHASE WEEKLY SCHEDULES */}
        {activeSubTab === 'schedules' && (
          <div className="space-y-6">
            {/* Phase 1 Discovery */}
            <div className="p-5 rounded-2xl bg-[#131b2e] border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                    <Calendar className="w-4 h-4 text-orange-400" />
                    <span>Phase 1 Discovery: Weekly URL Extraction (05:00 AM Daily)</span>
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Scans pagination catalog pages and updates URL Ledgers with zero redundant downloads.
                  </p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3">Day of Week</th>
                      <th className="py-2.5 px-3">Target Portal</th>
                      <th className="py-2.5 px-3">Airflow DAG</th>
                      <th className="py-2.5 px-3">Scheduled Time</th>
                      <th className="py-2.5 px-3 text-right">Quota Pages</th>
                      <th className="py-2.5 px-3 text-right">URLs Discovered</th>
                      <th className="py-2.5 px-3 text-center">Execution Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {phase1Data.map((d) => (
                      <tr key={d.dag_id} className="hover:bg-slate-900/60 transition">
                        <td className="py-3 px-3 font-bold text-white">{d.day_of_week}</td>
                        <td className="py-3 px-3 font-semibold text-orange-400">{d.focal_source.toUpperCase()}</td>
                        <td className="py-3 px-3 font-mono text-slate-300">{d.dag_id}</td>
                        <td className="py-3 px-3 text-slate-400">{d.scheduled_time}</td>
                        <td className="py-3 px-3 text-right font-mono text-slate-300">{d.quota_pages} pgs</td>
                        <td className="py-3 px-3 text-right font-mono font-bold text-white">{d.total_discovered} URLs</td>
                        <td className="py-3 px-3 text-center">{renderStatusBadge(d.status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Phase 2 Detail */}
            <div className="p-5 rounded-2xl bg-[#131b2e] border border-slate-800 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                    <Clock className="w-4 h-4 text-emerald-400" />
                    <span>Phase 2 Detail Extraction: Payload Scraping (20:00 PM Daily)</span>
                  </h3>
                  <p className="text-xs text-slate-400 mt-0.5">
                    Extracts full JD descriptions, salary, requirements, and uploads raw JSON directly to Cloudflare R2.
                  </p>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                    <tr>
                      <th className="py-2.5 px-3">Day of Week</th>
                      <th className="py-2.5 px-3">Focal Source</th>
                      <th className="py-2.5 px-3">Airflow DAG</th>
                      <th className="py-2.5 px-3">Scheduled Time</th>
                      <th className="py-2.5 px-3 text-right">Projected Quota</th>
                      <th className="py-2.5 px-3 text-right">Actual Crawled</th>
                      <th className="py-2.5 px-3 text-right">Pending</th>
                      <th className="py-2.5 px-3 text-center">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60">
                    {phase2Data.map((d) => (
                      <tr key={d.dag_id} className="hover:bg-slate-900/60 transition">
                        <td className="py-3 px-3 font-bold text-white">{d.day_of_week}</td>
                        <td className="py-3 px-3 font-semibold text-emerald-400">{d.focal_source.toUpperCase()}</td>
                        <td className="py-3 px-3 font-mono text-slate-300">{d.dag_id}</td>
                        <td className="py-3 px-3 text-slate-400">{d.scheduled_time}</td>
                        <td className="py-3 px-3 text-right font-mono text-slate-300">{d.projected_quota}</td>
                        <td className="py-3 px-3 text-right font-mono font-bold text-white">{d.actual_crawled}</td>
                        <td className="py-3 px-3 text-right font-mono text-amber-400">{d.uncrawled_pending}</td>
                        <td className="py-3 px-3 text-center">{renderStatusBadge(d.status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 3: CLOUDFLARE R2 SYNC AUDIT */}
        {activeSubTab === 'cloud_sync' && (
          <div className="p-5 rounded-2xl bg-[#131b2e] border border-slate-800 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                  <Cloud className="w-4 h-4 text-orange-400" />
                  <span>Cloudflare R2 Object Storage Lakehouse Sync</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Synchronizes raw collected payloads to R2 bucket <code className="text-white">vn-it-jobs</code>.
                </p>
              </div>

              <div className="flex items-center space-x-2">
                <button
                  onClick={handleSyncSourceToCloud}
                  disabled={isSyncingSource || isSyncingAll}
                  className="px-3.5 py-2 rounded-xl bg-orange-600 hover:bg-orange-500 text-white text-xs font-semibold transition flex items-center space-x-1.5"
                >
                  {isSyncingSource ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <UploadCloud className="w-3.5 h-3.5" />}
                  <span>Sync {selectedSource.toUpperCase()}</span>
                </button>
                <button
                  onClick={handleSyncAllToCloud}
                  disabled={isSyncingSource || isSyncingAll}
                  className="px-3.5 py-2 rounded-xl bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-200 text-xs font-semibold transition flex items-center space-x-1.5"
                >
                  {isSyncingAll ? <RefreshCw className="w-3.5 h-3.5 animate-spin text-orange-400" /> : <Sparkles className="w-3.5 h-3.5 text-amber-400" />}
                  <span>Sync All 8 Portals</span>
                </button>
              </div>
            </div>

            {syncFeedback && (
              <div className="p-3 rounded-xl bg-emerald-950/40 border border-emerald-500/30 text-emerald-300 text-xs">
                {syncFeedback}
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Source Portal</th>
                    <th className="py-2.5 px-3 text-right">Local Files</th>
                    <th className="py-2.5 px-3 text-right">Cloud Objects</th>
                    <th className="py-2.5 px-3 text-right">Missing in R2</th>
                    <th className="py-2.5 px-3 text-right">Sync Rate</th>
                    <th className="py-2.5 px-3 text-center">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {cloudSync &&
                    Object.entries(cloudSync.sources || {}).map(([src, diff]) => (
                      <tr key={src} className="hover:bg-slate-900/60 transition">
                        <td className="py-3 px-3 font-bold text-white uppercase">{src}</td>
                        <td className="py-3 px-3 text-right font-mono text-slate-300">{diff.local_raw_count}</td>
                        <td className="py-3 px-3 text-right font-mono text-white font-semibold">{diff.cloud_raw_count}</td>
                        <td className="py-3 px-3 text-right font-mono text-amber-400">
                          {Math.max(0, diff.local_raw_count - diff.cloud_raw_count)}
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-emerald-400 font-bold">{diff.sync_pct}%</td>
                        <td className="py-3 px-3 text-center">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              diff.status === 'SYNCED'
                                ? 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/20'
                                : 'bg-amber-500/15 text-amber-300 border border-amber-500/20'
                            }`}
                          >
                            {diff.status}
                          </span>
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* SUBTAB 4: LIVE CRAWLER CONTROLS & LOGS */}
        {activeSubTab === 'crawler' && (
          <div className="space-y-6">
            <div className="p-5 rounded-2xl bg-[#131b2e] border border-slate-800 space-y-4">
              <h3 className="text-sm font-bold text-white flex items-center space-x-2">
                <Terminal className="w-4 h-4 text-orange-400" />
                <span>Crawler Trigger Controls ({selectedSource.toUpperCase()})</span>
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">Phase</label>
                  <select
                    value={phase}
                    onChange={(e) => setPhase(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 text-xs rounded-xl px-3 py-2 text-white"
                  >
                    <option value="all">All Phases (Discover + Detail)</option>
                    <option value="discover">Phase 1: Discover URLs Only</option>
                    <option value="detail">Phase 2: Extract Postings Only</option>
                  </select>
                </div>

                <div>
                  <label className="text-xs text-slate-400 mb-1 block">Max Items</label>
                  <input
                    type="number"
                    value={maxItems}
                    onChange={(e) => setMaxItems(Number(e.target.value))}
                    min={1}
                    max={100}
                    className="w-full bg-slate-900 border border-slate-800 text-xs rounded-xl px-3 py-2 text-white"
                  />
                </div>

                <div>
                  <label className="text-xs text-slate-400 mb-1 block">Engine</label>
                  <select
                    value={engine}
                    onChange={(e) => setEngine(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 text-xs rounded-xl px-3 py-2 text-white"
                  >
                    <option value="curl_cffi">curl_cffi (Fast Anti-Bot)</option>
                    <option value="playwright">Playwright (Full Browser)</option>
                  </select>
                </div>
              </div>

              <div className="flex items-center space-x-3 pt-2">
                <button
                  onClick={handleStartCrawl}
                  disabled={isCrawling}
                  className="px-4 py-2 rounded-xl bg-orange-600 hover:bg-orange-500 text-white text-xs font-semibold transition disabled:opacity-40 flex items-center space-x-1.5"
                >
                  <Play className="w-4 h-4" />
                  <span>Start Crawler</span>
                </button>
                <button
                  onClick={handleStopCrawl}
                  disabled={!isCrawling}
                  className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold transition disabled:opacity-40 flex items-center space-x-1.5"
                >
                  <Square className="w-4 h-4" />
                  <span>Stop Crawler</span>
                </button>
              </div>
            </div>

            {/* Terminal View */}
            <div className="p-5 rounded-2xl bg-[#0b1120] border border-slate-800 space-y-3">
              <div className="flex items-center justify-between text-xs text-slate-400 border-b border-slate-800/80 pb-2">
                <span className="font-mono text-orange-400 font-bold">LIVE STDOUT STREAM</span>
                <span className="text-[11px]">{logs.length} log lines</span>
              </div>
              <div
                ref={logTerminalRef}
                className="h-64 overflow-y-auto font-mono text-[11px] space-y-1 text-slate-300 pr-2"
              >
                {logs.length === 0 ? (
                  <span className="text-slate-600 italic">No crawler output. Trigger a crawl to stream real-time logs.</span>
                ) : (
                  logs.map((log, i) => (
                    <div key={i} className="leading-relaxed">
                      {log}
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* SUBTAB 5: DUAL COCKPIT & ENUM STATUS */}
        {activeSubTab === 'cockpit' && (
          <div className="space-y-6">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Live Crawler Status */}
              <div className="p-5 rounded-2xl bg-[#131b2e] border border-slate-800 space-y-3">
                <div className="flex items-center space-x-2 text-xs font-bold text-slate-400 uppercase tracking-wider">
                  <Activity className="w-4 h-4 text-orange-400" />
                  <span>Live Crawler Runtime Status</span>
                </div>
                <div className="flex items-center space-x-3">
                  <span
                    className={`w-4 h-4 rounded-full shrink-0 ${
                      activeSource ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'
                    }`}
                  />
                  <span className={`text-2xl font-extrabold ${activeSource ? 'text-emerald-400' : 'text-slate-400'}`}>
                    {activeSource ? 'ACTIVE' : 'IDLE — READY'}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div>
                    <span className="text-slate-400">Active Source:</span>
                    <span className="ml-2 text-white font-bold">{activeSource ? activeSource.name : 'None'}</span>
                  </div>
                  <div>
                    <span className="text-slate-400">Engine:</span>
                    <span className="ml-2 text-orange-300 font-mono">{activeSource?.engine || 'curl_cffi'}</span>
                  </div>
                </div>
              </div>

              {/* Cloudflare R2 Metrics */}
              <div className="p-5 rounded-2xl bg-[#131b2e] border border-slate-800 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center space-x-2 text-xs font-bold text-slate-400 uppercase tracking-wider">
                    <Cloud className="w-4 h-4 text-orange-400" />
                    <span>Cloudflare R2 Bucket Telemetry</span>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-bold">
                    ONLINE ({cloudSync?.latency_ms || 24}ms)
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <p className="text-xs text-slate-400 mb-1">Total Cloud Objects</p>
                    <p className="text-2xl font-extrabold font-mono text-white">
                      {cloudSync?.total_cloud_raw?.toLocaleString() ?? '—'}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-slate-400 mb-1">Overall Sync Health</p>
                    <p className="text-2xl font-extrabold font-mono text-emerald-400">
                      {cloudSync?.overall_sync_pct ?? 0}%
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Enum Summary */}
            {enumSummary && (
              <div className="p-5 rounded-2xl bg-[#131b2e] border border-slate-800 space-y-4">
                <h3 className="text-sm font-bold text-white">5-Status URL Lifecycle Distribution</h3>
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-center">
                    <span className="text-xs text-slate-400">PENDING</span>
                    <p className="text-xl font-bold text-amber-400 mt-1">{enumSummary.pending.count}</p>
                    <span className="text-[10px] text-slate-500">{enumSummary.pending.pct}%</span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-center">
                    <span className="text-xs text-slate-400">DONE</span>
                    <p className="text-xl font-bold text-emerald-400 mt-1">{enumSummary.done.count}</p>
                    <span className="text-[10px] text-slate-500">{enumSummary.done.pct}%</span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-center">
                    <span className="text-xs text-slate-400">RECHECK_DUE</span>
                    <p className="text-xl font-bold text-indigo-400 mt-1">{enumSummary.recheck_due.count}</p>
                    <span className="text-[10px] text-slate-500">{enumSummary.recheck_due.pct}%</span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-center">
                    <span className="text-xs text-slate-400">CLOSED</span>
                    <p className="text-xl font-bold text-slate-400 mt-1">{enumSummary.closed.count}</p>
                    <span className="text-[10px] text-slate-500">{enumSummary.closed.pct}%</span>
                  </div>
                  <div className="p-3 rounded-xl bg-slate-900 border border-slate-800 text-center">
                    <span className="text-xs text-slate-400">FAILED</span>
                    <p className="text-xl font-bold text-rose-400 mt-1">{enumSummary.failed.count}</p>
                    <span className="text-[10px] text-slate-500">{enumSummary.failed.pct}%</span>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  )
}
