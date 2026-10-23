import React, { useState, useCallback } from 'react'
import { TopBar } from './components/layout/TopBar'
import { PipelineSidebar, TabType } from './components/layout/PipelineSidebar'
import { MasterDashboardPage } from './pages/MasterDashboardPage'
import { CrawlingPage } from './pages/CrawlingPage'
import { EDAPage } from './pages/EDAPage'
import { AirflowMonitorPage } from './pages/AirflowMonitorPage'
import { PreprocessingPage } from './pages/PreprocessingPage'
import { ProcessingPage } from './pages/ProcessingPage'
import { MLMining3DPage } from './pages/MLMining3DPage'
import { CloudflareR2Page } from './pages/CloudflareR2Page'

const SIDEBAR_STORAGE_KEY = 'sidebar_collapsed'

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<TabType>('dashboard')
  const [refreshKey, setRefreshKey] = useState<number>(0)
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(SIDEBAR_STORAGE_KEY) === 'true'
    } catch {
      return false
    }
  })

  const handleRefreshAll = () => {
    setRefreshKey((k) => k + 1)
  }

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((prev) => {
      const next = !prev
      try {
        localStorage.setItem(SIDEBAR_STORAGE_KEY, String(next))
      } catch {
        /* localStorage unavailable */
      }
      return next
    })
  }, [])

  const renderContent = () => {
    switch (currentTab) {
      case 'dashboard':
        return <MasterDashboardPage key={`dash-${refreshKey}`} />
      case 'crawling':
        return <CrawlingPage key={`crawl-${refreshKey}`} />
      case 'eda':
        return <EDAPage key={`eda-${refreshKey}`} />
      case 'airflow':
        return <AirflowMonitorPage key={`airflow-${refreshKey}`} />
      case 'preprocessing':
        return <PreprocessingPage key={`prep-${refreshKey}`} />
      case 'processing':
        return <ProcessingPage key={`proc-${refreshKey}`} />
      case 'ml3d':
        return <MLMining3DPage key={`ml-${refreshKey}`} />
      case 'cloud':
        return <CloudflareR2Page key={`cloud-${refreshKey}`} />
      default:
        return <MasterDashboardPage key={`default-${refreshKey}`} />
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col text-slate-100 selection:bg-indigo-500/30 selection:text-indigo-200">
      <TopBar
        onRefreshAll={handleRefreshAll}
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={toggleSidebar}
      />
      <div className="flex flex-1">
        <PipelineSidebar
          currentTab={currentTab}
          onSelectTab={setCurrentTab}
          collapsed={sidebarCollapsed}
        />
        <main
          className={`flex-1 p-6 mx-auto w-full overflow-y-auto transition-all duration-300 ${
            sidebarCollapsed ? 'max-w-full' : 'max-w-7xl'
          }`}
        >
          {renderContent()}
        </main>
      </div>
    </div>
  )
}

export default App
