import React, { useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Sidebar } from './components/layout/Sidebar'
import { TopBar } from './components/layout/TopBar'
import { SampleDataNotice } from './components/ui'
import { AirflowMonitorPage } from './pages/AirflowMonitorPage'
import { CloudflareR2Page } from './pages/CloudflareR2Page'
import { CollectionMonitorPage } from './pages/CollectionMonitorPage'
import { CrawlingPage } from './pages/CrawlingPage'
import { EDAPage } from './pages/EDAPage'
import { MasterDashboardPage } from './pages/MasterDashboardPage'
import { MLMining3DPage } from './pages/MLMining3DPage'
import { PreprocessingPage } from './pages/PreprocessingPage'
import { ProcessingPage } from './pages/ProcessingPage'
import { RawReportPage } from './pages/RawReportPage'

const TITLES: Record<string, [string, string?]> = {
  '/': ['Thu thập dữ liệu', '8 nguồn · cập nhật theo URL Ledger và Airflow'],
  '/raw': ['Báo cáo theo nguồn', 'Chọn một nguồn để xem 8 feature target, vấn đề cần xử lý, phân tích đơn biến và một bản ghi raw.'],
  '/crawling': ['Cấu hình cào'],
  '/airflow': ['Airflow'],
  '/cloud': ['Cloudflare R2'],
  '/eda': ['EDA'],
  '/preprocessing': ['Pre-processing'],
  '/processing': ['Processing'],
  '/master': ['Master Dashboard'],
  '/ml3d': ['ML 3D'],
}

const withNotice = (page: React.ReactElement): React.ReactElement => (
  <>
    <SampleDataNotice />
    {page}
  </>
)

const Shell: React.FC = () => {
  const { pathname } = useLocation()
  const [refreshKey, setRefreshKey] = useState(0)
  const [title, subtitle] = TITLES[pathname] ?? ['JobCrawl']

  return (
    <div className="min-h-screen bg-ground text-ink flex flex-col lg:flex-row">
      <Sidebar />
      <main className="flex-1 min-w-0 px-4 sm:px-8 pt-7 pb-12 flex flex-col gap-6">
        <TopBar title={title} subtitle={subtitle} onRefreshAll={() => setRefreshKey((k) => k + 1)} />
        <div key={refreshKey} className="min-w-0">
          <Routes>
            <Route path="/" element={<CollectionMonitorPage />} />
            <Route path="/raw" element={<RawReportPage />} />
            <Route path="/crawling" element={<CrawlingPage />} />
            <Route path="/airflow" element={<AirflowMonitorPage />} />
            <Route path="/cloud" element={<CloudflareR2Page />} />
            <Route path="/eda" element={withNotice(<EDAPage />)} />
            <Route path="/preprocessing" element={withNotice(<PreprocessingPage />)} />
            <Route path="/processing" element={withNotice(<ProcessingPage />)} />
            <Route path="/master" element={withNotice(<MasterDashboardPage />)} />
            <Route path="/ml3d" element={withNotice(<MLMining3DPage />)} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </main>
    </div>
  )
}

export const App: React.FC = () => (
  <BrowserRouter>
    <Shell />
  </BrowserRouter>
)

export default App
