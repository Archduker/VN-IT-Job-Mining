import React, { useEffect, useState } from 'react'
import axios from 'axios'
import {
  Cloud,
  Database,
  HardDrive,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  UploadCloud,
  Check,
  AlertCircle,
  FileText,
  Layers,
  ArrowUpRight,
} from 'lucide-react'
import { CloudHealth, StorageBreakdown, R2DiffResult, R2SyncResponse } from '../types'

const SOURCES = ['topcv', 'topdev', 'itviec', 'careerviet', 'vieclam24h', 'vietnamworks', 'glints', 'jobsgo']

export const CloudflareR2Page: React.FC = () => {
  const [health, setHealth] = useState<CloudHealth | null>(null)
  const [layers, setLayers] = useState<StorageBreakdown | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [selectedSource, setSelectedSource] = useState<string>('topcv')
  const [diffData, setDiffData] = useState<Record<string, R2DiffResult>>({})
  const [loadingDiff, setLoadingDiff] = useState<boolean>(false)
  const [syncingSource, setSyncingSource] = useState<string | null>(null)
  const [syncResult, setSyncResult] = useState<R2SyncResponse | null>(null)
  const [syncError, setSyncError] = useState<string | null>(null)

  const loadBaseData = async () => {
    try {
      setLoading(true)
      const [hRes, lRes] = await Promise.all([
        axios.get<CloudHealth>('/api/v1/cloud/r2/status'),
        axios.get<StorageBreakdown>('/api/v1/cloud/r2/layers'),
      ])
      setHealth(hRes.data)
      setLayers(lRes.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  const loadDiffForSource = async (src: string) => {
    try {
      setLoadingDiff(true)
      const res = await axios.get<R2DiffResult>(`/api/v1/cloud/r2/diff/${src}`)
      setDiffData((prev) => ({ ...prev, [src]: res.data }))
    } catch (e) {
      console.error(e)
    } finally {
      setLoadingDiff(false)
    }
  }

  const loadAllDiffs = async () => {
    for (const src of SOURCES) {
      try {
        const res = await axios.get<R2DiffResult>(`/api/v1/cloud/r2/diff/${src}`)
        setDiffData((prev) => ({ ...prev, [src]: res.data }))
      } catch (e) {
        console.error(`Failed to diff ${src}`, e)
      }
    }
  }

  const handleSyncSource = async (src: string) => {
    try {
      setSyncingSource(src)
      setSyncResult(null)
      setSyncError(null)
      const res = await axios.post<R2SyncResponse>(`/api/v1/cloud/r2/sync/${src}`)
      setSyncResult(res.data)
      // Reload diff and layers
      await Promise.all([loadDiffForSource(src), loadBaseData()])
    } catch (e: any) {
      console.error(e)
      setSyncError(e.response?.data?.detail || e.message || `Lỗi đồng bộ nguồn ${src}`)
    } finally {
      setSyncingSource(null)
    }
  }

  useEffect(() => {
    loadBaseData()
    loadDiffForSource(selectedSource)
  }, [])

  useEffect(() => {
    if (!diffData[selectedSource]) {
      loadDiffForSource(selectedSource)
    }
  }, [selectedSource])

  const currentDiff = diffData[selectedSource]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900 border border-slate-800">
        <div>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-semibold uppercase tracking-wider">
            Cloud Object Storage
          </span>
          <h2 className="text-xl font-bold text-white mt-1.5">
            Cloudflare R2 Data Lakehouse (Độc Quyền)
          </h2>
          <p className="text-xs text-slate-400">
            Hạ tầng lưu trữ đối tượng tập trung duy nhất của dự án VN-IT-Job-Mining (Bucket: vn-it-jobs). Toàn bộ dữ liệu Raw, Staging, Curated được kiểm toán và đồng bộ trực tiếp.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => {
              loadBaseData()
              loadAllDiffs()
            }}
            disabled={loading || loadingDiff}
            className="flex items-center space-x-2 px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 hover:bg-slate-800 text-slate-300 text-xs transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
            <span>Kiểm toán toàn bộ diff</span>
          </button>
        </div>
      </div>

      {/* Connection Status Card */}
      <div
        className={`p-5 rounded-2xl border ${
          health?.connected
            ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-200'
            : 'bg-amber-950/20 border-amber-500/30 text-amber-200'
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div
              className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                health?.connected ? 'bg-emerald-600/30' : 'bg-amber-600/30'
              }`}
            >
              <Cloud className="w-5 h-5 text-white" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">
                Trạng Thái Kết Nối R2: {health?.connected ? 'SẴN SÀNG (ONLINE)' : 'CHƯA KẾT NỐI'}
              </h3>
              <p className="text-xs text-slate-400">
                Endpoint: <span className="font-mono text-slate-300">{health?.endpoint || 'N/A'}</span>
              </p>
            </div>
          </div>

          {health?.connected && (
            <div className="text-right">
              <span className="text-xs text-emerald-400 font-bold">
                Độ trễ ping: {health.latency_ms} ms
              </span>
              <div className="text-[11px] text-slate-400">Bucket: vn-it-jobs</div>
            </div>
          )}
        </div>
      </div>

      {/* 4 Layers Breakdown */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          {
            key: 'url_ledger',
            title: '1. URL Ledger Layer',
            desc: 'Danh mục URL bài đăng & manifests',
            icon: Database,
            color: 'text-indigo-400',
          },
          {
            key: 'raw',
            title: '2. Raw Layer (As-Is)',
            desc: 'Dữ liệu cào Envelope JSON nguyên bản',
            icon: HardDrive,
            color: 'text-cyan-400',
          },
          {
            key: 'staging',
            title: '3. Staging Layer',
            desc: 'Dữ liệu sau khi regex tiền xử lý',
            icon: CheckCircle2,
            color: 'text-amber-400',
          },
          {
            key: 'curated',
            title: '4. Curated Layer',
            desc: 'Bộ dữ liệu vàng Golden Master Parquet',
            icon: Cloud,
            color: 'text-emerald-400',
          },
        ].map((layer) => {
          const Icon = layer.icon
          const metric = layers?.layers?.[layer.key]
          return (
            <div key={layer.key} className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white">{layer.title}</span>
                <Icon className={`w-4 h-4 ${layer.color}`} />
              </div>
              <p className="text-[11px] text-slate-400">{layer.desc}</p>
              <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
                <span className="text-slate-400">Đối tượng (Objects):</span>
                <span className="font-bold text-white">
                  {metric ? metric.count.toLocaleString() : '0'}
                </span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-slate-400">Dung lượng:</span>
                <span className="font-mono text-slate-300">
                  {metric ? `${metric.size_mb} MB` : '0.00 MB'}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* R2 Diff Engine & Synchronization Section */}
      <div className="rounded-2xl bg-slate-900 border border-slate-800 p-5 space-y-5">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-2">
            <UploadCloud className="w-5 h-5 text-indigo-400" />
            <div>
              <h3 className="text-sm font-bold text-white">
                R2 Diff Engine & Công Cụ Đồng Bộ Hóa Đám Mây
              </h3>
              <p className="text-xs text-slate-400">
                So sánh chênh lệch giữa ổ đĩa cục bộ (Local Disk) và Cloudflare R2 bucket.
              </p>
            </div>
          </div>

          {/* Source Tabs */}
          <div className="flex items-center flex-wrap gap-1 bg-slate-950 p-1 rounded-xl border border-slate-800">
            {SOURCES.map((src) => (
              <button
                key={src}
                onClick={() => setSelectedSource(src)}
                className={`px-3 py-1 rounded-lg text-xs font-semibold capitalize transition ${
                  selectedSource === src
                    ? 'bg-indigo-600 text-white shadow-sm'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {src}
              </button>
            ))}
          </div>
        </div>

        {/* Sync Status Banner for Selected Source */}
        {syncResult && (
          <div className="p-3.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <Check className="w-4 h-4 text-emerald-400" />
              <span>
                Đã đồng bộ thành công sàn <strong className="uppercase">{syncResult.source}</strong>: Tải lên {syncResult.uploaded_count} tệp tin mới lên R2 (Lỗi: {syncResult.failed_count}).
              </span>
            </div>
          </div>
        )}

        {syncError && (
          <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-300 text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
            <span>Lỗi đồng bộ: {syncError}</span>
          </div>
        )}

        {/* Diff Overview Card */}
        {currentDiff ? (
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800">
                <span className="text-xs text-slate-400">Tập Tin Cục Bộ (Local)</span>
                <div className="text-lg font-bold text-white mt-1">
                  {currentDiff.local_count} files
                </div>
                <div className="text-[11px] text-slate-500 mt-1 font-mono">
                  data/{currentDiff.source}/raw/
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800">
                <span className="text-xs text-slate-400">Đã Có Trên R2 (Cloud)</span>
                <div className="text-lg font-bold text-indigo-400 mt-1">
                  {currentDiff.cloud_count} files
                </div>
                <div className="text-[11px] text-slate-500 mt-1 font-mono">
                  raw/{currentDiff.source}/
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800">
                <span className="text-xs text-slate-400">Chưa Đồng Bộ (Missing)</span>
                <div
                  className={`text-lg font-bold mt-1 ${
                    currentDiff.missing_count === 0 ? 'text-emerald-400' : 'text-amber-400'
                  }`}
                >
                  {currentDiff.missing_count} files
                </div>
                <div className="text-[11px] text-slate-500 mt-1">
                  Cần đẩy lên R2
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-950/50 border border-slate-800 flex flex-col justify-between">
                <div>
                  <span className="text-xs text-slate-400">Tỷ Lệ Đồng Bộ</span>
                  <div className="text-lg font-bold text-emerald-400 mt-1">
                    {currentDiff.synced_pct}%
                  </div>
                </div>

                <button
                  onClick={() => handleSyncSource(selectedSource)}
                  disabled={syncingSource === selectedSource || currentDiff.missing_count === 0}
                  className={`mt-2 flex items-center justify-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
                    currentDiff.missing_count === 0
                      ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                      : 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-md'
                  }`}
                >
                  {syncingSource === selectedSource ? (
                    <>
                      <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                      <span>Đang tải lên...</span>
                    </>
                  ) : (
                    <>
                      <UploadCloud className="w-3.5 h-3.5" />
                      <span>{currentDiff.missing_count === 0 ? 'Đã Đồng Bộ' : 'Đồng Bộ Lên R2'}</span>
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Missing Keys Preview */}
            {currentDiff.missing_in_cloud.length > 0 && (
              <div className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between text-xs font-medium text-slate-300">
                  <span className="flex items-center space-x-1.5 text-amber-400">
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>Danh sách {currentDiff.missing_count} tệp tin chưa có trên R2 (Xem trước tối đa 10):</span>
                  </span>
                </div>
                <div className="max-h-36 overflow-y-auto space-y-1 font-mono text-[11px] text-slate-400">
                  {currentDiff.missing_in_cloud.slice(0, 10).map((file, idx) => (
                    <div key={idx} className="flex items-center space-x-2 py-0.5 px-2 rounded bg-slate-900">
                      <FileText className="w-3 h-3 text-slate-500 shrink-0" />
                      <span className="truncate">{file}</span>
                    </div>
                  ))}
                  {currentDiff.missing_in_cloud.length > 10 && (
                    <div className="text-[10px] text-slate-500 italic px-2 pt-1">
                      ... và {currentDiff.missing_in_cloud.length - 10} tệp tin khác.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="py-8 text-center text-xs text-slate-500">
            {loadingDiff ? (
              <div className="flex items-center justify-center space-x-2">
                <RefreshCw className="w-4 h-4 animate-spin text-indigo-400" />
                <span>Đang quét chênh lệch Local vs R2 cho sàn {selectedSource}...</span>
              </div>
            ) : (
              'Chọn một sàn để kiểm tra diff.'
            )}
          </div>
        )}
      </div>
    </div>
  )
}
export default CloudflareR2Page
