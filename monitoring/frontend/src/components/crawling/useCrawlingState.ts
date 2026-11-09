import { useEffect, useState, useRef } from 'react'
import axios from 'axios'
import {
  SourceStatus,
  EnumStatusSummary,
  WeeklyScheduleResponse,
  CloudSyncOverview,
  Phase1DiscoveryItem,
  Phase2DetailItem,
  LedgerItem,
} from '../../types'

export function useCrawlingState() {
  const [sources, setSources] = useState<SourceStatus[]>([])
  const [selectedSource, setSelectedSource] = useState<string>('topcv')

  // Crawler Controls state
  const [phase, setPhase] = useState<string>('all')
  const [maxItems, setMaxItems] = useState<number>(10)
  const [engine, setEngine] = useState<string>('curl_cffi')
  const [syncR2, setSyncR2] = useState<boolean>(true)
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
      setErrorMessage('Không tải được dữ liệu vận hành. Vui lòng thử lại.')
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
      setErrorMessage('Không tải được dữ liệu vận hành. Vui lòng thử lại.')
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

  useEffect(() => { eventSourceRef.current?.close(); setLogs([]); setLedgerPage(1) }, [selectedSource])
  useEffect(() => () => eventSourceRef.current?.close(), [])

  const startLogStream = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }
    const es = new EventSource(`/api/v1/crawling/${selectedSource}/logs/stream`)
    es.onmessage = (event) => {
      setLogs((prev) => [...prev.slice(-1999), event.data])
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
      setLogs([`[Client] Starting crawler for ${selectedSource.toUpperCase()} (Phase: ${phase}, ${syncR2 ? 'đồng bộ R2' : 'chỉ lưu trên máy'})...`])
      await axios.post(`/api/v1/crawling/${selectedSource}/trigger`, {
        phase,
        max_items: maxItems,
        engine: selectedSource === 'topcv' || selectedSource === 'jobsgo' ? engine : undefined,
        sync_r2: syncR2,
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

  return { logTerminalRef, eventSourceRef, fetchSources, fetchEnumSummary, fetchWeeklySchedule, fetchCloudSync, fetchLedger, startLogStream, handleStartCrawl, handleStopCrawl, handleSyncSourceToCloud, handleSyncAllToCloud, currentSourceCloud, activeSource, phase1Data, phase2Data, sources, setSources, selectedSource, setSelectedSource, phase, setPhase, maxItems, setMaxItems, engine, setEngine, syncR2, setSyncR2, isCrawling, setIsCrawling, logs, setLogs, ledgerItems, setLedgerItems, ledgerTotal, setLedgerTotal, ledgerCounts, setLedgerCounts, ledgerPage, setLedgerPage, searchLedger, setSearchLedger, statusFilter, setStatusFilter, enumSummary, setEnumSummary, weeklySchedule, setWeeklySchedule, cloudSync, setCloudSync, loadingCloudSync, setLoadingCloudSync, isSyncingSource, setIsSyncingSource, isSyncingAll, setIsSyncingAll, syncFeedback, setSyncFeedback, errorMessage, setErrorMessage }
}
