import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { GitMerge, Layers, CheckCircle2 } from 'lucide-react'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import { ProcessingMetricsData } from '../types'

export const ProcessingPage: React.FC = () => {
  const [data, setData] = useState<ProcessingMetricsData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)

  useEffect(() => {
    axios
      .get<ProcessingMetricsData>('/api/v1/processing/metrics')
      .then((res) => setData(res.data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }, [])

  if (loading || !data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    )
  }

  const { deduplication_metrics, schema_mapping_inventory } = data

  const chartData = deduplication_metrics.similarity_score_distribution.ranges.map(
    (range: string, idx: number) => ({
      range,
      count: deduplication_metrics.similarity_score_distribution.pairs_count[idx],
    })
  )

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
        <span className="text-xs px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-semibold uppercase tracking-wider">
          Giai Đoạn 3 • Stage 3
        </span>
        <h2 className="text-xl font-bold text-white mt-1.5">
          Processing, Schema Harmonization & Deduplication
        </h2>
        <p className="text-xs text-slate-400">
          Ánh xạ dị cấu trúc từ 8 sàn về Common Target Schema v1 và khử trùng lặp ngữ nghĩa xuyên sàn (Entity Resolution via Sentence-Transformers).
        </p>
      </div>

      {/* Deduplication Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="text-xs text-slate-400">Ngưỡng Tương Đồng (Threshold)</div>
          <div className="text-2xl font-bold text-white mt-1.5">
            Cosine $\ge$ {deduplication_metrics.similarity_threshold}
          </div>
          <div className="text-xs text-slate-400 mt-1">all-MiniLM-L6-v2 Embeddings</div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-emerald-500/30 bg-emerald-950/10">
          <div className="text-xs text-emerald-400">Số Cặp Bài Trùng Lặp Phát Hiện</div>
          <div className="text-2xl font-bold text-emerald-400 mt-1.5">
            {deduplication_metrics.detected_duplicates.toLocaleString()} bài
          </div>
          <div className="text-xs text-emerald-400/80 mt-1">
            Đã gộp về bản ghi chính tắc
          </div>
        </div>

        <div className="p-4 rounded-xl bg-slate-900 border border-slate-800">
          <div className="text-xs text-slate-400">Tỷ Lệ Giảm Trùng Lặp Toàn Hệ Thống</div>
          <div className="text-2xl font-bold text-amber-400 mt-1.5">
            {deduplication_metrics.deduplication_rate_pct}%
          </div>
          <div className="text-xs text-slate-400 mt-1">
            Tiết kiệm dung lượng và chống nhiễu
          </div>
        </div>
      </div>

      {/* Similarity Score Distribution Chart */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <h3 className="text-sm font-bold text-white">
          Phân Phối Điểm Tương Đồng Ngữ Nghĩa (Cosine Similarity Distribution)
        </h3>
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <XAxis dataKey="range" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip
                formatter={(val: any) => [val.toLocaleString(), 'Số cặp so sánh']}
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
              />
              <Bar dataKey="count" fill="#10b981" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Schema Mapping Inventory Table */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center space-x-2">
          <GitMerge className="w-4 h-4 text-emerald-400" />
          <span>Bảng Ánh Xạ Schema Đích Chuẩn Hóa (Common Target Schema v1)</span>
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Trường Đích (Target Field)</th>
                <th className="py-2.5 px-3">Kiểu Dữ Liệu</th>
                <th className="py-2.5 px-3">Tỷ Lệ Hội Tụ (%)</th>
                <th className="py-2.5 px-3">Trạng Thái</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {schema_mapping_inventory.map((row: any) => (
                <tr key={row.target_field} className="hover:bg-slate-800/40">
                  <td className="py-2.5 px-3 font-mono font-bold text-white">{row.target_field}</td>
                  <td className="py-2.5 px-3 text-slate-400">{row.data_type}</td>
                  <td className="py-2.5 px-3 font-semibold text-emerald-400">{row.unified_pct}%</td>
                  <td className="py-2.5 px-3">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-300 border border-emerald-500/20">
                      {row.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
