import React, { useEffect, useState, useRef } from 'react'
import {
  RefreshCw,
  ShieldCheck,
  Bell,
  AlertTriangle,
  AlertCircle,
  Info,
  Check,
  ExternalLink,
} from 'lucide-react'
import axios from 'axios'
import { Link } from 'react-router-dom'
import { AirflowStatusResponse, CloudHealth, AlertSummary, AlertItem } from '../../types'

interface TopBarProps {
  title: string
  subtitle?: string
  onRefreshAll?: () => void
}

const TONES = {
  ok: { dot: 'bg-[#1F8A5B]', halo: 'shadow-[0_0_0_4px_#DDF1E6]', fg: 'text-state-done-fg' },
  run: { dot: 'bg-brand-500', halo: 'shadow-[0_0_0_4px_#E7E4FC]', fg: 'text-state-running-fg' },
  off: { dot: 'bg-[#C2362F]', halo: 'shadow-[0_0_0_4px_#FBE3E1]', fg: 'text-state-fail-fg' },
}

const ConnectionCard: React.FC<{
  name: string
  status: string
  tone: keyof typeof TONES
  sub: string
  rows: [string, string][]
}> = ({ name, status, tone, sub, rows }) => {
  const meta = TONES[tone]
  return (
    <button
      type="button"
      aria-label={`${name}: ${status}, ${sub}`}
      className="group relative flex items-center gap-3 min-h-[52px] px-3.5 py-2 rounded-xl bg-white border border-line-strong text-left cursor-default"
    >
      <span className={`w-2.5 h-2.5 rounded-full ${meta.dot} ${meta.halo}`} />
      <span className="flex flex-col leading-snug">
        <span className="font-semibold text-ink">
          {name} · <span className={meta.fg}>{status}</span>
        </span>
        <span className="text-xs text-ink-muted max-w-[220px] truncate">{sub}</span>
      </span>
      <span
        role="tooltip"
        className="hidden group-hover:block group-focus:block absolute top-full right-0 mt-2 w-72 bg-ink text-slate-100 rounded-xl px-3.5 py-3 z-30 shadow-xl pointer-events-none"
      >
        <span className="block font-semibold mb-1.5">{name}</span>
        {rows.map(([k, v]) => (
          <span key={k} className="flex justify-between gap-2.5 text-[13px] leading-loose">
            <span className="text-nav-text">{k}</span>
            <span className="font-semibold text-right">{v}</span>
          </span>
        ))}
      </span>
    </button>
  )
}

