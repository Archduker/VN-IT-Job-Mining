import React, { useState } from 'react'
import { TopBar } from './components/layout/TopBar'
import { MasterDashboardPage } from './pages/MasterDashboardPage'
import { CrawlingPage } from './pages/CrawlingPage'
import { EDAPage } from './pages/EDAPage'
import { AirflowMonitorPage } from './pages/AirflowMonitorPage'
import { PreprocessingPage } from './pages/PreprocessingPage'
import { ProcessingPage } from './pages/ProcessingPage'
import { MLMining3DPage } from './pages/MLMining3DPage'
import { CloudflareR2Page } from './pages/CloudflareR2Page'
import { TabType } from './types'

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<TabType>('dashboard')
  const [refreshKey, setRefreshKey] = useState<number>(0)

  const handleRefreshAll = () => {
    setRefreshKey((k) => k + 1)
  }

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
    <div className="min-h-screen bg-[#0b1120] flex flex-col text-slate-100 selection:bg-orange-500/30 selection:text-orange-200">
      <TopBar
        currentTab={currentTab}
        onSelectTab={setCurrentTab}
        onRefreshAll={handleRefreshAll}
      />
      <main className="flex-1 p-4 lg:p-6 w-full max-w-[1600px] mx-auto overflow-y-auto">
        {renderContent()}
      </main>
    </div>
  )
}

export default App
