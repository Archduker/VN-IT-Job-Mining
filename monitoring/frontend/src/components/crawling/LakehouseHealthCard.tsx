import { Cloud, UploadCloud, RefreshCw, Sparkles, Activity } from 'lucide-react'

import type { useCrawlingState } from './useCrawlingState'
type Props = Pick<ReturnType<typeof useCrawlingState>, 'handleSyncSourceToCloud' | 'handleSyncAllToCloud' | 'activeSource' | 'selectedSource' | 'engine' | 'cloudSync' | 'loadingCloudSync' | 'isSyncingSource' | 'isSyncingAll'>
export function LakehouseHealthCard({ handleSyncSourceToCloud, handleSyncAllToCloud, activeSource, selectedSource, engine, cloudSync, loadingCloudSync, isSyncingSource, isSyncingAll }: Props) {
 return <>
      {/* 1 & 2: DUAL STATUS COCKPIT */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 1. Live Crawler Runtime Status */}
        <div className="p-5 rounded-2xl bg-panel border border-line space-y-3">
          <div className="flex items-center space-x-2 text-xs font-bold text-ink-soft uppercase tracking-wider">
            <Activity className="w-4 h-4 text-indigo-400" />
            <span>Live Crawler Runtime Status</span>
          </div>
          <div className="flex items-center space-x-3">
            <span
              className={`w-4 h-4 rounded-full shrink-0 ${
                activeSource ? 'bg-emerald-400 animate-pulse' : 'bg-ground'
              }`}
            />
            <span className={`text-2xl font-extrabold ${activeSource ? 'text-emerald-400' : 'text-ink-soft'}`}>
              {activeSource ? 'ACTIVE' : 'IDLE — READY'}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 text-xs">
            <div>
              <span className="text-ink-soft">Active Source:</span>
              <span className="ml-2 text-ink font-bold">{activeSource ? activeSource.name : 'None'}</span>
            </div>
            <div>
              <span className="text-ink-soft">Engine:</span>
              <span className="ml-2 text-indigo-300 font-mono">{activeSource?.engine || 'N/A'}</span>
            </div>
          </div>
        </div>

        {/* 2. Cloudflare R2 Lakehouse Metrics */}
        <div className="p-5 rounded-2xl bg-gradient-to-r from-slate-900 via-slate-900 to-indigo-950/40 border border-line space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2 text-xs font-bold text-ink-soft uppercase tracking-wider">
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
              <p className="text-xs text-ink-soft mb-1">Total Stored Objects</p>
              <p className="text-3xl font-extrabold font-mono text-ink">{cloudSync?.total_cloud_raw?.toLocaleString() ?? '—'}</p>
            </div>
            <div>
              <p className="text-xs text-ink-soft mb-1">Sync Health</p>
              <p className="text-3xl font-extrabold font-mono text-emerald-400">{cloudSync?.overall_sync_pct == null ? '—' : `${cloudSync.overall_sync_pct}%`}</p>
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
              className="flex items-center space-x-1.5 px-3 py-2 rounded-xl bg-panel hover:bg-ground border border-line text-ink text-xs font-semibold transition"
            >
              {isSyncingAll ? <RefreshCw className="w-3.5 h-3.5 animate-spin text-indigo-400" /> : <Sparkles className="w-3.5 h-3.5 text-amber-400" />}
              <span>Sync All 8 Portals</span>
            </button>
          </div>
        </div>
      </div>


 </>
}
