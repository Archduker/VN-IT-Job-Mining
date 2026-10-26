import React, { useEffect, useState, useRef } from 'react'
import axios from 'axios'
import {
  Play,
  Square,
  Terminal,
  FileSpreadsheet,
  BarChart3,
  Search,
  RefreshCw,
  AlertCircle,
  ExternalLink,
} from 'lucide-react'
import { SourceStatus, FieldInventoryItem } from '../types'

export const CollectionPage: React.FC = () => {
  const [sources, setSources] = useState<SourceStatus[]>([])
  const [selectedSource, setSelectedSource] = useState<string>('topcv')
  const [activeSubTab, setActiveSubTab] = useState<'crawler' | 'eda'>('crawler')

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

  // EDA 2D state
  const [inventory, setInventory] = useState<FieldInventoryItem[]>([])
  const [edaLoading, setEdaLoading] = useState<boolean>(false)
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  const fetchSources = async () => {
    try {
      const res = await axios.get<SourceStatus[]>('/api/v1/collection/crawling/sources')
      setSources(res.data)
      const current = res.data.find((s) => s.id === selectedSource)
      if (current) setIsCrawling(current.status === 'running')
    } catch (e) {
      console.error(e)
    }
  }

  const fetchLedger = async () => {
    try {
      const res = await axios.get(`/api/v1/collection/crawling/${selectedSource}/ledger`, {
        params: { page: ledgerPage, page_size: 10, search: searchLedger || undefined },
      })
      setLedgerItems(res.data.items || [])
      setLedgerTotal(res.data.total || 0)
      setLedgerCounts(res.data.counts || {})
    } catch (e) {
      console.error(e)
    }
  }

  const fetchInventory = async () => {
    try {
      setEdaLoading(true)
      const res = await axios.get(`/api/v1/collection/eda/${selectedSource}/inventory`)
      setInventory(res.data || [])
    } catch (e) {
      console.error(e)
    } finally {
      setEdaLoading(false)
    }
  }

  useEffect(() => {
    fetchSources()
  }, [])

  useEffect(() => {
    fetchLedger()
    if (activeSubTab === 'eda') {
      fetchInventory()
    }
  }, [selectedSource, ledgerPage, searchLedger, activeSubTab])

  // Real-time log streaming setup
  const startLogStream = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
    }
    const es = new EventSource(`/api/v1/collection/crawling/${selectedSource}/logs/stream`)
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
      setLogs([`[Client] Đang gửi yêu cầu kích hoạt cào ${selectedSource.toUpperCase()}...`])
      await axios.post(`/api/v1/collection/crawling/${selectedSource}/trigger`, {
        phase,
        max_items: maxItems,
        engine: selectedSource === 'topcv' || selectedSource === 'jobsgo' ? engine : undefined,
      })
      startLogStream()
      fetchSources()
    } catch (err: any) {
      setErrorMessage(err.response?.data?.detail || err.message)
      setIsCrawling(false)
    }
  }

  const handleStopCrawl = async () => {
    try {
      await axios.post(`/api/v1/collection/crawling/${selectedSource}/stop`)
      if (eventSourceRef.current) eventSourceRef.current.close()
      setIsCrawling(false)
      fetchSources()
    } catch (err: any) {
      setErrorMessage(err.message)
    }
  }

  return (
    <div className="space-y-6">
      {/* Stage Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-5 rounded-2xl bg-slate-900 border border-slate-800">
        <div>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-semibold uppercase tracking-wider">
            Giai Đoạn 1 • Stage 1
          </span>
          <h2 className="text-xl font-bold text-white mt-1.5">
            Collection Observatory & Preliminary EDA
          </h2>
          <p className="text-xs text-slate-400">
            Thu thập nguyên bản As-Is (Zero Information Loss) và đánh giá chất lượng trường thô tại 8 sàn.
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
              }}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold uppercase transition-all ${
                selectedSource === s.id
                  ? 'bg-indigo-600 text-white shadow'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800'
              }`}
            >
              {s.name}
            </button>
          ))}
        </div>
      </div>

      {/* Sub Tabs: Crawler Control vs Collection EDA */}
      <div className="flex items-center space-x-2 border-b border-slate-800">
        <button
          onClick={() => setActiveSubTab('crawler')}
          className={`flex items-center space-x-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-colors ${
            activeSubTab === 'crawler'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-white'
          }`}
        >
          <Terminal className="w-4 h-4" />
          <span>Điều Khiển Cào & URL Ledger Catalog</span>
        </button>
        <button
          onClick={() => setActiveSubTab('eda')}
          className={`flex items-center space-x-2 px-4 py-2.5 text-xs font-bold border-b-2 transition-colors ${
            activeSubTab === 'eda'
              ? 'border-indigo-500 text-indigo-400'
              : 'border-transparent text-slate-400 hover:text-white'
          }`}
        >
          <FileSpreadsheet className="w-4 h-4" />
          <span>Collection EDA 2D (Kiểm Kê Trường Thô)</span>
        </button>
      </div>

      {activeSubTab === 'crawler' ? (
        <div className="space-y-6">
          {/* Controls Panel */}
          <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex flex-wrap items-center gap-4">
                <div>
                  <label className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold block mb-1">
                    Giai Đoạn Cào (Phase)
                  </label>
                  <select
                    value={phase}
                    onChange={(e) => setPhase(e.target.value)}
                    className="bg-slate-950 border border-slate-800 text-white text-xs rounded-lg px-3 py-1.5"
                  >
                    <option value="all">Toàn bộ (Phase 1 + Phase 2)</option>
                    <option value="discover">Pha 1: Quét Link (Discover URLs)</option>
                    <option value="detail">Pha 2: Cào Chi Tiết (Detail Extraction)</option>
                  </select>
                </div>

                <div>
                  <label className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold block mb-1">
                    Số Bài Tối Đa
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    value={maxItems}
                    onChange={(e) => setMaxItems(Number(e.target.value))}
                    className="w-24 bg-slate-950 border border-slate-800 text-white text-xs rounded-lg px-3 py-1.5"
                  />
                </div>

                {(selectedSource === 'topcv' || selectedSource === 'jobsgo') && (
                  <div>
                    <label className="text-[11px] uppercase tracking-wider text-slate-400 font-semibold block mb-1">
                      Engine Bypass Cloudflare
                    </label>
                    <select
                      value={engine}
                      onChange={(e) => setEngine(e.target.value)}
                      className="bg-slate-950 border border-slate-800 text-white text-xs rounded-lg px-3 py-1.5"
                    >
                      <option value="curl_cffi">curl_cffi (JA3/TLS Chrome 124 - Nhanh)</option>
                      <option value="playwright">playwright (Headless Chrome)</option>
                    </select>
                  </div>
                )}
              </div>

              <div className="flex items-center space-x-3">
                {isCrawling ? (
                  <button
                    onClick={handleStopCrawl}
                    className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition shadow-lg shadow-rose-600/30"
                  >
                    <Square className="w-4 h-4 fill-current" />
                    <span>DỪNG TIẾN TRÌNH</span>
                  </button>
                ) : (
                  <button
                    onClick={handleStartCrawl}
                    className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition shadow-lg shadow-indigo-600/30"
                  >
                    <Play className="w-4 h-4 fill-current" />
                    <span>BẮT ĐẦU CÀO BATCH</span>
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Live Terminal */}
          <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-2">
            <div className="flex items-center justify-between border-b border-slate-800/80 pb-2">
              <div className="flex items-center space-x-2 text-xs font-bold text-slate-300">
                <Terminal className="w-4 h-4 text-emerald-400" />
                <span>Live Console Logs (Server-Sent Events)</span>
                {isCrawling && (
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse ml-2"></span>
                )}
              </div>
              <button
                onClick={() => setLogs([])}
                className="text-xs text-slate-400 hover:text-white"
              >
                Xóa Log
              </button>
            </div>
            <div
              ref={logTerminalRef}
              className="h-48 overflow-y-auto font-mono text-xs text-slate-300 space-y-1 p-2 bg-slate-900/60 rounded-xl"
            >
              {logs.length === 0 ? (
                <div className="text-slate-400 italic">
                  Chưa có log. Bấm "BẮT ĐẦU CÀO BATCH" để stream log console trực tiếp từ run.py...
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

          {/* URL Ledger Table */}
          <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-bold text-white">
                  Danh Mục URL Ledger ({selectedSource.toUpperCase()})
                </h3>
                <p className="text-xs text-slate-400">
                  Tổng số: {ledgerTotal} URLs • Đã cào: {ledgerCounts['SCRAPED'] || 0} • Lỗi:{' '}
                  {ledgerCounts['ERROR'] || 0}
                </p>
              </div>

              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-2.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Tìm theo chức danh, công ty..."
                  value={searchLedger}
                  onChange={(e) => setSearchLedger(e.target.value)}
                  className="bg-slate-950 border border-slate-800 text-xs rounded-xl pl-9 pr-3 py-2 text-white placeholder-slate-400 w-64 focus:outline-none focus:border-indigo-500"
                />
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Job Title</th>
                    <th className="py-2.5 px-3">Công Ty</th>
                    <th className="py-2.5 px-3">Trạng Thái</th>
                    <th className="py-2.5 px-3">HTTP</th>
                    <th className="py-2.5 px-3">Cào Lúc</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {ledgerItems.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="py-6 text-center text-slate-400">
                        Chưa có dữ liệu URL Ledger cho nguồn này.
                      </td>
                    </tr>
                  ) : (
                    ledgerItems.map((item, idx) => (
                      <tr key={idx} className="hover:bg-slate-800/40">
                        <td className="py-2 px-3 font-semibold text-white max-w-xs truncate">
                          {item.job_title || 'N/A'}
                        </td>
                        <td className="py-2 px-3 text-slate-300 max-w-xs truncate">
                          {item.company || 'N/A'}
                        </td>
                        <td className="py-2 px-3">
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                              item.status === 'SCRAPED'
                                ? 'bg-emerald-500/20 text-emerald-300'
                                : item.status === 'ERROR'
                                ? 'bg-rose-500/20 text-rose-300'
                                : 'bg-slate-800 text-slate-300'
                            }`}
                          >
                            {item.status}
                          </span>
                        </td>
                        <td className="py-2 px-3 font-mono text-slate-400">
                          {item.http_status || 200}
                        </td>
                        <td className="py-2 px-3 text-slate-400 text-[11px]">
                          {item.scraped_at ? item.scraped_at.slice(0, 16) : 'N/A'}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-800/80">
              <span>Trang {ledgerPage}</span>
              <div className="flex space-x-2">
                <button
                  disabled={ledgerPage <= 1}
                  onClick={() => setLedgerPage((p) => p - 1)}
                  className="px-3 py-1 rounded bg-slate-950 border border-slate-800 hover:bg-slate-800 disabled:opacity-40"
                >
                  Trước
                </button>
                <button
                  disabled={ledgerItems.length < 10}
                  onClick={() => setLedgerPage((p) => p + 1)}
                  className="px-3 py-1 rounded bg-slate-950 border border-slate-800 hover:bg-slate-800 disabled:opacity-40"
                >
                  Sau
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* Sub Tab: Collection EDA 2D */
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-white">
                Bảng Kiểm Kê Trường & Tỷ Lệ Thiếu (Field Inventory - {selectedSource.toUpperCase()})
              </h3>
              <p className="text-xs text-slate-400">
                Đánh giá chất lượng cào thô tại nguồn theo chuẩn kỹ năng eda-intelligence.
              </p>
            </div>
            <button
              onClick={fetchInventory}
              disabled={edaLoading}
              className="p-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:bg-slate-800 text-slate-300"
            >
              <RefreshCw className={`w-4 h-4 ${edaLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Tên Trường (Field)</th>
                  <th className="py-2.5 px-3">Kiểu Dữ Liệu</th>
                  <th className="py-2.5 px-3">Số Dòng Thiếu</th>
                  <th className="py-2.5 px-3">Tỷ Lệ Thiếu (%)</th>
                  <th className="py-2.5 px-3">Số Giá Trị Duy Nhất</th>
                  <th className="py-2.5 px-3">Giá Trị Mẫu</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {inventory.map((row) => (
                  <tr key={row.field_name} className="hover:bg-slate-800/40">
                    <td className="py-2.5 px-3 font-mono font-semibold text-white">
                      {row.field_name}
                    </td>
                    <td className="py-2.5 px-3 text-slate-400">{row.data_type}</td>
                    <td className="py-2.5 px-3 text-slate-300">{row.null_count}</td>
                    <td className="py-2.5 px-3 font-semibold">
                      <span
                        className={
                          row.null_rate_pct === 0
                            ? 'text-emerald-400'
                            : row.null_rate_pct < 15
                            ? 'text-cyan-400'
                            : 'text-amber-400'
                        }
                      >
                        {row.null_rate_pct}%
                      </span>
                    </td>
                    <td className="py-2.5 px-3 text-slate-300">{row.unique_count}</td>
                    <td className="py-2.5 px-3 text-slate-400 max-w-xs truncate">
                      {row.sample_value || 'None'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
