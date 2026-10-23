import React, { useEffect, useState } from 'react'
import axios from 'axios'
import {
  Sparkles,
  Layers,
  Percent,
  CheckCircle2,
  TrendingUp,
  GitFork,
  ArrowRight,
  Download,
  AlertCircle,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  PieChart,
  Pie,
} from 'recharts'
import { MasterDashboardData } from '../types'

const COLORS = [
  '#6366f1',
  '#06b6d4',
  '#10b981',
  '#f59e0b',
  '#ec4899',
  '#8b5cf6',
  '#14b8a6',
  '#f97316',
]

export const MasterDashboardPage: React.FC = () => {
  const [data, setData] = useState<MasterDashboardData | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchDashboard = async () => {
    try {
      setLoading(true)
      const res = await axios.get<MasterDashboardData>('/api/dashboard')
      setData(res.data)
      setError(null)
    } catch (err: any) {
      setError(err.message || 'Lỗi khi tải thông tin từ api/Dashboard')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDashboard()
  }, [])

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="text-center space-y-3">
          <div className="w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full animate-spin mx-auto"></div>
          <p className="text-sm text-slate-400">Đang tải thông tin bộ dữ liệu sau integration từ api/Dashboard...</p>
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="p-6 rounded-2xl bg-rose-950/30 border border-rose-500/30 text-rose-200 flex items-center space-x-3">
        <AlertCircle className="w-5 h-5 shrink-0" />
        <div>
          <h4 className="font-semibold text-sm">Lỗi tải dữ liệu</h4>
          <p className="text-xs text-rose-300">{error}</p>
        </div>
      </div>
    )
  }

  const { dataset_metadata, platform_breakdown, schema_convergence, market_salary_benchmark_vnd, top_golden_skills, data_lineage } = data

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-6 rounded-2xl bg-gradient-to-r from-slate-900 via-indigo-950/40 to-slate-900 border border-slate-800">
        <div>
          <div className="flex items-center space-x-2 text-indigo-400 text-xs font-semibold uppercase tracking-wider">
            <Sparkles className="w-4 h-4" />
            <span>Executive Master Dashboard • api/Dashboard</span>
          </div>
          <h2 className="text-xl font-bold text-white mt-1">
            Bộ Dữ Liệu Hoàn Chỉnh Sau Integration (Golden Master)
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Phản ánh hình ảnh thực tế của toàn bộ thị trường CNTT Việt Nam sau chuỗi làm sạch, ánh xạ và khử trùng lặp.
          </p>
        </div>

        <div className="flex items-center space-x-3">
          <button
            onClick={() => {
              const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
              const url = URL.createObjectURL(blob)
              const a = document.createElement('a')
              a.href = url
              a.download = `golden_master_summary_${new Date().toISOString().slice(0, 10)}.json`
              a.click()
            }}
            className="flex items-center space-x-2 px-3.5 py-2 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold transition shadow-lg shadow-indigo-600/30"
          >
            <Download className="w-4 h-4" />
            <span>Xuất Báo Cáo JSON</span>
          </button>
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Dữ Liệu Thô (Raw)</span>
            <Layers className="w-4 h-4 text-indigo-400" />
          </div>
          <div className="text-2xl font-bold text-white mt-2">
            {dataset_metadata.total_raw_scraped.toLocaleString()}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Tổng bài cào từ 8 sàn
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Sau Tiền Xử Lý</span>
            <CheckCircle2 className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-cyan-400 mt-2">
            {dataset_metadata.total_preprocessed.toLocaleString()}
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Đạt chuẩn Data Quality Gate
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-emerald-500/30 bg-emerald-950/10">
          <div className="flex items-center justify-between text-emerald-300 text-xs">
            <span>Tin Vàng Duy Nhất</span>
            <Sparkles className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400 mt-2">
            {dataset_metadata.total_golden_unique.toLocaleString()}
          </div>
          <div className="text-xs text-emerald-500/80 mt-1 font-medium">
            Bộ dữ liệu sạch sau khử trùng
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Tỷ Lệ Khử Trùng Lặp</span>
            <Percent className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400 mt-2">
            {dataset_metadata.deduplication_rate_pct}%
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Đã lọc bỏ tin đăng chéo sàn
          </div>
        </div>
      </div>

      {/* Visual Data Lineage */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
        <h3 className="text-sm font-bold text-white flex items-center space-x-2">
          <GitFork className="w-4 h-4 text-indigo-400" />
          <span>Dòng Chảy Dữ Liệu Liền Mạch (Data Lineage)</span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-center">
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
            <div className="text-xs text-slate-400">1. Cào Thô (Raw)</div>
            <div className="text-lg font-bold text-white mt-1">{data_lineage.raw_input_files} files</div>
          </div>
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
            <div className="text-xs text-slate-400">2. Tiền Xử Lý (Pre-processed)</div>
            <div className="text-lg font-bold text-cyan-400 mt-1">{data_lineage.preprocessed_records} tin</div>
          </div>
          <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
            <div className="text-xs text-slate-400">3. Trùng Lặp Ghép Nối</div>
            <div className="text-lg font-bold text-amber-400 mt-1">-{data_lineage.cross_platform_duplicates_merged} bài</div>
          </div>
          <div className="p-3 rounded-xl bg-emerald-950/20 border border-emerald-500/30">
            <div className="text-xs text-emerald-300">4. Bộ Dữ Liệu Vàng (Curated)</div>
            <div className="text-lg font-bold text-emerald-400 mt-1">{data_lineage.final_golden_records} bài duy nhất</div>
          </div>
        </div>
      </div>

      {/* Two columns: Platform Breakdown & Salary Benchmark */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Platform Share */}
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white">
              Đóng Góp Tỷ Trọng Từ 8 Sàn Tuyển Dụng
            </h3>
            <span className="text-xs text-slate-400">Tổng 8 nguồn</span>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={platform_breakdown} layout="vertical" margin={{ left: 10, right: 20 }}>
                <XAxis type="number" unit="%" stroke="#64748b" fontSize={11} />
                <YAxis dataKey="source" type="category" stroke="#94a3b8" fontSize={11} width={80} />
                <Tooltip
                  formatter={(val: any) => [`${val}%`, 'Tỷ trọng đóng góp']}
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                />
                <Bar dataKey="share_pct" radius={[0, 4, 4, 0]}>
                  {platform_breakdown.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Market Salary Benchmark */}
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              <span>Phân Bố Mức Lương Chuẩn Thị Trường (Triệu VND)</span>
            </h3>
            <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              Quy đổi VND
            </span>
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
              <div className="text-xs text-slate-400">Phân vị 25 (P25)</div>
              <div className="text-lg font-bold text-white mt-1">{market_salary_benchmark_vnd.p25}M</div>
            </div>
            <div className="p-3 rounded-xl bg-slate-950 border border-emerald-500/30 bg-emerald-950/10">
              <div className="text-xs text-emerald-400 font-medium">Trung Vị (Median)</div>
              <div className="text-lg font-bold text-emerald-400 mt-1">{market_salary_benchmark_vnd.median}M</div>
            </div>
            <div className="p-3 rounded-xl bg-slate-950 border border-slate-800">
              <div className="text-xs text-slate-400">Phân vị 75 (P75)</div>
              <div className="text-lg font-bold text-white mt-1">{market_salary_benchmark_vnd.p75}M</div>
            </div>
          </div>

          <div className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2 text-xs">
            <div className="flex justify-between text-slate-400">
              <span>Mức lương trung bình (Mean):</span>
              <span className="text-white font-semibold">{market_salary_benchmark_vnd.mean} Triệu VND</span>
            </div>
            <div className="flex justify-between text-slate-400">
              <span>Khoảng hợp lệ chuẩn:</span>
              <span className="text-white font-semibold">
                {market_salary_benchmark_vnd.min_valid}M - {market_salary_benchmark_vnd.max_valid}M VND/tháng
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Two columns: Schema Convergence & Top Golden Skills */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Schema Convergence Table */}
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white">
              Độ Hội Tụ Vào Common Target Schema v1
            </h3>
            <span className="text-xs text-emerald-400 font-medium">
              Độ hoàn thiện: {dataset_metadata.overall_completeness_score}%
            </span>
          </div>
          <div className="space-y-2.5">
            {Object.entries(schema_convergence).map(([fName, pct]) => (
              <div key={fName} className="space-y-1">
                <div className="flex justify-between text-xs text-slate-300">
                  <span className="font-mono">{fName}</span>
                  <span className="font-semibold text-emerald-400">{pct}%</span>
                </div>
                <div className="w-full h-1.5 rounded-full bg-slate-800 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-emerald-400 transition-all duration-500"
                    style={{ width: `${pct}%` }}
                  ></div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Top Golden Skills */}
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-bold text-white">
              Top Kỹ Năng Công Nghệ Chuẩn Hóa (ESCO Standard)
            </h3>
            <span className="text-xs text-slate-400">Phần trăm xuất hiện</span>
          </div>
          <div className="grid grid-cols-2 gap-2.5">
            {top_golden_skills.map((sk) => (
              <div
                key={sk.skill}
                className="p-2.5 rounded-xl bg-slate-950 border border-slate-800/80 flex items-center justify-between"
              >
                <div>
                  <div className="text-xs font-semibold text-white">{sk.skill}</div>
                  <div className="text-[10px] text-slate-400">{sk.job_count} bài đăng</div>
                </div>
                <span className="text-xs font-bold text-indigo-400">{sk.percentage}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
