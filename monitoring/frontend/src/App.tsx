import React, { useState } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Sidebar } from './components/layout/Sidebar'
import { TopBar } from './components/layout/TopBar'
import { CollectionMonitorPage } from './pages/CollectionMonitorPage'
import { EDAPage } from './pages/EDAPage'
import { PreprocessingPage } from './pages/PreprocessingPage'
import { ProcessingPage } from './pages/ProcessingPage'

const TITLES: Record<string, [string, string?]> = {
  '/': ['Thu thập dữ liệu', '8 nguồn · kiểm kê raw và URL Ledger trực tiếp trên R2'],
  '/eda': ['EDA', 'Kiểm kê trường raw và phân phối từ dữ liệu staging'],
  '/preprocessing': ['Pre-processing', 'Clean → Dedup → Integration → Transformation → Normalization → Encoding, đọc báo cáo từng bước'],
  '/processing': ['Processing', 'Tách section, trích kỹ năng và tách từ (bước 07–09), đọc báo cáo từng bước'],
}

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
            <Route path="/eda" element={<EDAPage />} />
            <Route path="/preprocessing" element={<PreprocessingPage />} />
            <Route path="/processing" element={<ProcessingPage />} />
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
