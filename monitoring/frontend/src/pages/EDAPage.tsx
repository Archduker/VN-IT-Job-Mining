import React, { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api/client'
import { RankBars, TableShell, pct } from '../components/reports'
import { Card, EmptyState, ErrorState, LoadingState, SectionTitle, SourcePills, StatCard, fmt, useAsync } from '../components/ui'
import { sourceName } from '../constants/sources'

const SourceDetail: React.FC<{ source: string }> = ({ source }) => {
  const summary = useAsync(() => api.edaSummary(source), [source])
  const inventory = useAsync(() => api.edaInventory(source), [source])
  const charts = useAsync(() => api.edaCharts(source), [source])
  if (summary.error || inventory.error || charts.error) return <ErrorState />
  if (!summary.data || !inventory.data || !charts.data) return <LoadingState />
  const s = summary.data
  const c = charts.data

  return (
    <>
      <section aria-label="Tóm tắt nguồn" className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label="Bản ghi raw trên máy" value={fmt(s.total_records)} sub="Đọc tối đa 200 bản ghi để kiểm kê" />
        <StatCard label="Độ đầy đủ trung bình" value={pct(s.completeness_score_pct)} sub={`${s.fields_count} trường trong raw`} />
        <StatCard label="Có lương dạng số" value={pct(s.salary_parse_rate_pct)} sub={s.reason ?? 'Theo health card của pipeline'} />
        <StatCard label="Lương thỏa thuận" value={pct(s.negotiable_salary_pct)} sub="Tính từ parquet staging" />
      </section>

      <Card>
        <SectionTitle title="Kiểm kê trường trong raw" hint="Tỉ lệ thiếu tính trên các bản ghi raw đang có trên máy." />
        {inventory.data.length ? (
          <TableShell head={['Trường', 'Kiểu', 'Số dòng thiếu', 'Tỉ lệ thiếu', 'Số giá trị khác nhau', 'Giá trị mẫu']} alignRightFrom={2}>
            {inventory.data.map((row) => (
              <tr key={row.field_name}>
                <th scope="row" className="py-2 pr-4 font-medium text-ink whitespace-nowrap">{row.field_name}</th>
                <td className="py-2 pr-4 text-ink-muted">{row.data_type}</td>
                <td className="py-2 pr-4 text-right tabular-nums">{fmt(row.null_count)}</td>
                <td className="py-2 pr-4 text-right tabular-nums">{pct(row.null_rate_pct)}</td>
                <td className="py-2 pr-4 text-right tabular-nums">{fmt(row.unique_count)}</td>
                <td className="py-2 pr-4 text-right text-ink-muted max-w-xs truncate">{row.sample_value ?? '—'}</td>
              </tr>
            ))}
          </TableShell>
        ) : (
          <EmptyState message={`Máy này chưa có raw của ${sourceName(source)}. Chạy python scripts/sync_cloud_lakehouse.py --download --source ${source}.`} />
        )}
      </Card>

      {c.available ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card>
            <SectionTitle title="Phân phối lương (triệu VND)" hint={`${fmt(c.salary_records)} trên ${fmt(c.records)} tin có lương dạng số.`} />
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={c.salary_histogram} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="#EFEEF4" />
                  <XAxis dataKey="bin" tick={{ fill: '#6B6980', fontSize: 12 }} axisLine={{ stroke: '#D9D8E2' }} tickLine={false} />
                  <YAxis width={44} allowDecimals={false} tick={{ fill: '#6B6980', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: '#F1EFFD' }} formatter={(v: number) => [`${fmt(v)} tin`, 'Số tin']} />
                  <Bar dataKey="count" fill="#5B4CE6" radius={[5, 5, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
          <Card>
            <SectionTitle title="Top 10 kỹ năng" hint="Đếm trên skills_list sau bước imputer." />
            <RankBars items={c.skills_pareto} empty="Chưa có kỹ năng trong dữ liệu staging." labelWidth={120} />
          </Card>
          <Card className="xl:col-span-2">
            <SectionTitle title="Tỉnh/thành sau chuẩn hóa" />
            <RankBars items={c.locations} empty="Chưa có số liệu địa điểm." labelWidth={120} />
          </Card>
        </div>
      ) : (
        <Card>
          <SectionTitle title="Biểu đồ phân phối" />
          <EmptyState message={c.unavailable_reason ?? 'Chưa có dữ liệu staging.'} />
        </Card>
      )}
    </>
  )
}

const CrossSource: React.FC = () => {
  const { data, error } = useAsync(() => api.edaCompare(), [])
  if (error) return <ErrorState />
  if (!data) return <LoadingState />
  return (
    <Card>
      <SectionTitle
        title="So sánh độ đầy đủ giữa 8 nguồn"
        hint="Đọc từ reports/integration/<nguồn>_integration_report.json; lương dạng số lấy từ health card."
      />
      {data.available ? (
        <TableShell head={['Nguồn', 'Bản ghi', 'Đầy đủ trung bình', 'Có chuỗi lương', 'Có lương dạng số', 'Có kinh nghiệm', 'Có cấp bậc']}>
          {data.sources.map((row) => (
            <tr key={row.source}>
              <th scope="row" className="py-2.5 pr-4 font-semibold text-ink whitespace-nowrap">{sourceName(row.source)}</th>
              {row.available ? (
                <>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{fmt(row.records)}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{pct(row.completeness_pct)}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{pct(row.salary_text_pct)}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{pct(row.salary_numeric_pct)}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{pct(row.experience_pct)}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{pct(row.seniority_pct)}</td>
                </>
              ) : (
                <td colSpan={6} className="py-2.5 pr-4 text-right text-ink-muted">Chưa có báo cáo Integration</td>
              )}
            </tr>
          ))}
        </TableShell>
      ) : (
        <EmptyState message={data.unavailable_reason ?? 'Chưa có báo cáo Integration.'} />
      )}
    </Card>
  )
}

export const EDAPage: React.FC = () => {
  const [source, setSource] = useState<string>('topcv')
  const [mode, setMode] = useState<'single' | 'cross'>('single')

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {mode === 'single' ? <SourcePills label="Chọn nguồn" selected={source} onSelect={setSource} /> : <span />}
        <div role="group" aria-label="Chế độ xem" className="flex bg-white border border-line-strong rounded-xl p-1 gap-1">
          {([
            ['single', 'Một nguồn'],
            ['cross', 'So sánh 8 nguồn'],
          ] as const).map(([key, label]) => (
            <button
              key={key}
              type="button"
              aria-pressed={mode === key}
              onClick={() => setMode(key)}
              className={`min-h-9 px-3.5 rounded-lg text-[13px] font-semibold ${mode === key ? 'bg-brand-500 text-white' : 'text-[#4E4C5E]'}`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>
      {mode === 'single' ? <SourceDetail key={source} source={source} /> : <CrossSource />}
    </div>
  )
}

export default EDAPage
