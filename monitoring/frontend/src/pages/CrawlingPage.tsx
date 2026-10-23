import React, { useEffect, useState, useRef } from 'react'
import axios from 'axios'
import {
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
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-5 rounded-2xl bg-slate-900 border border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <Radio className="w-4 h-4 text-indigo-400" />
            <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">
              Operations Module • Crawling Operations
            </span>
          </div>
          <h2 className="text-xl font-bold text-white mt-1">
            Batch Crawler Orchestrator & URL Ledger ({selectedSource.toUpperCase()})
          </h2>
          <p className="text-xs text-slate-400">
            Two-Phase Decoupled Crawler Architecture with Enum Lifecycle Tracking and Cloudflare R2 Sync.
          </p>
        </div>
      </div>

      {/* 1 & 2: DUAL STATUS COCKPIT */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 1. Live Crawler Runtime Status */}
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
          <div className="flex items-center space-x-2 text-xs font-bold text-slate-400 uppercase tracking-wider">
            <Activity className="w-4 h-4 text-indigo-400" />
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
              <span className="ml-2 text-indigo-300 font-mono">{activeSource?.engine || 'N/A'}</span>
            </div>
          </div>
        </div>

        {/* 2. Cloudflare R2 Lakehouse Metrics */}
        <div className="p-5 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/40 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-xs font-bold text-slate-400 uppercase tracking-wider">
              <Cloud className="w-4 h-4 text-indigo-400" />
              <span>Cloudflare R2 Lakehouse Metrics</span>
            </div>
            <span
              className={`text-[10px] px-2 py-0.5 rounded-full font-bold ${
                loadingCloudSync
                  ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
                  : cloudSync?.connected
                  ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                  : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
              }`}
            >
              {loadingCloudSync ? (
                <span className="inline-flex items-center space-x-1">
                  <RefreshCw className="w-2.5 h-2.5 animate-spin" />
                  <span>SCANNING R2...</span>
                </span>
              ) : cloudSync?.connected ? (
                `ONLINE (${cloudSync.latency_ms}ms)`
              ) : (
                'DISCONNECTED'
              )}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-xs text-slate-400 mb-1">Total Stored Objects</p>
              <p className="text-3xl font-extrabold font-mono text-white">{cloudSync?.total_cloud_raw?.toLocaleString() ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">Sync Health</p>
              <p className="text-3xl font-extrabold font-mono text-emerald-400">{cloudSync?.overall_sync_pct ?? 0}%</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleSyncSourceToCloud}
              disabled={isSyncingSource || isSyncingAll}
              className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-300 text-xs font-semibold transition"
            >
              {isSyncingSource ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <UploadCloud className="w-3.5 h-3.5" />}
              <span>Sync {selectedSource.toUpperCase()}</span>
            </button>
            <button
              onClick={handleSyncAllToCloud}
              disabled={isSyncingSource || isSyncingAll}
              className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-200 text-xs font-semibold transition"
            >
              {isSyncingAll ? <RefreshCw className="w-3.5 h-3.5 animate-spin text-indigo-400" /> : <Sparkles className="w-3.5 h-3.5 text-amber-400" />}
              <span>Sync All 8 Portals</span>
            </button>
          </div>
        </div>
      </div>

      {/* Feedback banners */}
      {syncFeedback && (
        <div className="p-3.5 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs flex items-center justify-between">
          <span>{syncFeedback}</span>
          <button onClick={() => setSyncFeedback(null)} className="text-slate-400 hover:text-white">✕</button>
        </div>
      )}
      {errorMessage && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)} className="text-slate-400 hover:text-white ml-2">✕</button>
        </div>
      )}

      {/* 3.1: PHASE 1 — DAILY URL DISCOVERY SCHEDULE */}
      {phase1Data.length > 0 && (
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="border-b border-slate-800 pb-3">
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <Layers className="w-4 h-4 text-indigo-400" />
              <span>3.1 Phase 1: Daily URL Discovery Schedule (05:00 AM UTC+7)</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Sweep catalog pages across all 8 portals and ingest new URLs into Ledger with PENDING status.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Day</th>
                  <th className="py-2.5 px-3">Portal</th>
                  <th className="py-2.5 px-3">Airflow DAG ID</th>
                  <th className="py-2.5 px-3">Task ID</th>
                  <th className="py-2.5 px-3">Run Time</th>
                  <th className="py-2.5 px-3">Pages Quota</th>
                  <th className="py-2.5 px-3">Total URLs Discovered</th>
                  <th className="py-2.5 px-3 text-right">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {phase1Data.map((d) => (
                  <tr key={`p1-${d.day_index}`} className="hover:bg-slate-800/40 transition">
                    <td className="py-2.5 px-3 font-bold text-white whitespace-nowrap">{d.day_of_week}</td>
                    <td className="py-2.5 px-3 font-semibold text-indigo-300 uppercase">{d.focal_source}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-slate-300">{d.dag_id}</td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-slate-300">{d.task_id}</td>
                    <td className="py-2.5 px-3 text-slate-300">{d.scheduled_time}</td>
                    <td className="py-2.5 px-3 text-white font-mono font-bold">{d.quota_pages} Pages</td>
                    <td className="py-2.5 px-3 text-emerald-400 font-mono font-bold">{d.total_discovered.toLocaleString()} URLs</td>
                    <td className="py-2.5 px-3 text-right">{renderStatusBadge(d.status)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 3.2: PHASE 2 — ADAPTIVE DETAIL EXTRACTION SCHEDULE */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <Calendar className="w-4 h-4 text-indigo-400" />
              <span>3.2 Phase 2: Adaptive Detail Extraction Schedule (20:00 PM UTC+7)</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Quota <strong className="text-indigo-300 font-mono">{weeklySchedule?.total_projected_weekly?.toLocaleString() || '2,050'}</strong> items/week
              vs Crawled <strong className="text-emerald-400 font-mono">{weeklySchedule?.total_actual_crawled?.toLocaleString() || 0}</strong> items
              • Pending <strong className="text-amber-400 font-mono">{weeklySchedule?.total_uncrawled_pending?.toLocaleString() || 0}</strong> items
              ({weeklySchedule?.overall_progress_pct || 0}% target)
            </p>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Day</th>
                <th className="py-2.5 px-3">Portal</th>
                <th className="py-2.5 px-3">Detail DAG ID</th>
                <th className="py-2.5 px-3">Run Time</th>
                <th className="py-2.5 px-3">Quota</th>
                <th className="py-2.5 px-3">Crawled</th>
                <th className="py-2.5 px-3">Pending</th>
                <th className="py-2.5 px-3">Progress %</th>
                <th className="py-2.5 px-3">Engine</th>
                <th className="py-2.5 px-3 text-right">Airflow State</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {phase2Data.map((day) => (
                <tr key={`p2-${day.day_index}`} className="hover:bg-slate-800/40 transition">
                  <td className="py-2.5 px-3 font-bold text-white whitespace-nowrap">{day.day_of_week}</td>
                  <td className="py-2.5 px-3 font-semibold text-indigo-300 uppercase">{day.focal_source}</td>
                  <td className="py-2.5 px-3 font-mono text-[11px] text-slate-300">{day.dag_id}</td>
                  <td className="py-2.5 px-3 text-slate-300">{day.scheduled_time}</td>
                  <td className="py-2.5 px-3 font-mono text-white font-bold">{day.projected_quota} items</td>
                  <td className="py-2.5 px-3 font-mono text-emerald-400 font-bold">{day.actual_crawled.toLocaleString()} items</td>
                  <td className="py-2.5 px-3 font-mono font-bold">
                    <span className={day.uncrawled_pending > 0 ? 'text-amber-400' : 'text-slate-500'}>
                      {day.uncrawled_pending.toLocaleString()} items
                    </span>
                  </td>
                  <td className="py-2.5 px-3 min-w-[120px]">
                    <div className="flex items-center space-x-2">
                      <div className="flex-1 h-2 rounded-full bg-slate-950 overflow-hidden border border-slate-800">
                        <div
                          style={{ width: `${Math.min(100, day.progress_pct)}%` }}
                          className={`h-full rounded-full ${
                            day.progress_pct >= 100
                              ? 'bg-emerald-500'
                              : day.progress_pct > 50
                              ? 'bg-indigo-500'
                              : 'bg-amber-500'
                          }`}
                        />
                      </div>
                      <span className="font-mono text-[10px] text-slate-300">{day.progress_pct}%</span>
                    </div>
                  </td>
                  <td className="py-2.5 px-3 text-[11px] text-slate-300">{day.engine}</td>
                  <td className="py-2.5 px-3 text-right">{renderStatusBadge(day.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 4. DATA SOURCE SELECTION MATRIX (8 PORTALS) */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center space-x-2">
          <Cpu className="w-4 h-4 text-indigo-400" />
          <span>Data Source Selection Matrix (8 Portals)</span>
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-8 gap-2">
          {sources.map((s) => {
            const isSelected = selectedSource === s.id
            const isRunning = s.status === 'running'
            const cloudCount = cloudSync?.sources?.[s.id]?.cloud_raw_count ?? s.total_raw
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
                    : 'bg-slate-950/60 border-slate-800 hover:border-slate-600 hover:bg-slate-950'
                }`}
              >
                <div className="flex items-center justify-center space-x-1.5 mb-1">
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${
                      isRunning ? 'bg-emerald-400 animate-pulse' : 'bg-slate-600'
                    }`}
                  />
                  <span className="text-xs font-bold uppercase text-white truncate">{s.name}</span>
                </div>
                <p className="text-lg font-extrabold font-mono text-indigo-300">{cloudCount.toLocaleString()}</p>
                <p className="text-[10px] text-slate-400">in R2</p>
              </button>
            )
          })}
        </div>
      </div>

      {/* 5. BIG KPI HERO CARDS */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 text-center">
          <p className="text-xs text-slate-400 uppercase tracking-wider font-bold mb-2">Total URLs in Ledger</p>
          <p className="text-4xl font-extrabold font-mono text-white">{enumSummary?.total?.toLocaleString() || '—'}</p>
          <p className="text-xs text-slate-400 mt-1">Discovered Catalog</p>
        </div>
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 text-center">
          <p className="text-xs text-slate-400 uppercase tracking-wider font-bold mb-2">Raw Objects in R2</p>
          <p className="text-4xl font-extrabold font-mono text-indigo-300">{cloudSync?.total_cloud_raw?.toLocaleString() ?? '—'}</p>
          <p className="text-xs text-slate-400 mt-1">Stored in Bucket</p>
        </div>
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 text-center">
          <p className="text-xs text-slate-400 uppercase tracking-wider font-bold mb-2">Pending Extraction</p>
          <p className="text-4xl font-extrabold font-mono text-amber-400">{weeklySchedule?.total_uncrawled_pending?.toLocaleString() ?? enumSummary?.pending?.count?.toLocaleString() ?? '—'}</p>
          <p className="text-xs text-slate-400 mt-1">Queued for Phase 2</p>
        </div>
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 text-center">
          <p className="text-xs text-slate-400 uppercase tracking-wider font-bold mb-2">Weekly Schedule Quota</p>
          <p className="text-4xl font-extrabold font-mono text-violet-400">{weeklySchedule?.total_projected_weekly?.toLocaleString() ?? '—'}</p>
          <p className="text-xs text-slate-400 mt-1">Projected Target</p>
        </div>
      </div>

      {/* 6. 5-STATE ENUM LIFECYCLE BREAKDOWN */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <Layers className="w-4 h-4 text-indigo-400" />
              <span>5-State Enum Lifecycle Breakdown</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Total <span className="text-white font-bold font-mono">{enumSummary?.total?.toLocaleString() || '—'}</span> URLs across the entire URL Ledger system. Click a card to filter.
            </p>
          </div>
          {statusFilter !== 'ALL' && (
            <button
              onClick={() => setStatusFilter('ALL')}
              className="text-xs text-indigo-400 hover:underline flex items-center space-x-1 font-semibold"
            >
              <span>Clear filter (Filtering: {statusFilter})</span>
            </button>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {[
            { key: 'PENDING', label: 'PENDING', data: enumSummary?.pending, icon: <Clock className="w-5 h-5 text-amber-400" />, color: 'amber', desc: 'Queued for Phase 2' },
            { key: 'DONE', label: 'DONE', data: enumSummary?.done, icon: <CheckCircle2 className="w-5 h-5 text-emerald-400" />, color: 'emerald', desc: 'Raw As-Is Extracted & Hashed' },
            { key: 'RECHECK_DUE', label: 'RECHECK_DUE', data: enumSummary?.recheck_due, icon: <RotateCcw className="w-5 h-5 text-indigo-400" />, color: 'indigo', desc: 'Re-crawl due (≥21 days)' },
            { key: 'CLOSED', label: 'CLOSED', data: enumSummary?.closed, icon: <XCircle className="w-5 h-5 text-slate-400" />, color: 'slate', desc: 'Expired / 404 / Removed' },
            { key: 'FAILED', label: 'FAILED', data: enumSummary?.failed, icon: <AlertCircle className="w-5 h-5 text-rose-400" />, color: 'rose', desc: 'Network / Bot blocked' },
          ].map((st) => (
            <div
              key={st.key}
              onClick={() => setStatusFilter(statusFilter === st.key ? 'ALL' : st.key)}
              className={`p-4 rounded-xl cursor-pointer border transition-all ${
                statusFilter === st.key
                  ? `bg-${st.color}-500/20 border-${st.color}-500 ring-2 ring-${st.color}-500/40`
                  : `bg-slate-950/60 border-slate-800 hover:border-${st.color}-500/50 hover:bg-slate-950`
              }`}
            >
              <div className="flex items-center justify-between mb-2">
                <span className={`text-xs font-bold uppercase tracking-wider text-${st.color}-400`}>{st.label}</span>
                {st.icon}
              </div>
              <p className="text-3xl font-extrabold font-mono text-white">{st.data?.count?.toLocaleString() || 0}</p>
              <div className="flex items-center justify-between mt-1">
                <span className="text-[10px] text-slate-400">{st.desc}</span>
                <span className={`text-xs font-semibold text-${st.color}-400`}>{st.data?.pct || 0}%</span>
              </div>
            </div>
          ))}
        </div>

        {/* Multi-segment visual progress bar */}
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span>URL Lifecycle Distribution Across All Portals:</span>
            <span className="font-mono text-slate-300">100% Surveyed</span>
          </div>
          <div className="h-3 w-full rounded-full bg-slate-950 overflow-hidden flex border border-slate-800">
            <div style={{ width: `${enumSummary?.done?.pct || 0}%` }} title={`DONE: ${enumSummary?.done?.pct}%`} className="bg-emerald-500 h-full transition-all" />
            <div style={{ width: `${enumSummary?.pending?.pct || 0}%` }} title={`PENDING: ${enumSummary?.pending?.pct}%`} className="bg-amber-500 h-full transition-all" />
            <div style={{ width: `${enumSummary?.recheck_due?.pct || 0}%` }} title={`RECHECK_DUE: ${enumSummary?.recheck_due?.pct}%`} className="bg-indigo-500 h-full transition-all" />
            <div style={{ width: `${enumSummary?.closed?.pct || 0}%` }} title={`CLOSED: ${enumSummary?.closed?.pct}%`} className="bg-slate-600 h-full transition-all" />
            <div style={{ width: `${enumSummary?.failed?.pct || 0}%` }} title={`FAILED: ${enumSummary?.failed?.pct}%`} className="bg-rose-500 h-full transition-all" />
          </div>
        </div>
      </div>

      {/* Crawl Control Deck */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <label className="text-[11px] uppercase tracking-wider text-slate-400 font-bold block mb-1">
                Crawl Phase
              </label>
              <select
                value={phase}
                onChange={(e) => setPhase(e.target.value)}
                className="bg-slate-950 border border-slate-800 text-white text-xs rounded-xl px-3 py-2 font-medium focus:outline-none focus:border-indigo-500"
              >
                <option value="all">Full Pipeline (Phase 1 + Phase 2)</option>
                <option value="discover">Phase 1: URL Discovery</option>
                <option value="detail">Phase 2: Detail Extraction</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] uppercase tracking-wider text-slate-400 font-bold block mb-1">
                Batch Limit
              </label>
              <input
                type="number"
                min="1"
                max="200"
                value={maxItems}
                onChange={(e) => setMaxItems(Number(e.target.value))}
                className="w-28 bg-slate-950 border border-slate-800 text-white text-xs rounded-xl px-3 py-2 font-mono focus:outline-none focus:border-indigo-500"
              />
            </div>
            {(selectedSource === 'topcv' || selectedSource === 'jobsgo') && (
              <div>
                <label className="text-[11px] uppercase tracking-wider text-slate-400 font-bold block mb-1">
                  Cloudflare Bypass Engine
                </label>
                <select
                  value={engine}
                  onChange={(e) => setEngine(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-white text-xs rounded-xl px-3 py-2 font-medium focus:outline-none focus:border-indigo-500"
                >
                  <option value="curl_cffi">curl_cffi (JA3/TLS Chrome 124)</option>
                  <option value="playwright">playwright (Headless Browser Fallback)</option>
                </select>
              </div>
            )}
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
                className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white text-xs font-bold transition shadow-lg shadow-indigo-600/30"
              >
                <Play className="w-4 h-4 fill-current" />
                <span>START BATCH CRAWL</span>
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Live Terminal Stream */}
      <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-2">
        <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
          <div className="flex items-center space-x-2 text-xs font-bold text-slate-300">
            <Terminal className="w-4 h-4 text-emerald-400" />
            <span>Live Console Stream (Server-Sent Events)</span>
            {isCrawling && (
              <span className="flex items-center space-x-1 text-[11px] font-semibold text-emerald-400 ml-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
                <span>Streaming...</span>
              </span>
            )}
          </div>
          <button onClick={() => setLogs([])} className="text-xs text-slate-400 hover:text-white transition">
            Clear
          </button>
        </div>
        <div
          ref={logTerminalRef}
          className="h-48 overflow-y-auto font-mono text-xs text-slate-300 space-y-1 p-2 bg-slate-900/60 rounded-xl select-text"
        >
          {logs.length === 0 ? (
            <div className="text-slate-400 italic">
              No logs yet. Click &quot;START BATCH CRAWL&quot; to stream execution logs from CLI run.py...
            </div>
          ) : (
            logs.map((line, idx) => (
              <div key={idx} className="whitespace-pre-wrap leading-tight">{line}</div>
            ))
          )}
        </div>
      </div>

      {/* 7. URL LEDGER MANIFEST (ID & STATUS FOCUS) */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <FileCode2 className="w-4 h-4 text-indigo-400" />
              <span>URL Ledger Manifest ({selectedSource.toUpperCase()})</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Total: <span className="font-bold text-white">{ledgerTotal}</span> URLs
              • Done: <span className="text-emerald-400 font-semibold">{ledgerCounts['DONE'] || ledgerCounts['SCRAPED'] || 0}</span>
              • Pending: <span className="text-amber-400 font-semibold">{ledgerCounts['PENDING'] || ledgerCounts['NEW'] || 0}</span>
              • Failed: <span className="text-rose-400 font-semibold">{ledgerCounts['ERROR'] || ledgerCounts['FAILED'] || 0}</span>
            </p>
          </div>
          <div className="flex items-center space-x-2">
            <select
              value={statusFilter}
              onChange={(e) => { setStatusFilter(e.target.value); setLedgerPage(1) }}
              className="bg-slate-950 border border-slate-800 text-xs rounded-xl px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">All Status</option>
              <option value="DONE">DONE (Extracted)</option>
              <option value="PENDING">PENDING (Queued)</option>
              <option value="RECHECK_DUE">RECHECK_DUE (21-Day)</option>
              <option value="CLOSED">CLOSED (Expired)</option>
              <option value="FAILED">FAILED (Error)</option>
            </select>
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Search Job ID, URL Hash..."
                value={searchLedger}
                onChange={(e) => { setSearchLedger(e.target.value); setLedgerPage(1) }}
                className="bg-slate-950 border border-slate-800 text-xs rounded-xl pl-9 pr-3 py-2 text-white placeholder-slate-400 w-56 focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
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
                  <td colSpan={6} className="py-6 text-center text-slate-400">
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
                    <tr key={idx} className="hover:bg-slate-800/40 transition">
                      <td className="py-2.5 px-3 font-mono font-bold text-white">
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
                              : 'bg-slate-800 text-slate-300'
                          }`}
                        >
                          {st}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 font-mono text-slate-400">
                        {item.http_status || '—'}
                      </td>
                      <td className="py-2.5 px-3 font-mono text-[11px] text-slate-300 max-w-xs truncate">
                        {item.content_hash ? item.content_hash.slice(0, 24) + '...' : isPending ? '(Awaiting Phase 2)' : '—'}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400 text-[11px]">
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
                          <span className="text-slate-500 text-[10px]">—</span>
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
        <div className="flex items-center justify-between text-xs text-slate-400 pt-3 border-t border-slate-800/80">
          <span>Page {ledgerPage}</span>
          <div className="flex space-x-2">
            <button
              disabled={ledgerPage <= 1}
              onClick={() => setLedgerPage((p) => p - 1)}
              className="px-3 py-1 rounded-lg bg-slate-950 border border-slate-800 hover:bg-slate-800 disabled:opacity-40 transition"
            >
              Previous
            </button>
            <button
              disabled={ledgerItems.length < 15}
              onClick={() => setLedgerPage((p) => p + 1)}
              className="px-3 py-1 rounded-lg bg-slate-950 border border-slate-800 hover:bg-slate-800 disabled:opacity-40 transition"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
export default CrawlingPage