export const TopBar: React.FC<TopBarProps> = ({
  title,
  subtitle,
  onRefreshAll,
}) => {
  const [r2Health, setR2Health] = useState<CloudHealth | null>(null)
  const [airflow, setAirflow] = useState<AirflowStatusResponse | null>(null)
  const [alertSummary, setAlertSummary] = useState<AlertSummary | null>(null)
  const [showAlertDrawer, setShowAlertDrawer] = useState<boolean>(false)
  const [loading, setLoading] = useState<boolean>(false)
  const drawerRef = useRef<HTMLDivElement>(null)

  const checkStatus = async () => {
    try {
      const [r2Res, afRes, alertRes] = await Promise.all([
        axios.get<CloudHealth>('/api/v1/cloud/r2/status').catch(() => null),
        axios.get<AirflowStatusResponse>('/api/v1/orchestration/airflow/status').catch(() => null),
        axios.get<AlertSummary>('/api/v1/alerts').catch(() => null),
      ])
      if (r2Res?.data) setR2Health(r2Res.data)
      if (afRes?.data) setAirflow(afRes.data)
      if (alertRes?.data) {
        setAlertSummary(alertRes.data)
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    checkStatus()
    const interval = setInterval(checkStatus, 20000)
    return () => clearInterval(interval)
  }, [])

  // Close drawer when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (drawerRef.current && !drawerRef.current.contains(event.target as Node)) {
        setShowAlertDrawer(false)
      }
    }
    if (showAlertDrawer) {
      document.addEventListener('mousedown', handleClickOutside)
    }
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showAlertDrawer])

  const handleRefresh = async () => {
    setLoading(true)
    await checkStatus()
    if (onRefreshAll) onRefreshAll()
    setTimeout(() => setLoading(false), 500)
  }

  const handleAcknowledge = async (alertId: string) => {
    try {
      await axios.post(`/api/v1/alerts/${alertId}/acknowledge`)
      setAlertSummary((prev) => {
        if (!prev) return null
        const filtered = prev.alerts.filter((a) => a.id !== alertId)
        return {
          ...prev,
          total_alerts: filtered.length,
          critical_count: filtered.filter((a) => a.severity === 'CRITICAL').length,
          warning_count: filtered.filter((a) => a.severity === 'WARNING').length,
          alerts: filtered,
        }
      })
    } catch (e) {
      console.error('Failed to acknowledge alert', e)
    }
  }

  const activeAlertCount = alertSummary ? alertSummary.alerts.length : 0
  const hasCritical = alertSummary ? alertSummary.critical_count > 0 : false

  return (
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div className="flex flex-col gap-1 min-w-0">
        <h1 className="m-0 text-[28px] font-bold tracking-tight text-ink">{title}</h1>
        {subtitle && <p className="m-0 text-ink-muted">{subtitle}</p>}
      </div>

      <div className="flex flex-wrap items-center gap-2.5 relative">
        <ConnectionCard
          name="Cloudflare R2"
          status={r2Health?.connected ? 'Đã kết nối' : r2Health?.configured ? 'Mất kết nối' : 'Chưa cấu hình'}
          tone={r2Health?.connected ? 'ok' : 'off'}
          sub={r2Health?.connected ? `Độ trễ ${r2Health.latency_ms} ms` : r2Health?.message ?? 'Đang kiểm tra…'}
          rows={[
            ['Bucket', r2Health?.bucket ?? '—'],
            ['Độ trễ API', r2Health?.latency_ms !== undefined ? `${r2Health.latency_ms} ms` : '—'],
          ]}
        />
        <ConnectionCard
          name="Airflow"
          status={airflow?.scheduler.running ? 'Đang chạy' : 'Đã dừng'}
          tone={airflow?.scheduler.running ? 'run' : 'off'}
          sub={airflow?.database.connected ? `${airflow.active_dags_count} DAG` : 'Chưa kết nối PostgreSQL'}
          rows={[
            ['Scheduler', airflow?.scheduler.running ? `PID ${airflow.scheduler.pid}` : 'Dừng'],
            ['Webserver', airflow?.webserver.running ? 'Cổng 8080' : 'Dừng'],
            ['PostgreSQL', airflow?.database.connected ? 'Đã kết nối' : 'Mất kết nối'],
          ]}
        />

        {/* Integrated Alert Bell Button */}
        <div className="relative">
          <button
            onClick={() => setShowAlertDrawer((v) => !v)}
            className={`p-2 rounded-xl border transition-all relative ${
              hasCritical
                ? 'bg-rose-950/60 border-rose-500/50 text-rose-300 hover:bg-rose-900/60'
                : activeAlertCount > 0
                ? 'bg-amber-950/60 border-amber-500/50 text-amber-300 hover:bg-amber-900/60'
                : 'bg-slate-800/80 hover:bg-slate-700 border-slate-700 text-slate-300'
            }`}
            title="Trung tâm cảnh báo sự cố"
          >
            <Bell className={`w-4 h-4 ${hasCritical ? 'animate-bounce text-rose-400' : ''}`} />
            {activeAlertCount > 0 && (
              <span
                className={`absolute -top-1.5 -right-1.5 text-[10px] font-bold px-1.5 py-0.5 rounded-full border shadow-sm ${
                  hasCritical
                    ? 'bg-rose-600 text-white border-rose-400'
                    : 'bg-amber-500 text-slate-950 border-amber-300'
                }`}
              >
                {activeAlertCount}
              </span>
            )}
          </button>

          {/* Alert Popover Drawer */}
          {showAlertDrawer && (
            <div
              ref={drawerRef}
              className="absolute right-0 mt-3 w-96 max-w-[90vw] rounded-2xl bg-slate-900/95 border border-slate-700/80 shadow-2xl backdrop-blur-xl p-4 text-xs z-50"
            >
              <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
                <div className="flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <h3 className="font-bold text-slate-100 text-sm">Trung Tâm Cảnh Báo</h3>
                </div>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                  {activeAlertCount} sự cố hoạt động
                </span>
              </div>

              <div className="max-h-80 overflow-y-auto space-x-0 space-y-2.5 pr-1">
                {activeAlertCount === 0 ? (
                  <div className="text-center py-6 text-slate-400 space-y-1">
                    <ShieldCheck className="w-8 h-8 text-emerald-400 mx-auto" />
                    <p className="font-semibold text-slate-200">Hệ thống an toàn 100%</p>
                    <p className="text-[11px]">Không có cảnh báo hay sự cố nào đang kích hoạt.</p>
                  </div>
                ) : (
                  alertSummary?.alerts.map((alert: AlertItem) => {
                    const isCrit = alert.severity === 'CRITICAL'
                    const isWarn = alert.severity === 'WARNING'
                    return (
                      <div
                        key={alert.id}
                        className={`p-3 rounded-xl border flex flex-col space-y-1.5 transition-all ${
                          isCrit
                            ? 'bg-rose-950/40 border-rose-500/40 text-rose-200'
                            : isWarn
                            ? 'bg-amber-950/40 border-amber-500/40 text-amber-200'
                            : 'bg-blue-950/40 border-blue-500/40 text-blue-200'
                        }`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-center space-x-1.5">
                            {isCrit ? (
                              <AlertCircle className="w-3.5 h-3.5 text-rose-400 shrink-0" />
                            ) : isWarn ? (
                              <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                            ) : (
                              <Info className="w-3.5 h-3.5 text-blue-400 shrink-0" />
                            )}
                            <span className="font-bold text-slate-100 text-[11px] leading-tight">
                              {alert.title}
                            </span>
                          </div>
                          <span
                            className={`text-[9px] uppercase font-bold px-1.5 py-0.5 rounded ${
                              isCrit
                                ? 'bg-rose-900/80 text-rose-300 border border-rose-700'
                                : 'bg-amber-900/80 text-amber-300 border border-amber-700'
                            }`}
                          >
                            {alert.severity}
                          </span>
                        </div>
                        <p className="text-[11px] text-slate-300 leading-relaxed">
                          {alert.message}
                        </p>
                        <div className="flex items-center justify-between pt-1 border-t border-slate-800/60 text-[10px] text-slate-400">
                          {alert.action_url ? (
                            <Link to={alert.action_url} onClick={() => setShowAlertDrawer(false)} className="font-semibold text-brand-600 hover:underline">
                              Mở trang liên quan
                            </Link>
                          ) : (
                            <span>Phân hệ: {alert.category}</span>
                          )}
                          <button
                            onClick={() => handleAcknowledge(alert.id)}
                            className="flex items-center space-x-1 text-slate-400 hover:text-emerald-300 transition-colors"
                            title="Ẩn cảnh báo này"
                          >
                            <Check className="w-3 h-3" />
                            <span>Đã xử lý</span>
                          </button>
                        </div>
                      </div>
                    )
                  })
                )}
              </div>
            </div>
          )}
        </div>

        {/* Refresh button */}
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-slate-100 transition-colors"
          title="Refresh all data"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
        </button>
      </div>
    </header>
  )
}
