import React from 'react'
import {
  LayoutDashboard,
  Radio,
  BarChart3,
  Cpu,
  FileCheck2,
  GitMerge,
  Box,
  Cloud,
  ArrowRight,
  ShieldCheck,
} from 'lucide-react'

export type TabType =
  | 'dashboard'
  | 'crawling'
  | 'eda'
  | 'airflow'
  | 'preprocessing'
  | 'processing'
  | 'ml3d'
  | 'cloud'

interface PipelineSidebarProps {
  currentTab: TabType
  onSelectTab: (tab: TabType) => void
  collapsed?: boolean
}

export const PipelineSidebar: React.FC<PipelineSidebarProps> = ({
  currentTab,
  onSelectTab,
  collapsed = false,
}) => {
  const navSections = [
    {
      group: 'EXECUTIVE COMMAND',
      items: [
        {
          id: 'dashboard' as TabType,
          label: 'Master Dashboard',
          sublabel: 'api/Dashboard (Golden Dataset)',
          icon: LayoutDashboard,
          badge: 'Golden v1.0',
        },
      ],
    },
    {
      group: 'PHASE 1: COLLECTION & EDA',
      items: [
        {
          id: 'crawling' as TabType,
          label: 'Crawling Operations',
          sublabel: '8 Portals & URL Ledger',
          icon: Radio,
        },
        {
          id: 'eda' as TabType,
          label: 'EDA Intelligence',
          sublabel: 'Field Inventory, Missing & 2D Charts',
          icon: BarChart3,
        },
      ],
    },
    {
      group: 'AUTOMATED ORCHESTRATION',
      items: [
        {
          id: 'airflow' as TabType,
          label: 'Airflow Pipeline',
          sublabel: 'Scheduler Daemon & 7 Rotation DAGs',
          icon: Cpu,
        },
      ],
    },
    {
      group: 'PHASE 2 & 3: SANITIZATION & INTEGRATION',
      items: [
        {
          id: 'preprocessing' as TabType,
          label: 'Pre-processing',
          sublabel: 'Regex Rules & Null Reduction',
          icon: FileCheck2,
        },
        {
          id: 'processing' as TabType,
          label: 'Processing & Dedup',
          sublabel: 'Target Schema & Entity Resolution',
          icon: GitMerge,
        },
      ],
    },
    {
      group: 'ADVANCED AI & CLOUD',
      items: [
        {
          id: 'ml3d' as TabType,
          label: 'AI/ML 3D Spatial Lab',
          sublabel: 'UMAP 3D & Isolation Forest',
          icon: Box,
        },
        {
          id: 'cloud' as TabType,
          label: 'Cloudflare R2 Sync',
          sublabel: 'Lakehouse 4-Layer & Diff Engine',
          icon: Cloud,
        },
      ],
    },
  ]

  return (
    <aside
      className={`bg-slate-900/90 backdrop-blur-md border-r border-slate-800/80 flex flex-col justify-between shrink-0 h-[calc(100vh-4rem)] sticky top-16 select-none overflow-hidden transition-all duration-300 ${
        collapsed
          ? 'w-0 opacity-0 pointer-events-none border-r-0'
          : 'w-72 opacity-100'
      }`}
    >
      <div className="p-3.5 space-y-5 overflow-y-auto">
        {navSections.map((sec, idx) => (
          <div key={idx} className="space-y-1">
            <div className="text-[10px] font-bold uppercase tracking-wider text-slate-400 px-3 py-1">
              {sec.group}
            </div>
            <nav className="space-y-1">
              {sec.items.map((item) => {
                const Icon = item.icon
                const active = currentTab === item.id
                return (
                  <button
                    key={item.id}
                    onClick={() => onSelectTab(item.id)}
                    className={`w-full flex items-center space-x-3 px-3 py-2 rounded-xl text-left transition-all ${
                      active
                        ? 'bg-gradient-to-r from-indigo-600 to-indigo-700 text-white shadow-md shadow-indigo-600/25 border border-indigo-400/30'
                        : 'text-slate-300 hover:bg-slate-800/70 hover:text-white'
                    }`}
                  >
                    <Icon
                      className={`w-4 h-4 shrink-0 ${
                        active ? 'text-white' : 'text-slate-400'
                      }`}
                    />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-xs truncate">
                          {item.label}
                        </span>
                        {item.badge && !active && (
                          <span className="text-[10px] px-1.5 py-0.2 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono">
                            {item.badge}
                          </span>
                        )}
                        {active && (
                          <ArrowRight className="w-3.5 h-3.5 shrink-0 opacity-80" />
                        )}
                      </div>
                      <p
                        className={`text-[11px] truncate ${
                          active ? 'text-indigo-100' : 'text-slate-400'
                        }`}
                      >
                        {item.sublabel}
                      </p>
                    </div>
                  </button>
                )
              })}
            </nav>
          </div>
        ))}

        {/* Visual mission reminder */}
        <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800/80 space-y-1.5 text-xs">
          <div className="flex items-center space-x-1.5 text-indigo-400 font-bold text-[11px]">
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Zero-Auth Observatory</span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Pure engineering monitor. Reflects real-time data quality across every pipeline stage.
          </p>
        </div>
      </div>

      <div className="p-3 border-t border-slate-800/80 text-[11px] text-slate-400 flex items-center justify-between bg-slate-950/40">
        <span>Cloud: Cloudflare R2</span>
        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 font-mono">
          vn-it-jobs
        </span>
      </div>
    </aside>
  )
}
