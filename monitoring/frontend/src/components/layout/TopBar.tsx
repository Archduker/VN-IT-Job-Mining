import React, { useEffect, useState } from 'react'
import {
  Cloud,
  RefreshCw,
  ShieldCheck,
  Database,
  Cpu,
  PanelLeftClose,
  PanelLeftOpen,
} from 'lucide-react'
import axios from 'axios'
import { CloudHealth } from '../../types'

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
  const [loading, setLoading] = useState(false)

  const checkStatus = async () => {
    try {
      const [r2Res, afRes] = await Promise.all([
        axios.get<CloudHealth>('/api/v1/cloud/r2/status').catch(() => null),
        axios.get('/api/v1/orchestration/airflow/status').catch(() => null),
      ])
      if (r2Res?.data) setR2Health(r2Res.data)
      if (afRes?.data) {
        setAirflowRunning(
          afRes.data.scheduler?.running || afRes.data.webserver?.running
        )
      }
    } catch (e) {
      console.error(e)
    }
  }

  useEffect(() => {
    checkStatus()
    const interval = setInterval(checkStatus, 30000)
    return () => clearInterval(interval)
  }, [])

  const handleRefresh = async () => {
    setLoading(true)
    await checkStatus()
    if (onRefreshAll) onRefreshAll()
    setTimeout(() => setLoading(false), 500)
  }

  return (
    <header className="h-16 border-b border-slate-800 bg-slate-900/90 backdrop-blur-md px-6 flex items-center justify-between z-10 sticky top-0">
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
            Data Operations & Pipeline Monitor
          </p>
        </div>
      </div>

      <div className="flex items-center space-x-3">
        {/* Airflow Daemon Status Pill */}
        <div
          className={`hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-xl border text-xs font-medium transition-colors ${
            airflowRunning
              ? 'bg-indigo-950/40 border-indigo-500/30 text-indigo-300'
              : 'bg-slate-800/60 border-slate-700/60 text-slate-400'
          }`}
        >
          <Cpu className="w-4 h-4 text-indigo-400" />
          <span>Airflow:</span>
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

        {/* Golden Dataset Tag */}
        <div className="hidden lg:flex items-center space-x-1.5 px-3 py-1.5 rounded-xl bg-slate-800/80 border border-slate-700/60 text-xs">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span className="text-slate-300">Dataset:</span>
          <span className="font-semibold text-emerald-400">Golden Master</span>
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
