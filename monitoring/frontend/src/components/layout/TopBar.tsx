import React, { useEffect, useState, useRef } from 'react'
import {
  Cloud,
  RefreshCw,
  ShieldCheck,
  Cpu,
  Bell,
  AlertTriangle,
  AlertCircle,
  Info,
  Check,
  Sun,
  User,
  Zap,
} from 'lucide-react'
import axios from 'axios'
import { CloudHealth, AlertSummary, AlertItem, TabType } from '../../types'

interface TopBarProps {
  currentTab: TabType
  onSelectTab: (tab: TabType) => void
  onRefreshAll?: () => void
  sidebarCollapsed?: boolean
  onToggleSidebar?: () => void
}

const PIPELINE_PROCESSES: { id: TabType; label: string }[] = [
  { id: 'dashboard', label: 'Dashboard' },
  { id: 'crawling', label: 'Collection' },
  { id: 'airflow', label: 'Airflow Pipeline' },
  { id: 'preprocessing', label: 'Pre-processing' },
  { id: 'processing', label: 'Processing & Dedup' },
  { id: 'eda', label: 'EDA Intelligence' },
  { id: 'ml3d', label: 'AI/ML 3D Lab' },
  { id: 'cloud', label: 'Cloudflare R2' },
]

export const TopBar: React.FC<TopBarProps> = ({
  currentTab,
  onSelectTab,
  onRefreshAll,
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

  // Close alert drawer when clicking outside
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
    <header className="h-16 border-b border-slate-800 bg-[#0f172a] px-4 lg:px-6 flex items-center justify-between z-30 sticky top-0 shadow-md">
      {/* Left: Brand Identity */}
      <div className="flex items-center space-x-3 shrink-0">
        <div className="flex items-center space-x-2.5 cursor-pointer" onClick={() => onSelectTab('dashboard')}>
          <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-amber-500 via-orange-500 to-amber-600 flex items-center justify-center shadow-lg shadow-orange-500/20">
            <Zap className="w-5 h-5 text-slate-950 font-bold" />
          </div>
          <div className="hidden sm:block">
            <div className="flex items-center space-x-1.5">
              <span className="text-sm font-extrabold text-white tracking-tight">
                VN-IT Mining
              </span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-orange-500/10 text-orange-400 border border-orange-500/20 font-bold uppercase tracking-wider">
                AI
              </span>
            </div>
            <p className="text-[10px] text-slate-400 -mt-0.5">Central Observatory</p>
          </div>
        </div>
      </div>

      {/* Middle: Horizontal Pipeline Processes (Thanh ngang các tiến trình) */}
      <nav className="flex items-center space-x-1 md:space-x-2 overflow-x-auto no-scrollbar mx-4 py-1">
        {PIPELINE_PROCESSES.map((proc) => {
          const isActive = currentTab === proc.id
          return (
            <button
              key={proc.id}
              onClick={() => onSelectTab(proc.id)}
              className={`px-3 py-1.5 text-xs md:text-sm font-medium transition-all duration-150 rounded-lg whitespace-nowrap relative ${
                isActive
                  ? 'text-[#f97316] font-bold after:content-[""] after:absolute after:bottom-0 after:left-3 after:right-3 after:h-0.5 after:bg-[#f97316]'
                  : 'text-slate-300 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              {proc.label}
            </button>
          )
        })}
      </nav>

      {/* Right: Quick Telemetry + Actions + Theme + Alert Bell + Avatar */}
      <div className="flex items-center space-x-2.5 sm:space-x-3 shrink-0 relative">
        {/* Airflow Status Pill */}
        <div
          className={`hidden xl:flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium ${
            airflowRunning
              ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
              : 'bg-slate-800/60 border-slate-700/60 text-slate-400'
          }`}
          title="Airflow Daemon Status"
        >
          <Cpu className="w-3.5 h-3.5 text-indigo-400" />
          <span className="text-[11px]">Airflow:</span>
          {airflowRunning ? (
            <span className="text-[10px] text-emerald-400 font-bold">ONLINE</span>
          ) : (
            <span className="text-[10px] text-slate-400">OFFLINE</span>
          )}
        </div>

        {/* Cloudflare R2 Pill */}
        <div
          className={`hidden xl:flex items-center space-x-1.5 px-2.5 py-1 rounded-lg border text-xs font-medium ${
            r2Health?.connected
              ? 'bg-emerald-950/40 border-emerald-500/30 text-emerald-300'
              : 'bg-amber-950/40 border-amber-500/30 text-amber-300'
          }`}
          title="Cloudflare R2 Bucket Health"
        >
          <Cloud className="w-3.5 h-3.5 text-orange-400" />
          <span className="text-[11px]">R2:</span>
          {r2Health?.connected ? (
            <span className="text-[10px] text-emerald-400 font-bold">{r2Health.latency_ms}ms</span>
          ) : (
            <span className="text-[10px] text-amber-400">DISCONNECTED</span>
          )}
        </div>

        {/* Theme Toggle Button (matching sun icon in images) */}
        <button
          className="p-2 rounded-xl text-slate-400 hover:text-amber-400 hover:bg-slate-800 transition-colors"
          title="Light / Dark mode"
        >
          <Sun className="w-4 h-4" />
        </button>

        {/* Integrated Alert Bell Button with Notification Count Badge */}
        <div className="relative">
          <button
            onClick={() => setShowAlertDrawer((v) => !v)}
            className={`p-2 rounded-xl border transition-all relative ${
              hasCritical
                ? 'bg-rose-950/60 border-rose-500/50 text-rose-300 hover:bg-rose-900/60'
                : activeAlertCount > 0
                ? 'bg-slate-800 border-slate-700 text-slate-200 hover:bg-slate-700'
                : 'bg-slate-800/80 hover:bg-slate-700 border-slate-700 text-slate-300'
            }`}
            title="Alert Notifications"
          >
            <Bell className={`w-4 h-4 ${hasCritical ? 'animate-bounce text-rose-400' : ''}`} />
            {activeAlertCount > 0 && (
              <span className="absolute -top-1 -right-1 text-[10px] font-bold px-1.5 py-0.2 rounded-full bg-[#f97316] text-white border border-slate-900 shadow-sm leading-tight">
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
                  <h3 className="font-bold text-white text-sm">System Alerts & Logs</h3>
                </div>
                <span className="text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                  {activeAlertCount} active
                </span>
              </div>

              <div className="max-h-80 overflow-y-auto space-y-2.5 pr-1">
                {activeAlertCount === 0 ? (
                  <div className="text-center py-6 text-slate-400 space-y-1">
                    <ShieldCheck className="w-8 h-8 text-emerald-400 mx-auto" />
                    <p className="font-semibold text-slate-200">All Systems Nominal</p>
                    <p className="text-[11px]">No active critical or warning alerts detected.</p>
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
                          <span>Module: {alert.category}</span>
                          <button
                            onClick={() => handleAcknowledge(alert.id)}
                            className="flex items-center space-x-1 text-slate-400 hover:text-emerald-300 transition-colors"
                            title="Acknowledge alert"
                          >
                            <Check className="w-3 h-3" />
                            <span>Dismiss</span>
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

        {/* User Profile Avatar (matching the circular avatar in Image 1 & 2) */}
        <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-orange-400 to-amber-500 p-0.5 shadow cursor-pointer" title="Zero-Auth Admin Session">
          <div className="w-full h-full rounded-full bg-slate-900 flex items-center justify-center text-amber-400 font-bold text-xs">
            <User className="w-4 h-4 text-orange-400" />
          </div>
        </div>

        {/* Global Refresh button */}
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="p-2 rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 hover:text-white transition-colors"
          title="Refresh telemetry"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-orange-400' : ''}`} />
        </button>
      </div>
    </header>
  )
}
