import React, { useEffect, useState, useRef } from 'react'
import axios from 'axios'
import Plotly from 'plotly.js-dist-min'
import { Box, Sparkles, ShieldAlert, RotateCcw } from 'lucide-react'
import { Spatial3DData } from '../types'

export const MLMining3DPage: React.FC = () => {
  const [modelType, setModelType] = useState<'umap' | 'isolation-forest'>('umap')
  const [data, setData] = useState<Spatial3DData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const plotContainerRef = useRef<HTMLDivElement>(null)

  const fetchData = async (type: 'umap' | 'isolation-forest') => {
    try {
      setLoading(true)
      const res = await axios.get<Spatial3DData>(`/api/v1/mining/spatial-3d/${type}`)
      setData(res.data)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData(modelType)
  }, [modelType])

  useEffect(() => {
    if (!data || !plotContainerRef.current) return

    const { points, decision_boundary_mesh } = data

    // Nhóm điểm theo Job Family
    const traces: any[] = []
    const familyMap: Record<string, { x: number[]; y: number[]; z: number[]; text: string[] }> = {}

    points.forEach((pt) => {
      const fam = pt.is_anomaly ? '⚠️ Tin Rác / Anomaly' : pt.job_family
      if (!familyMap[fam]) {
        familyMap[fam] = { x: [], y: [], z: [], text: [] }
      }
      familyMap[fam].x.push(pt.x)
      familyMap[fam].y.push(pt.y)
      familyMap[fam].z.push(pt.z)
      familyMap[fam].text.push(
        `<b>${pt.title}</b><br>Công ty: ${pt.company}<br>Lương: ${pt.salary_vnd || 'Thỏa thuận'}M VND<br>Kỹ năng: ${pt.skills.join(', ')}`
      )
    })

    const colorPalette: Record<string, string> = {
      'Backend & Cloud': '#6366f1',
      'Data & AI': '#10b981',
      'Frontend & Mobile': '#06b6d4',
      'DevOps & Security': '#f59e0b',
      '⚠️ Tin Rác / Anomaly': '#f43f5e',
    }

    Object.entries(familyMap).forEach(([fam, vals]) => {
      traces.push({
        type: 'scatter3d',
        mode: 'markers',
        name: fam,
        x: vals.x,
        y: vals.y,
        z: vals.z,
        hoverinfo: 'text',
        text: vals.text,
        marker: {
          size: fam.includes('Tin Rác') ? 6 : 4,
          color: colorPalette[fam] || '#a855f7',
          opacity: 0.85,
        },
      })
    })

    // Nếu có Decision Boundary Mesh của Isolation Forest
    if (decision_boundary_mesh) {
      traces.push({
        type: 'surface',
        name: 'Decision Surface (Isolation Forest)',
        x: decision_boundary_mesh.x,
        y: decision_boundary_mesh.y,
        z: decision_boundary_mesh.z,
        opacity: 0.4,
        colorscale: 'Viridis',
        showscale: false,
        hoverinfo: 'none',
      })
    }

    const layout: Partial<Plotly.Layout> = {
      autosize: true,
      paper_bgcolor: '#090d16',
      plot_bgcolor: '#090d16',
      margin: { l: 0, r: 0, b: 0, t: 0 },
      legend: {
        x: 0,
        y: 1,
        font: { color: '#94a3b8', size: 11 },
        bgcolor: 'rgba(15, 23, 42, 0.7)',
      },
      scene: {
        xaxis: {
          title: 'Trục X (Đặc trưng Nền tảng)',
          color: '#64748b',
          gridcolor: '#1e293b',
          zerolinecolor: '#334155',
        },
        yaxis: {
          title: 'Trục Y (Đặc trưng Nghiệp vụ)',
          color: '#64748b',
          gridcolor: '#1e293b',
          zerolinecolor: '#334155',
        },
        zaxis: {
          title: 'Trục Z (Cấp bậc / Lương)',
          color: '#64748b',
          gridcolor: '#1e293b',
          zerolinecolor: '#334155',
        },
        camera: {
          eye: { x: 1.5, y: 1.5, z: 1.2 },
        },
      },
    }

    Plotly.newPlot(plotContainerRef.current, traces, layout, {
      responsive: true,
      displayModeBar: true,
      displaylogo: false,
    })

    return () => {
      if (plotContainerRef.current) {
        Plotly.purge(plotContainerRef.current)
      }
    }
  }, [data])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-5 rounded-2xl bg-slate-900 border border-slate-800">
        <div>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-violet-500/10 text-violet-400 border border-violet-500/20 font-semibold uppercase tracking-wider">
            Phòng Thí Nghiệm Machine Learning 3D
          </span>
          <h2 className="text-xl font-bold text-white mt-1.5">
            3D Spatial Machine Learning Observatory
          </h2>
          <p className="text-xs text-slate-400">
            Trực quan hóa không gian đa chiều WebGL 60 FPS: Cụm ngữ nghĩa nghề nghiệp và ranh giới phân tách tin rác (Isolation Forest).
          </p>
        </div>

        {/* Algorithm Toggle */}
        <div className="flex items-center space-x-2 bg-slate-950 p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => setModelType('umap')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              modelType === 'umap'
                ? 'bg-indigo-600 text-white shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Box className="w-3.5 h-3.5" />
            <span>UMAP 3D Embeddings</span>
          </button>
          <button
            onClick={() => setModelType('isolation-forest')}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              modelType === 'isolation-forest'
                ? 'bg-rose-600 text-white shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Isolation Forest 3D Mesh (SD5)</span>
          </button>
        </div>
      </div>

      {/* 3D Canvas Container */}
      <div className="relative rounded-2xl bg-slate-950 border border-slate-800 overflow-hidden shadow-2xl">
        <div className="absolute top-4 right-4 z-10 flex items-center space-x-2 bg-slate-900/80 backdrop-blur border border-slate-700/60 px-3 py-1.5 rounded-xl text-xs text-slate-300">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
          <span>WebGL 60 FPS • Kéo xoay 360° • Cuộn chuột zoom</span>
        </div>

        {loading && (
          <div className="absolute inset-0 z-20 flex items-center justify-center bg-slate-950/80">
            <div className="text-center space-y-2">
              <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
              <p className="text-xs text-slate-400">Đang tính toán ma trận không gian 3D...</p>
            </div>
          </div>
        )}

        <div ref={plotContainerRef} className="w-full h-[580px]" />
      </div>
    </div>
  )
}
