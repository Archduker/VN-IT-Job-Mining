import React, { useEffect, useState, useRef } from 'react'
import {
  Cloud,
  RefreshCw,
  ShieldCheck,
  Database,
  Cpu,
  PanelLeftClose,
  PanelLeftOpen,
  Bell,
  AlertTriangle,
  AlertCircle,
  Info,
  Check,
  ExternalLink,
} from 'lucide-react'
import axios from 'axios'
import { CloudHealth, AlertSummary, AlertItem } from '../../types'

interface TopBarProps {
  onRefreshAll?: () => void
  sidebarCollapsed?: boolean
  onToggleSidebar?: () => void
}

export const TopBar: React.FC<TopBarProps> = ({
  onRefreshAll,
  sidebarCollapsed = false,
  onToggleSidebar,
}) => {
  const [r2Health, setR2Health] = useState<CloudHealth | null>(null)
  const [airflowRunning, setAirflowRunning] = useState<boolean>(false)
  const [alertSummary, setAlertSummary] = useState<AlertSummary | null>(null)
  const [showAlertDrawer, setShowAlertDrawer] = useState<boolean>(false)
  const [loading, setLoading] = useState<boolean>(false)
  const drawerRef = useRef<HTMLDivElement>(null)

  const checkStatus = async () => {
    try {
      const [r2Res, afRes, alertRes] = await Promise.all([
        axios.get<CloudHealth>('/api/v1/cloud/r2/status').catch(() => null),
        axios.get('/api/v1/orchestration/airflow/status').catch(() => null),
        axios.get<AlertSummary>('/api/v1/alerts').catch(() => null),
      ])
      if (r2Res?.data) setR2Health(r2Res.data)
      if (afRes?.data) {
        setAirflowRunning(
          afRes.data.scheduler?.running || afRes.data.webserver?.running
        )
      }
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
    <header className="h-16 border-b border-slate-800 bg-slate-900/90 backdrop-blur-md px-6 flex items-center justify-between z-20 sticky top-0">
      <div className="flex items-center space-x-3">
        {/* Sidebar Toggle Button */}
        {onToggleSidebar && (
          <button
            onClick={onToggleSidebar}
            className="p-2 rounded-xl bg-slate-800/80 hover:bg-slate-700 border border-slate-700/60 text-slate-300 hover:text-white transition-colors"
            title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {sidebarCollapsed ? (
              <PanelLeftOpen className="w-4 h-4" />
            ) : (
              <PanelLeftClose className="w-4 h-4" />
            )}
          </button>
        )}

        <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 via-indigo-500 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/20">
          <Database className="w-5 h-5 text-white" />
        </div>
        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-sm font-bold text-white tracking-wide">
              VN-IT-Job-Mining
            </h1>
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-semibold uppercase">
              Central Observatory
            </span>
          </div>
          <p className="text-[11px] text-slate-400">
            Data Operations & Pipeline Monitor (R2 Cloud Native)
          </p>
        </div>
      </div>

      <div className="flex items-center space-x-3 relative">
        {/* Airflow Daemon Status Pill */}
        <div
          className={`hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-xl border text-xs font-medium transition-colors ${
            airflowRunning
              ? 'bg-indigo-950/40 border-indigo-500/30 text-indigo-300'
              : 'bg-slate-800/60 border-slate-700/60 text-slate-400'
          }`}
        >
          <Cpu className="w-4 h-4 text-indigo-400" />
          <span>Airflow (PostgreSQL):</span>
          {airflowRunning ? (
            <span className="flex items-center space-x-1.5 font-semibold text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>ONLINE</span>
            </span>
          ) : (
            <span className="text-slate-400">STOPPED</span>
          )}
        </div>

        {/* Cloudflare R2 Connection Pill */}
        <div
          className={`flex items-center space-x-2 px-3 py-1.5 rounded-xl border text-xs font-medium transition-colors ${
            r2Health?.connected
              ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
              : 'bg-amber-950/40 border-amber-500/30 text-amber-300'
          }`}
        >
          <Cloud className="w-4 h-4" />
          <span className="hidden md:inline">Cloudflare R2:</span>
          {r2Health?.connected ? (
            <span className="flex items-center space-x-1.5 font-semibold text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <span>{r2Health.latency_ms}ms</span>
            </span>
          ) : (
            <span className="text-amber-400 font-semibold">Disconnected</span>
          )}
        </div>

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
                className={`absolute -top-1.5 -right-1.5 text-[10px] font-bold px-1.5 py-0.2 rounded-full border shadow-sm ${
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
              className="absolute right-0 mt-3 w-96 max-w-[90vw] rounded-2xl bg-slate-900/95 border border-slate-700/80 shadow-2xl backdrop-blur-xl p-4 text-xs z-50 animate-in fade-in slide-in-from-top-2 duration-200"
            >
              <div className="flex items-center justify-between border-b border-slate-800 pb-3 mb-3">
                <div className="flex items-center space-x-2">
                  <AlertTriangle className="w-4 h-4 text-amber-400" />
                  <h3 className="font-bold text-white text-sm">Trung Tâm Cảnh Báo</h3>
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
                          <span>Phân hệ: {alert.category}</span>
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
          className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-white transition-colors"
          title="Refresh all data"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-indigo-400' : ''}`} />
        </button>
      </div>
    </header>
  )
}
