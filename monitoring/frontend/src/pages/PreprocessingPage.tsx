import React, { useEffect, useState } from 'react'
import axios from 'axios'
import { FileCheck, Sparkles, AlertTriangle, ArrowRight, CheckCircle2 } from 'lucide-react'
import { PreprocessingMetricsData, ParsingRuleItem } from '../types'

export const PreprocessingPage: React.FC = () => {
  const [data, setData] = useState<PreprocessingMetricsData | null>(null)
  const [loading, setLoading] = useState<boolean>(true)

  useEffect(() => {
    axios
      .get<PreprocessingMetricsData>('/api/v1/preprocessing/metrics')
      .then((res) => setData(res.data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }, [])

  if (loading || !data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <div className="w-8 h-8 border-4 border-cyan-500 border-t-transparent rounded-full animate-spin"></div>
      </div>
    )
  }

  const { parsing_rules, null_reduction_comparison } = data

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800">
        <span className="text-xs px-2.5 py-0.5 rounded-full bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 font-semibold uppercase tracking-wider">
          Giai Đoạn 2 • Stage 2
        </span>
        <h2 className="text-xl font-bold text-white mt-1.5">
          Pre-processing Observatory & Data Cleaning
        </h2>
        <p className="text-xs text-slate-400">
          Theo dõi các quy tắc tiền xử lý: Regex dải lương VND, bóc tách số năm kinh nghiệm, làm sạch HTML và đo lường mức độ suy giảm Null.
        </p>
      </div>

      {/* Parsing Rules Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {parsing_rules.map((rule: ParsingRuleItem) => (
          <div key={rule.rule_name} className="p-4 rounded-xl bg-slate-900 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-bold text-white flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                <span>{rule.rule_name}</span>
              </h4>
              <span className="text-xs font-bold text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-500/30">
                {rule.success_rate_pct}% Thành công
              </span>
            </div>
            <div className="text-xs text-slate-400">
              Trường đích: <span className="font-mono text-slate-300">{rule.target_field}</span>
            </div>
            <div className="flex justify-between text-xs text-slate-400 border-t border-slate-800 pt-2">
              <span>Đã parse: {rule.successfully_parsed.toLocaleString()} / {rule.total_attempted.toLocaleString()}</span>
              <span>Lỗi/Bỏ qua: {(rule.total_attempted - rule.successfully_parsed).toLocaleString()}</span>
            </div>
            {rule.failed_samples?.length > 0 && (
              <div className="text-[11px] text-amber-400/90 bg-amber-950/20 p-2 rounded-lg border border-amber-500/20">
                Mẫu chuỗi không khớp: {rule.failed_samples.join(', ')}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Null Reduction Comparison Table */}
      <div className="p-5 rounded-2xl bg-slate-900 border border-slate-800 space-y-4">
        <h3 className="text-sm font-bold text-white flex items-center space-x-2">
          <Sparkles className="w-4 h-4 text-cyan-400" />
          <span>Mức Độ Cải Thiện Dữ Liệu Sau Tiền Xử Lý (Null Reduction Rate)</span>
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-slate-950 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
              <tr>
                <th className="py-2.5 px-3">Trường Dữ Liệu</th>
                <th className="py-2.5 px-3">Tỷ Lệ Thiếu Thô (%)</th>
                <th className="py-2.5 px-3">Sau Tiền Xử Lý (%)</th>
                <th className="py-2.5 px-3">Mức Cải Thiện</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {null_reduction_comparison.map((item: any) => (
                <tr key={item.field} className="hover:bg-slate-800/40">
                  <td className="py-2.5 px-3 font-semibold text-white">{item.field}</td>
                  <td className="py-2.5 px-3 text-rose-400">{item.raw_null_pct}%</td>
                  <td className="py-2.5 px-3 text-emerald-400">{item.clean_null_pct}%</td>
                  <td className="py-2.5 px-3">
                    <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-cyan-500/20 text-cyan-300">
                      +{item.improvement_pct}% dữ liệu thu hồi
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
