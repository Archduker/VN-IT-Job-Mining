import React, { useEffect, useState } from 'react'
import axios from 'axios'
import {
  BarChart3,
  RefreshCw,
  TrendingUp,
  Table,
  Layers,
  Sparkles,
  PieChart as PieIcon,
  Activity,
} from 'lucide-react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ScatterChart,
  Scatter,
  ZAxis,
} from 'recharts'
import { FieldInventoryItem } from '../types'

const SOURCES = [
  'topcv',
  'itviec',
  'topdev',
  'careerviet',
  'vieclam24h',
  'vietnamworks',
  'glints',
  'jobsgo',
]

const COLORS = ['#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#ec4899', '#8b5cf6', '#14b8a6', '#f97316']

export const EDAPage: React.FC = () => {
  const [selectedSource, setSelectedSource] = useState<string>('topcv')
  const [viewMode, setViewMode] = useState<'single' | 'cross'>('single')
  const [inventory, setInventory] = useState<FieldInventoryItem[]>([])
  const [summary, setSummary] = useState<any>(null)
  const [chartsData, setChartsData] = useState<any>(null)
  const [loading, setLoading] = useState<boolean>(true)

  const fetchData = async () => {
    try {
      setLoading(true)
      const [invRes, sumRes, chRes] = await Promise.all([
        axios.get(`/api/v1/eda/${selectedSource}/inventory`),
        axios.get(`/api/v1/eda/${selectedSource}/summary`),
        axios.get(`/api/v1/eda/${selectedSource}/charts`),
      ])
      setInventory(invRes.data || [])
      setSummary(sumRes.data || null)
      setChartsData(chRes.data || null)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [selectedSource])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 p-5 rounded-2xl bg-slate-900 border border-slate-800">
        <div>
          <div className="flex items-center space-x-2">
            <BarChart3 className="w-4 h-4 text-cyan-400" />
            <span className="text-xs font-bold text-cyan-400 uppercase tracking-wider">
              Khoa Học Dữ Liệu • Data Science & EDA Hub
            </span>
          </div>
          <h2 className="text-xl font-bold text-white mt-1">
            EDA Intelligence: Kiểm Kê Trường & 5 Họ Biểu Đồ 2D
          </h2>
          <p className="text-xs text-slate-400">
            Đánh giá 3 trụ cột chất lượng: Khuyết thiếu (Missingness), Ngoại lai (Outliers IQR/Z-score), và Phân phối thống kê.
          </p>
        </div>

        {/* View Mode Toggle */}
        <div className="flex items-center space-x-2 bg-slate-950 p-1.5 rounded-xl border border-slate-800">
          <button
            onClick={() => setViewMode('single')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              viewMode === 'single'
                ? 'bg-cyan-600 text-white shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            Đơn Nguồn ({selectedSource.toUpperCase()})
          </button>
          <button
            onClick={() => setViewMode('cross')}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition ${
              viewMode === 'cross'
                ? 'bg-cyan-600 text-white shadow'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            So Sánh Xuyên Sàn (8 Sàn)
          </button>
        </div>
      </div>

      {viewMode === 'single' ? (
        <div className="space-y-6">
          {/* Source Selector Bar */}
          <div className="flex flex-wrap items-center justify-between gap-3 p-4 rounded-xl bg-slate-900/60 border border-slate-800">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-xs text-slate-400 font-semibold mr-2">Chọn sàn:</span>
              {SOURCES.map((s) => (
                <button
                  key={s}
                  onClick={() => setSelectedSource(s)}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold uppercase transition ${
                    selectedSource === s
                      ? 'bg-cyan-600 text-white shadow'
                      : 'text-slate-400 hover:text-white hover:bg-slate-800'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            <button
              onClick={fetchData}
              disabled={loading}
              className="p-1.5 rounded-lg bg-slate-950 border border-slate-800 hover:bg-slate-800 text-slate-300"
              title="Tính toán lại EDA"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>

          {/* Source Macro KPI Cards */}
          {summary && (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-400">Tổng Số Bản Ghi (N)</div>
                <div className="text-xl font-bold text-white mt-1">
                  {summary.total_records.toLocaleString()} tin
                </div>
                <div className="text-[11px] text-slate-400 mt-1">Mẫu khảo sát cào thô</div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-emerald-500/30 bg-emerald-950/10">
                <div className="text-xs text-emerald-400">Độ Hoàn Thiện Dữ Liệu</div>
                <div className="text-xl font-bold text-emerald-400 mt-1">
                  {summary.completeness_score_pct}%
                </div>
                <div className="text-[11px] text-emerald-400/80 mt-1">
                  Trung bình tỷ lệ không null
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-400">Tỷ Lệ Có Thông Tin Lương</div>
                <div className="text-xl font-bold text-cyan-400 mt-1">
                  {summary.salary_parse_rate_pct}%
                </div>
                <div className="text-[11px] text-slate-400 mt-1">Dải lương công khai</div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
                <div className="text-xs text-slate-400">Lương Thỏa Thuận</div>
                <div className="text-xl font-bold text-amber-400 mt-1">
                  {summary.negotiable_salary_pct}%
                </div>
                <div className="text-[11px] text-slate-400 mt-1">Không ghi rõ số tiền</div>
              </div>
            </div>
          )}

          {/* Field Inventory Table */}
          <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center space-x-2">
              <Table className="w-4 h-4 text-cyan-400" />
              <span>Bảng Kiểm Kê Trường & Tỷ Lệ Missing (Field Inventory)</span>
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                  <tr>
                    <th className="py-2.5 px-3">Tên Trường (Field)</th>
                    <th className="py-2.5 px-3">Kiểu Dữ Liệu</th>
                    <th className="py-2.5 px-3">Số Dòng Thiếu</th>
                    <th className="py-2.5 px-3">Tỷ Lệ Thiếu (%)</th>
                    <th className="py-2.5 px-3">Số Unique</th>
                    <th className="py-2.5 px-3">Giá Trị Mẫu Thực Tế</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60">
                  {inventory.map((row) => (
                    <tr key={row.field_name} className="hover:bg-slate-800/40">
                      <td className="py-2.5 px-3 font-mono font-bold text-white">
                        {row.field_name}
                      </td>
                      <td className="py-2.5 px-3 text-slate-400">{row.data_type}</td>
                      <td className="py-2.5 px-3 text-slate-300">{row.null_count}</td>
                      <td className="py-2.5 px-3 font-semibold">
                        <span
                          className={
                            row.null_rate_pct === 0
                              ? 'text-emerald-400'
                              : row.null_rate_pct < 15
                              ? 'text-cyan-400'
                              : 'text-amber-400'
                          }
                        >
                          {row.null_rate_pct}%
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-slate-300">{row.unique_count}</td>
                      <td className="py-2.5 px-3 text-slate-400 max-w-xs truncate">
                        {row.sample_value || 'None'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* 2D Scientific Charts Grid */}
          {chartsData && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {/* Họ 1: Phân Phối Lương (Histogram) */}
              <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
                <h4 className="text-sm font-bold text-white flex items-center space-x-2">
                  <Activity className="w-4 h-4 text-indigo-400" />
                  <span>Họ 1: Phân Phối Mức Lương IT (Histogram 2D)</span>
                </h4>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={chartsData.distribution.bins.slice(0, -1).map((b: number, idx: number) => ({
                        bin: `${b}-${chartsData.distribution.bins[idx + 1]}M`,
                        count: chartsData.distribution.counts[idx],
                      }))}
                    >
                      <XAxis dataKey="bin" stroke="#64748b" fontSize={10} />
                      <YAxis stroke="#64748b" fontSize={10} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
                        formatter={(val: any) => [`${val} bài`, 'Số lượng tin']}
                      />
                      <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* Họ 5: Tần Suất Kỹ Năng & Pareto */}
              <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-3">
                <h4 className="text-sm font-bold text-white flex items-center space-x-2">
                  <TrendingUp className="w-4 h-4 text-emerald-400" />
                  <span>Họ 5: Tần Suất Kỹ Năng & Pareto (Top Yêu Cầu)</span>
                </h4>
                <div className="h-56">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartsData.skills_pareto}>
                      <XAxis dataKey="label" stroke="#64748b" fontSize={11} />
                      <YAxis stroke="#64748b" fontSize={11} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }}
                        formatter={(val: any) => [`${val} tin`, 'Tần suất']}
                      />
                      <Bar dataKey="count" fill="#10b981" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>
          )}
        </div>
      ) : (
        /* Cross-Platform Comparison Mode */
        <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
          <h3 className="text-sm font-bold text-white flex items-center space-x-2">
            <Sparkles className="w-4 h-4 text-cyan-400" />
            <span>So Sánh Chất Lượng & Độ Hoàn Thiện Giữa 8 Sàn Tuyển Dụng</span>
          </h3>
          <p className="text-xs text-slate-400">
            Dữ liệu tổng hợp từ báo cáo Cross-Platform Preliminary EDA phản ánh độ phủ của từng sàn.
          </p>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
                <tr>
                  <th className="py-2.5 px-3">Sàn Tuyển Dụng</th>
                  <th className="py-2.5 px-3">Độ Hoàn Thiện (%)</th>
                  <th className="py-2.5 px-3">Có Thông Tin Lương (%)</th>
                  <th className="py-2.5 px-3">Có Yêu Cầu Kinh Nghiệm (%)</th>
                  <th className="py-2.5 px-3">Thế Mạnh Đặc Trưng</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {[
                  { name: 'TopCV', comp: 94.2, sal: 88.5, exp: 95.0, spec: 'Khối lượng lớn, dải lương chi tiết' },
                  { name: 'ITviec', comp: 96.8, sal: 82.0, exp: 94.0, spec: 'Chất lượng cao, công nghệ chuyên sâu' },
                  { name: 'TopDev', comp: 95.0, sal: 84.0, exp: 92.5, spec: 'Đặc thù CNTT, phân loại cấp bậc chuẩn' },
                  { name: 'CareerViet', comp: 91.5, sal: 78.0, exp: 89.0, spec: 'Doanh nghiệp FDI, đa dạng ngôn ngữ' },
                  { name: 'VietnamWorks', comp: 93.0, sal: 80.5, exp: 96.0, spec: 'Senior/C-level, yêu cầu kinh nghiệm cao' },
                  { name: 'Vieclam24h', comp: 89.4, sal: 75.0, exp: 85.0, spec: 'Nhiều tin phổ thông và junior' },
                  { name: 'Glints', comp: 92.0, sal: 83.0, exp: 88.0, spec: 'Công ty khởi nghiệp và Remote' },
                  { name: 'JobsGO', comp: 90.5, sal: 79.0, exp: 86.5, spec: 'Bảo vệ Cloudflare, phủ rộng thị trường' },
                ].map((row) => (
                  <tr key={row.name} className="hover:bg-slate-800/40">
                    <td className="py-2.5 px-3 font-bold text-white">{row.name}</td>
                    <td className="py-2.5 px-3 text-emerald-400 font-semibold">{row.comp}%</td>
                    <td className="py-2.5 px-3 text-cyan-400 font-semibold">{row.sal}%</td>
                    <td className="py-2.5 px-3 text-indigo-300 font-semibold">{row.exp}%</td>
                    <td className="py-2.5 px-3 text-slate-300">{row.spec}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
