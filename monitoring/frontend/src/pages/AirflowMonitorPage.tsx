import React, { useEffect, useState } from 'react'
import axios from 'axios'
import {
  Cpu,
  Server,
  Database,
  Calendar,
  Clock,
  PlayCircle,
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  RefreshCw,
  Activity,
  Layers,
  ShieldCheck,
  ChevronRight,
} from 'lucide-react'
import { AirflowStatusResponse, AirflowDAGItem } from '../types'

export const AirflowMonitorPage: React.FC = () => {
  const [status, setStatus] = useState<AirflowStatusResponse | null>(null)
  const [dags, setDags] = useState<AirflowDAGItem[]>([])
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)

  const loadAirflowData = async () => {
    try {
      setLoading(true)
      setError(null)
      const [statusRes, dagsRes] = await Promise.all([
        axios.get<AirflowStatusResponse>('/api/v1/airflow/status'),
        axios.get<AirflowDAGItem[]>('/api/v1/airflow/dags'),
      ])
      setStatus(statusRes.data)
      setDags(dagsRes.data)
    } catch (e: any) {
      console.error(e)
      setError(e.response?.data?.detail || e.message || 'Không thể kết nối Airflow backend')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAirflowData()
    const interval = setInterval(loadAirflowData, 15000)
    return () => clearInterval(interval)
  }, [])

  const schedulerOnline = status?.scheduler.status === 'ONLINE'
  const webserverOnline = status?.webserver.status === 'ONLINE'
  const dbConnected = status?.database.connected

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-5 rounded-2xl bg-slate-900 border border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 font-semibold uppercase tracking-wider">
              Orchestration Engine
            </span>
            <span className="text-[11px] text-slate-500 font-mono">Port 8080 • PostgreSQL DB</span>
          </div>
          <h2 className="text-xl font-bold text-white mt-1.5 flex items-center space-x-2">
            <span>Apache Airflow Orchestrator Monitor</span>
          </h2>
          <p className="text-xs text-slate-400">
            Giám sát vận hành 9 DAGs cào dữ liệu Hai Pha (Daily Discovery 05:00 & 8 DAGs Chi tiết) và trạng thái daemon cốt lõi.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <a
            href="http://localhost:8080"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-violet-600/20 border border-violet-500/30 text-violet-300 hover:bg-violet-600/30 text-xs font-semibold transition"
          >
            <span>Mở Airflow WebUI</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>

          <button
            onClick={loadAirflowData}
            disabled={loading}
            className="p-2 rounded-xl bg-slate-950 border border-slate-800 hover:bg-slate-800 text-slate-300 transition"
            title="Làm mới trạng thái"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-violet-400' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center space-x-3">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>Lỗi tải thông tin Airflow: {error}</span>
        </div>
      )}

      {/* Daemon Health Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Scheduler */}
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Airflow Scheduler</span>
            <Cpu className="w-4 h-4 text-violet-400" />
          </div>
          <div className="flex items-center space-x-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                schedulerOnline ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'
              }`}
            />
            <span
              className={`text-lg font-bold ${
                schedulerOnline ? 'text-emerald-300' : 'text-rose-400'
              }`}
            >
              {schedulerOnline ? 'ONLINE' : 'STOPPED'}
            </span>
          </div>
          <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
            <span>PID Process:</span>
            <span className="font-mono text-slate-300">
              {status?.scheduler.pid ? status.scheduler.pid : 'Không tìm thấy'}
            </span>
          </div>
        </div>

        {/* Webserver */}
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Airflow Webserver</span>
            <Server className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="flex items-center space-x-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                webserverOnline ? 'bg-emerald-400' : 'bg-rose-500'
              }`}
            />
            <span
              className={`text-lg font-bold ${
                webserverOnline ? 'text-emerald-300' : 'text-rose-400'
              }`}
            >
              {webserverOnline ? 'PORT 8080 ONLINE' : 'STOPPED'}
            </span>
          </div>
          <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
            <span>Giao diện quản trị:</span>
            <a
              href="http://localhost:8080"
              target="_blank"
              rel="noreferrer"
              className="text-cyan-400 hover:underline flex items-center space-x-1"
            >
              <span>localhost:8080</span>
              <ExternalLink className="w-2.5 h-2.5" />
            </a>
          </div>
        </div>

        {/* Database */}
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Metadata Database</span>
            <Database className="w-4 h-4 text-amber-400" />
          </div>
          <div className="flex items-center space-x-2">
            <span
              className={`w-2.5 h-2.5 rounded-full ${
                dbConnected ? 'bg-emerald-400' : 'bg-rose-500'
              }`}
            />
            <span
              className={`text-lg font-bold ${
                dbConnected ? 'text-emerald-300' : 'text-rose-400'
              }`}
            >
              {dbConnected ? 'POSTGRESQL READY' : 'DISCONNECTED'}
            </span>
          </div>
          <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
            <span>Cơ sở dữ liệu:</span>
            <span className="font-mono text-slate-300">
              {status?.database.name || 'airflow'} (Port {status?.database.port || 5432})
            </span>
          </div>
        </div>

        {/* Active DAGs count */}
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-slate-400">Tổng Số DAGs Hoạt Động</span>
            <Layers className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-lg font-bold text-white">
            {status?.active_dags_count || dags.length} DAGs
          </div>
          <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
            <span>Kiến trúc:</span>
            <span className="text-indigo-300">Hai Pha (Discovery & Detail)</span>
          </div>
        </div>
      </div>

      {/* Rotation Policy Explainer Banner */}
      <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex items-start space-x-3">
        <ShieldCheck className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
        <div className="text-xs space-y-1">
          <p className="font-semibold text-slate-200">
            Kiến Trúc Điều Phối Hai Pha (Two-Phase Decoupled Ingestion Pipeline)
          </p>
          <p className="text-slate-400 leading-relaxed">
            Hệ thống phân tách triệt để 2 pha cào: Pha 1 Discovery quét nhanh trang danh mục lúc 05:00 sáng nạp vào URL Ledger, Pha 2 Detail bóc tách chi tiết JobRecord nguyên bản cho 8 sàn (TopDev, CareerViet, ITViec, VietnamWorks, TopCV, ViecLam24h, Glints, JobsGO) vào buổi tối. Dữ liệu sau cào được băm Canonical JSON SHA-256 để chống trùng lặp và đồng bộ trực tiếp lên Cloudflare R2 bucket <span className="font-mono text-indigo-300">vn-it-jobs</span>.
          </p>
        </div>
      </div>

      {/* 7-DAG Table */}
      <div className="rounded-2xl bg-slate-900 border border-slate-800 overflow-hidden">
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <Activity className="w-4 h-4 text-violet-400" />
            <h3 className="text-sm font-bold text-white">
              Danh Sách DAGs Tuyển Dụng Xoay Vòng Hàng Tuần
            </h3>
          </div>
          <span className="text-xs text-slate-500 font-mono">
            Cập nhật lần cuối: {status?.last_checked ? new Date(status.last_checked).toLocaleTimeString() : 'N/A'}
          </span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-slate-950/50 text-slate-400 border-b border-slate-800">
                <th className="py-3 px-4 font-semibold">Tên DAG ID</th>
                <th className="py-3 px-4 font-semibold">Sàn Tuyển Dụng</th>
                <th className="py-3 px-4 font-semibold">Lịch Chạy Hàng Tuần</th>
                <th className="py-3 px-4 font-semibold">Trạng Thái DAG</th>
                <th className="py-3 px-4 font-semibold">Lần Chạy Gần Nhất</th>
                <th className="py-3 px-4 font-semibold">Thời Lượng</th>
                <th className="py-3 px-4 font-semibold">Thời Gian Bắt Đầu</th>
                <th className="py-3 px-4 text-right font-semibold">Thao Tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {dags.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-500">
                    {loading ? 'Đang truy vấn PostgreSQL Airflow Database...' : 'Không tìm thấy DAG nào.'}
                  </td>
                </tr>
              ) : (
                dags.map((dag) => {
                  const state = dag.last_run_state?.toLowerCase()
                  const isSuccess = state === 'success'
                  const isRunning = state === 'running'
                  const isFailed = state === 'failed'

                  return (
                    <tr key={dag.dag_id} className="hover:bg-slate-800/30 transition">
                      <td className="py-3.5 px-4 font-mono font-bold text-violet-300">
                        {dag.dag_id}
                      </td>
                      <td className="py-3.5 px-4 font-medium text-slate-200 uppercase">
                        {dag.source}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="px-2.5 py-1 rounded-md bg-slate-800 text-slate-300 font-medium">
                          {dag.schedule_day}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        {dag.is_paused ? (
                          <span className="px-2 py-0.5 rounded text-[11px] bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold">
                            TẠM DỪNG (PAUSED)
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[11px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                            HOẠT ĐỘNG (ACTIVE)
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4">
                        {isSuccess && (
                          <span className="inline-flex items-center space-x-1.5 px-2 py-0.5 rounded text-[11px] bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold">
                            <CheckCircle2 className="w-3 h-3" />
                            <span>THÀNH CÔNG</span>
                          </span>
                        )}
                        {isRunning && (
                          <span className="inline-flex items-center space-x-1.5 px-2 py-0.5 rounded text-[11px] bg-blue-500/10 text-blue-400 border border-blue-500/20 font-semibold">
                            <RefreshCw className="w-3 h-3 animate-spin" />
                            <span>ĐANG CHẠY</span>
                          </span>
                        )}
                        {isFailed && (
                          <span className="inline-flex items-center space-x-1.5 px-2 py-0.5 rounded text-[11px] bg-rose-500/10 text-rose-400 border border-rose-500/20 font-semibold">
                            <AlertCircle className="w-3 h-3" />
                            <span>THẤT BẠI</span>
                          </span>
                        )}
                        {!isSuccess && !isRunning && !isFailed && (
                          <span className="text-slate-500 text-[11px] font-mono">
                            {dag.last_run_state || 'Chưa chạy'}
                          </span>
                        )}
                      </td>
                      <td className="py-3.5 px-4 text-slate-300 font-mono">
                        {dag.duration_seconds !== null ? `${dag.duration_seconds}s` : '—'}
                      </td>
                      <td className="py-3.5 px-4 text-slate-400">
                        {dag.last_run_start ? new Date(dag.last_run_start).toLocaleString() : '—'}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <a
                          href={`http://localhost:8080/dags/${dag.dag_id}/grid`}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center space-x-1 text-slate-400 hover:text-violet-400 transition"
                        >
                          <span>Xem Grid</span>
                          <ExternalLink className="w-3 h-3" />
                        </a>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
export default AirflowMonitorPage
