import React, { useEffect, useState, useRef } from 'react'
import axios from 'axios'
import {
  Play,
  Square,
  Terminal,
  Radio,
  Search,
  ExternalLink,
  ShieldCheck,
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
} from 'lucide-react'
import {
  SourceStatus,
  EnumStatusSummary,
  WeeklyScheduleResponse,
  CloudSyncOverview,
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
  const [ledgerItems, setLedgerItems] = useState<any[]>([])
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
      setLogs([`[Client] Khởi động crawler cho nguồn ${selectedSource.toUpperCase()} (Phase: ${phase})...`])
      await axios.post(`/api/v1/crawling/${selectedSource}/trigger`, {
        phase,
        max_items: maxItems,
        engine: selectedSource === 'topcv' || selectedSource === 'jobsgo' ? engine : undefined,
      })
      startLogStream()
      fetchSources()
      fetchEnumSummary()
      fetchWeeklySchedule()
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || err.message || 'Lỗi khởi động crawler')
      setIsCrawling(false)
    }
  }

  const handleStopCrawl = async () => {
    try {
      await axios.post(`/api/v1/crawling/${selectedSource}/stop`)
      if (eventSourceRef.current) eventSourceRef.current.close()
      setIsCrawling(false)
      fetchSources()
    } catch (err: any) {
      setErrorMessage(err.message || 'Lỗi dừng tiến trình crawler')
    }
  }

  const handleSyncSourceToCloud = async () => {
    try {
      setIsSyncingSource(true)
      setSyncFeedback(null)
      const res = await axios.post(`/api/v1/crawling/${selectedSource}/sync-cloud`)
      setSyncFeedback(`Đã đồng bộ thành công nguồn ${selectedSource.toUpperCase()} lên Cloudflare R2!`)
      await Promise.all([fetchCloudSync(), fetchSources()])
    } catch (err: any) {
      setSyncFeedback(`Lỗi đồng bộ nguồn ${selectedSource}: ${err.message}`)
    } finally {
      setIsSyncingSource(false)
    }
  }

  const handleSyncAllToCloud = async () => {
    try {
      setIsSyncingAll(true)
      setSyncFeedback(null)
      await axios.post('/api/v1/crawling/sync-all-cloud')
      setSyncFeedback('Đã hoàn tất đồng bộ toàn bộ 8 nguồn lên Cloudflare R2 bucket vn-it-jobs!')
      await Promise.all([fetchCloudSync(), fetchSources()])
    } catch (err: any) {
      setSyncFeedback(`Lỗi đồng bộ toàn hệ thống: ${err.message}`)
    } finally {
      setIsSyncingAll(false)
    }
  }

  const currentSourceCloud = cloudSync?.sources?.[selectedSource]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-5 rounded-2xl bg-slate-900 border border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <Radio className="w-4 h-4 text-indigo-400" />
            <span className="text-xs font-bold text-indigo-400 uppercase tracking-wider">
              Phân Hệ Vận Hành • Crawling Operations
            </span>
          </div>
          <h2 className="text-xl font-bold text-white mt-1">
            Điều Phối Cào Batch & URL Ledger ({selectedSource.toUpperCase()})
          </h2>
          <p className="text-xs text-slate-400">
            Kiến trúc Two-Phase Decoupled Crawler kết hợp giám sát trạng thái Enum và đồng bộ hóa Cloudflare R2.
          </p>
        </div>

        {/* Source selector buttons */}
        <div className="flex flex-wrap items-center gap-1.5 p-1 rounded-xl bg-slate-950 border border-slate-800">
          {sources.map((s) => (
            <button
              key={s.id}
              onClick={() => {
                setSelectedSource(s.id)
                setLogs([])
                setLedgerPage(1)
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase transition-all ${
                selectedSource === s.id
                  ? 'bg-indigo-600 text-white shadow-md shadow-indigo-600/30'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {s.name}
            </button>
          ))}
        </div>
      </div>

      {/* CLOUD LAKEHOUSE SYNCHRONIZATION STRIP */}
      <div className="p-4 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/40 border border-slate-800 flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex items-center space-x-3.5">
          <div className="w-10 h-10 rounded-xl bg-indigo-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
            <Cloud className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <span className="text-xs font-bold text-white uppercase tracking-wider">
                Cloudflare R2 Synchronization
              </span>
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
                    <span>ĐANG ĐỐI SOÁT R2...</span>
                  </span>
                ) : cloudSync?.connected ? (
                  `ONLINE (${cloudSync.latency_ms}ms)`
                ) : (
                  'DISCONNECTED'
                )}
              </span>
              <span className="text-[11px] text-slate-400 font-mono">Bucket: vn-it-jobs</span>
            </div>
            <p className="text-xs text-slate-300 mt-0.5">
              {loadingCloudSync ? (
                <span className="text-slate-400 italic">Đang đối chiếu dữ liệu cục bộ với Cloudflare R2...</span>
              ) : (
                <>
                  Tỷ lệ đồng bộ toàn hệ thống: <strong className="text-emerald-400 font-mono">{cloudSync?.overall_sync_pct ?? 0}%</strong> • Cục bộ:{' '}
                  <span className="font-mono text-slate-200">{cloudSync?.total_local_raw ?? 0}</span> files • Đã đẩy lên R2:{' '}
                  <span className="font-mono text-indigo-300">{cloudSync?.total_cloud_raw ?? 0}</span> files
                </>
              )}
            </p>
          </div>
        </div>

        <div className="flex items-center space-x-2 shrink-0">
          <button
            onClick={handleSyncSourceToCloud}
            disabled={isSyncingSource || isSyncingAll}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-indigo-600/20 hover:bg-indigo-600/30 border border-indigo-500/30 text-indigo-300 text-xs font-semibold transition"
          >
            {isSyncingSource ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <UploadCloud className="w-3.5 h-3.5" />
            )}
            <span>Đồng Bộ {selectedSource.toUpperCase()} Lên R2</span>
          </button>

          <button
            onClick={handleSyncAllToCloud}
            disabled={isSyncingSource || isSyncingAll}
            className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-slate-950 hover:bg-slate-800 border border-slate-800 text-slate-200 text-xs font-semibold transition"
          >
            {isSyncingAll ? (
              <RefreshCw className="w-3.5 h-3.5 animate-spin text-indigo-400" />
            ) : (
              <Sparkles className="w-3.5 h-3.5 text-amber-400" />
            )}
            <span>Đồng Bộ Toàn Bộ 8 Sàn</span>
          </button>
        </div>
      </div>

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

      {/* URL STATUS ENUM METRICS COCKPIT */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <Layers className="w-4 h-4 text-indigo-400" />
              <span>Báo Cáo Định Lượng 5 Trạng Thái Enum Vòng Đời URL</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Tổng số <span className="text-white font-bold font-mono">{enumSummary?.total?.toLocaleString() || '10,488'}</span> URLs trong Sổ cái URL Ledger toàn hệ thống. Nhấp vào thẻ để lọc danh mục.
            </p>
          </div>
          {statusFilter !== 'ALL' && (
            <button
              onClick={() => setStatusFilter('ALL')}
              className="text-xs text-indigo-400 hover:underline flex items-center space-x-1 font-semibold"
            >
              <span>Xóa bộ lọc (Đang lọc: {statusFilter})</span>
            </button>
          )}
        </div>

        {/* 5 Enum Cards Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* 1. PENDING */}
          <div
            onClick={() => setStatusFilter(statusFilter === 'PENDING' ? 'ALL' : 'PENDING')}
            className={`p-3.5 rounded-xl cursor-pointer border transition-all ${
              statusFilter === 'PENDING'
                ? 'bg-amber-500/20 border-amber-500 ring-2 ring-amber-500/40'
                : 'bg-slate-950/60 border-slate-800 hover:border-amber-500/50 hover:bg-slate-950'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-amber-400">
                1. PENDING
              </span>
              <Clock className="w-4 h-4 text-amber-400" />
            </div>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-xl font-bold font-mono text-white">
                {enumSummary?.pending?.count?.toLocaleString() || 0}
              </span>
              <span className="text-xs font-semibold text-amber-400">
                {enumSummary?.pending?.pct || 0}%
              </span>
            </div>
            <p className="text-[10px] text-slate-400 mt-1">Đang chờ cào chi tiết Phase 2</p>
          </div>

          {/* 2. DONE */}
          <div
            onClick={() => setStatusFilter(statusFilter === 'DONE' ? 'ALL' : 'DONE')}
            className={`p-3.5 rounded-xl cursor-pointer border transition-all ${
              statusFilter === 'DONE'
                ? 'bg-emerald-500/20 border-emerald-500 ring-2 ring-emerald-500/40'
                : 'bg-slate-950/60 border-slate-800 hover:border-emerald-500/50 hover:bg-slate-950'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-emerald-400">
                2. DONE
              </span>
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
            </div>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-xl font-bold font-mono text-white">
                {enumSummary?.done?.count?.toLocaleString() || 0}
              </span>
              <span className="text-xs font-semibold text-emerald-400">
                {enumSummary?.done?.pct || 0}%
              </span>
            </div>
            <p className="text-[10px] text-slate-400 mt-1">Đã cào Raw As-Is & Hash</p>
          </div>

          {/* 3. RECHECK_DUE */}
          <div
            onClick={() => setStatusFilter(statusFilter === 'RECHECK_DUE' ? 'ALL' : 'RECHECK_DUE')}
            className={`p-3.5 rounded-xl cursor-pointer border transition-all ${
              statusFilter === 'RECHECK_DUE'
                ? 'bg-indigo-500/20 border-indigo-500 ring-2 ring-indigo-500/40'
                : 'bg-slate-950/60 border-slate-800 hover:border-indigo-500/50 hover:bg-slate-950'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-indigo-400">
                3. RECHECK_DUE
              </span>
              <RotateCcw className="w-4 h-4 text-indigo-400" />
            </div>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-xl font-bold font-mono text-white">
                {enumSummary?.recheck_due?.count?.toLocaleString() || 0}
              </span>
              <span className="text-xs font-semibold text-indigo-400">
                {enumSummary?.recheck_due?.pct || 0}%
              </span>
            </div>
            <p className="text-[10px] text-slate-400 mt-1">Đến hạn tái cào (≥21 ngày)</p>
          </div>

          {/* 4. CLOSED */}
          <div
            onClick={() => setStatusFilter(statusFilter === 'CLOSED' ? 'ALL' : 'CLOSED')}
            className={`p-3.5 rounded-xl cursor-pointer border transition-all ${
              statusFilter === 'CLOSED'
                ? 'bg-slate-700/30 border-slate-500 ring-2 ring-slate-500/40'
                : 'bg-slate-950/60 border-slate-800 hover:border-slate-600 hover:bg-slate-950'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">
                4. CLOSED
              </span>
              <XCircle className="w-4 h-4 text-slate-400" />
            </div>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-xl font-bold font-mono text-white">
                {enumSummary?.closed?.count?.toLocaleString() || 0}
              </span>
              <span className="text-xs font-semibold text-slate-400">
                {enumSummary?.closed?.pct || 0}%
              </span>
            </div>
            <p className="text-[10px] text-slate-400 mt-1">Tin đã đóng / Hết hạn / 404</p>
          </div>

          {/* 5. FAILED */}
          <div
            onClick={() => setStatusFilter(statusFilter === 'FAILED' ? 'ALL' : 'FAILED')}
            className={`p-3.5 rounded-xl cursor-pointer border transition-all ${
              statusFilter === 'FAILED'
                ? 'bg-rose-500/20 border-rose-500 ring-2 ring-rose-500/40'
                : 'bg-slate-950/60 border-slate-800 hover:border-rose-500/50 hover:bg-slate-950'
            }`}
          >
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold uppercase tracking-wider text-rose-400">
                5. FAILED
              </span>
              <AlertCircle className="w-4 h-4 text-rose-400" />
            </div>
            <div className="mt-2 flex items-baseline justify-between">
              <span className="text-xl font-bold font-mono text-white">
                {enumSummary?.failed?.count?.toLocaleString() || 0}
              </span>
              <span className="text-xs font-semibold text-rose-400">
                {enumSummary?.failed?.pct || 0}%
              </span>
            </div>
            <p className="text-[10px] text-slate-400 mt-1">Lỗi mạng / Chặn bot sau retry</p>
          </div>
        </div>

        {/* Multi-segment visual progress bar */}
        <div className="space-y-1.5 pt-1">
          <div className="flex items-center justify-between text-[11px] text-slate-400">
            <span>Phân Bổ Tỷ Trọng Vòng Đời URLs Toàn Hệ Thống:</span>
            <span className="font-mono text-slate-300">100% Đã Khảo Sát</span>
          </div>
          <div className="h-3 w-full rounded-full bg-slate-950 overflow-hidden flex border border-slate-800">
            <div
              style={{ width: `${enumSummary?.done?.pct || 0}%` }}
              title={`DONE: ${enumSummary?.done?.pct}%`}
              className="bg-emerald-500 h-full transition-all"
            />
            <div
              style={{ width: `${enumSummary?.pending?.pct || 0}%` }}
              title={`PENDING: ${enumSummary?.pending?.pct}%`}
              className="bg-amber-500 h-full transition-all"
            />
            <div
              style={{ width: `${enumSummary?.recheck_due?.pct || 0}%` }}
              title={`RECHECK_DUE: ${enumSummary?.recheck_due?.pct}%`}
              className="bg-indigo-500 h-full transition-all"
            />
            <div
              style={{ width: `${enumSummary?.closed?.pct || 0}%` }}
              title={`CLOSED: ${enumSummary?.closed?.pct}%`}
              className="bg-slate-600 h-full transition-all"
            />
            <div
              style={{ width: `${enumSummary?.failed?.pct || 0}%` }}
              title={`FAILED: ${enumSummary?.failed?.pct}%`}
              className="bg-rose-500 h-full transition-all"
            />
          </div>
        </div>
      </div>

      {/* WEEKLY CRAWL PROJECTION SCHEDULE TABLE */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800 pb-3">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <Calendar className="w-4 h-4 text-indigo-400" />
              <span>Bảng Lịch Dự Kiến Cào 1 Tuần (Weekly Crawl Projection Schedule)</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Kế hoạch định ngạch 7 ngày xoay vòng trên Apache Airflow: Hạn mức dự kiến{' '}
              <strong className="text-indigo-300 font-mono">
                {weeklySchedule?.total_projected_weekly?.toLocaleString() || '1,800'}
              </strong>{' '}
              tin/tuần vs Đã thu thập{' '}
              <strong className="text-emerald-400 font-mono">
                {weeklySchedule?.total_actual_crawled?.toLocaleString() || 0}
              </strong>{' '}
              tin ({weeklySchedule?.overall_progress_pct || 0}% chỉ tiêu).
            </p>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Ngày Trong Tuần</th>
                <th className="py-2.5 px-3">Sàn Trọng Tâm</th>
                <th className="py-2.5 px-3">DAG ID & Giờ Chạy</th>
                <th className="py-2.5 px-3">Dự Kiến Quota</th>
                <th className="py-2.5 px-3">Thực Tế Trong Kho</th>
                <th className="py-2.5 px-3">Tiến Độ %</th>
                <th className="py-2.5 px-3">Engine & Chống Bot</th>
                <th className="py-2.5 px-3 text-right">Trạng Thái</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {weeklySchedule?.days?.map((day) => {
                const isCompleted = day.status === 'COMPLETED'
                const isRunning = day.status === 'ACTIVE_QUEUE'

                return (
                  <tr key={day.day_index} className="hover:bg-slate-800/40 transition">
                    <td className="py-2.5 px-3 font-bold text-white whitespace-nowrap">
                      {day.day_of_week}
                    </td>
                    <td className="py-2.5 px-3 font-semibold text-indigo-300 uppercase">
                      {day.focal_source}
                    </td>
                    <td className="py-2.5 px-3 font-mono text-[11px] text-slate-300">
                      <div>{day.dag_id}</div>
                      <span className="text-[10px] text-slate-500 font-sans">
                        Hàng ngày {day.scheduled_time}
                      </span>
                    </td>
                    <td className="py-2.5 px-3 font-mono text-white font-bold">
                      {day.projected_quota} tin
                    </td>
                    <td className="py-2.5 px-3 font-mono text-emerald-400 font-bold">
                      {day.actual_crawled.toLocaleString()} tin
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
                        <span className="font-mono text-[10px] text-slate-300">
                          {day.progress_pct}%
                        </span>
                      </div>
                    </td>
                    <td className="py-2.5 px-3 text-[11px] text-slate-300">
                      <div>{day.engine}</div>
                      <span className="text-[10px] text-slate-500">{day.recrawl_strategy}</span>
                    </td>
                    <td className="py-2.5 px-3 text-right">
                      {isCompleted ? (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                          <Check className="w-3 h-3" />
                          <span>HOÀN TẤT</span>
                        </span>
                      ) : isRunning ? (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold bg-blue-500/10 text-blue-400 border border-blue-500/20">
                          <RefreshCw className="w-3 h-3 animate-spin" />
                          <span>ĐANG CHẠY</span>
                        </span>
                      ) : (
                        <span className="inline-flex items-center space-x-1 px-2 py-0.5 rounded text-[10px] font-bold bg-slate-800 text-slate-400">
                          <Clock className="w-3 h-3" />
                          <span>LÊN LỊCH</span>
                        </span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Crawl Control Deck */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <div>
              <label className="text-[11px] uppercase tracking-wider text-slate-400 font-bold block mb-1">
                Giai Đoạn Cào (Phase)
              </label>
              <select
                value={phase}
                onChange={(e) => setPhase(e.target.value)}
                className="bg-slate-950 border border-slate-800 text-white text-xs rounded-xl px-3 py-2 font-medium focus:outline-none focus:border-indigo-500"
              >
                <option value="all">Toàn bộ (Phase 1 + Phase 2)</option>
                <option value="discover">Pha 1: Quét Link (URL Discovery)</option>
                <option value="detail">Pha 2: Cào Chi Tiết (Detail Extraction)</option>
              </select>
            </div>

            <div>
              <label className="text-[11px] uppercase tracking-wider text-slate-400 font-bold block mb-1">
                Số Bài Tối Đa (Batch Limit)
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
                  Engine Vượt Cloudflare
                </label>
                <select
                  value={engine}
                  onChange={(e) => setEngine(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-white text-xs rounded-xl px-3 py-2 font-medium focus:outline-none focus:border-indigo-500"
                >
                  <option value="curl_cffi">curl_cffi (JA3/TLS Chrome 124 - Siêu Nhẹ)</option>
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
                <span>DỪNG TIẾN TRÌNH</span>
              </button>
            ) : (
              <button
                onClick={handleStartCrawl}
                className="flex items-center space-x-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white text-xs font-bold transition shadow-lg shadow-indigo-600/30"
              >
                <Play className="w-4 h-4 fill-current" />
                <span>BẮT ĐẦU CÀO BATCH</span>
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
          <button
            onClick={() => setLogs([])}
            className="text-xs text-slate-400 hover:text-white transition"
          >
            Xóa màn hình
          </button>
        </div>
        <div
          ref={logTerminalRef}
          className="h-48 overflow-y-auto font-mono text-xs text-slate-300 space-y-1 p-2 bg-slate-900/60 rounded-xl select-text"
        >
          {logs.length === 0 ? (
            <div className="text-slate-400 italic">
              Chưa có log. Bấm "BẮT ĐẦU CÀO BATCH" để stream log thực thi từ CLI run.py...
            </div>
          ) : (
            logs.map((line, idx) => (
              <div key={idx} className="whitespace-pre-wrap leading-tight">
                {line}
              </div>
            ))
          )}
        </div>
      </div>

      {/* URL Ledger Catalog Table */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <FileCode2 className="w-4 h-4 text-indigo-400" />
              <span>URL Ledger Catalog ({selectedSource.toUpperCase()})</span>
            </h3>
            <p className="text-xs text-slate-400 mt-0.5">
              Tổng số: <span className="font-bold text-white">{ledgerTotal}</span> URLs • Đã cào:{' '}
              <span className="text-emerald-400 font-semibold">{ledgerCounts['SCRAPED'] || ledgerCounts['DONE'] || 0}</span> • Lỗi:{' '}
              <span className="text-rose-400 font-semibold">{ledgerCounts['ERROR'] || ledgerCounts['FAILED'] || 0}</span> • Chờ cào:{' '}
              <span className="text-amber-400 font-semibold">{ledgerCounts['NEW'] || ledgerCounts['PENDING'] || 0}</span>
            </p>
          </div>

          <div className="flex items-center space-x-2">
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setLedgerPage(1)
              }}
              className="bg-slate-950 border border-slate-800 text-xs rounded-xl px-3 py-2 text-white focus:outline-none focus:border-indigo-500"
            >
              <option value="ALL">Tất cả trạng thái</option>
              <option value="DONE">DONE / SCRAPED (Đã cào)</option>
              <option value="PENDING">PENDING / NEW (Chờ cào)</option>
              <option value="RECHECK_DUE">RECHECK_DUE (Tái cào 21 ngày)</option>
              <option value="CLOSED">CLOSED (Đã đóng)</option>
              <option value="FAILED">FAILED / ERROR (Lỗi)</option>
            </select>

            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
              <input
                type="text"
                placeholder="Tìm tiêu đề, công ty..."
                value={searchLedger}
                onChange={(e) => {
                  setSearchLedger(e.target.value)
                  setLedgerPage(1)
                }}
                className="bg-slate-950 border border-slate-800 text-xs rounded-xl pl-9 pr-3 py-2 text-white placeholder-slate-400 w-56 focus:outline-none focus:border-indigo-500"
              />
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Chức Danh Công Việc</th>
                <th className="py-2.5 px-3">Công Ty</th>
                <th className="py-2.5 px-3">Trạng Thái</th>
                <th className="py-2.5 px-3">HTTP</th>
                <th className="py-2.5 px-3">Thời Gian Cào</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {ledgerItems.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-slate-400">
                    Không tìm thấy bản ghi URL Ledger nào.
                  </td>
                </tr>
              ) : (
                ledgerItems.map((item, idx) => {
                  const st = String(item.status || 'NEW').toUpperCase()
                  const isDone = st === 'DONE' || st === 'SCRAPED'
                  const isPending = st === 'PENDING' || st === 'NEW'
                  const isDue = st === 'RECHECK_DUE'
                  const isFailed = st === 'FAILED' || st === 'ERROR'
                  const isClosed = st === 'CLOSED'

                  return (
                    <tr key={idx} className="hover:bg-slate-800/40 transition">
                      <td className="py-2.5 px-3 font-semibold text-white max-w-xs truncate">
                        {item.job_title || 'N/A'}
                      </td>
                      <td className="py-2.5 px-3 text-slate-300 max-w-xs truncate">
                        {item.company || 'N/A'}
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
                        {item.http_status || 200}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400 text-[11px]">
                        {item.scraped_at ? item.scraped_at.slice(0, 16) : 'N/A'}
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
          <span>Trang {ledgerPage}</span>
          <div className="flex space-x-2">
            <button
              disabled={ledgerPage <= 1}
              onClick={() => setLedgerPage((p) => p - 1)}
              className="px-3 py-1 rounded-lg bg-slate-950 border border-slate-800 hover:bg-slate-800 disabled:opacity-40 transition"
            >
              Trang trước
            </button>
            <button
              disabled={ledgerItems.length < 15}
              onClick={() => setLedgerPage((p) => p + 1)}
              className="px-3 py-1 rounded-lg bg-slate-950 border border-slate-800 hover:bg-slate-800 disabled:opacity-40 transition"
            >
              Trang sau
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
export default CrawlingPage
