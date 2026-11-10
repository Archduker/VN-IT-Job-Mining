import React, { useState, useEffect } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { RawQualityCharts } from '../components/eda/RawQualityCharts'
import { ExplorationCharts } from '../components/eda/ExplorationCharts'
import { api } from '../api/client'
import { RankBars, TableShell, pct } from '../components/reports'
import { Card, EmptyState, ErrorState, LoadingState, SectionTitle, SourcePills, StatCard, fmt, useAsync } from '../components/ui'
import { sourceName } from '../constants/sources'

const SourceDetail: React.FC<{ source: string; origin: 'local' | 'r2' }> = ({ source, origin }) => {
  const [scanTick, setScanTick] = useState(0)
  const summary = useAsync(() => api.edaSummary(source, origin), [source, origin, scanTick])
  useEffect(() => {
    if (origin !== 'r2' || summary.data?.raw_scan?.status === 'COMPLETE' || summary.data?.raw_scan?.status === 'ERROR') return
    const id = setInterval(() => setScanTick(t => t + 1), 5000)
    return () => clearInterval(id)
  }, [origin, summary.data?.raw_scan?.status])
  const inventory = useAsync(() => api.edaInventory(source, origin), [source, origin, summary.data?.raw_scan?.status])
  const charts = useAsync(() => api.edaCharts(source, origin), [source, origin])
  if (summary.error || inventory.error || charts.error) return <ErrorState message={origin === 'r2' ? 'Không đọc được dữ liệu R2. Kiểm tra kết nối, cấu hình và quyền đọc bucket; xem chi tiết phản hồi API để biết nguyên nhân.' : undefined} />
  if (!summary.data || !inventory.data || !charts.data) return <LoadingState />
  const s = summary.data
  const c = charts.data

  return (
    <>
      {s.raw_scan && <Card>
        <SectionTitle title="Quét toàn bộ raw trên R2" hint="Bao gồm mọi phiên bản và từng bản ghi trong file batch; không phải số tin unique. Chỉ công bố độ đầy đủ và kiểm kê khi quét hoàn tất. Kết quả lưu RAM đến khi quét lại hoặc backend khởi động lại." />
        <p role="status">{s.raw_scan.status} · đã đọc {fmt(s.raw_scan.objects)} object, {fmt(s.raw_scan.records)} bản ghi{s.raw_scan.completed_at ? ` · hoàn tất ${new Date(s.raw_scan.completed_at).toLocaleString('vi-VN')}` : ''}</p>
        {s.raw_scan.status === 'ERROR' && <p className="text-state-fail-fg">Quét lỗi; kết quả chưa đầy đủ không được sử dụng. Kiểm tra quyền đọc/kết nối và định dạng raw.</p>}
        <button disabled={['QUEUED', 'RUNNING'].includes(s.raw_scan.status)} onClick={() => { api.refreshEdaScan(source).then(() => setScanTick(t => t + 1)).catch(() => alert('Không khởi động được lượt quét.')) }} className="px-4 py-2 rounded-lg border border-line disabled:opacity-50">Quét lại toàn bộ</button>
      </Card>}
      <section aria-label="Tóm tắt nguồn" className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label={origin === 'r2' ? 'Bản ghi staging trên R2' : 'Bản ghi sau Integration'} value={fmt(s.total_records)} sub={origin === 'r2' ? 'Theo Parquet staging trên R2' : 'Theo báo cáo Integration của nguồn'} />
        <StatCard
          label="Độ đầy đủ trong raw"
          value={pct(s.completeness_score_pct)}
          sub={s.raw_scan && s.raw_scan.status !== 'COMPLETE' ? 'Chưa có thống kê đầy đủ; xem tiến độ quét ở trên.' : `${s.fields_count} trường, tính trên ${fmt(s.sampled_records)} bản ghi raw ${origin === 'r2' ? 'trên R2' : 'trên máy'}`}
        />
        <StatCard label="Có lương dạng số" value={pct(s.salary_parse_rate_pct)} sub={s.reason ?? 'Theo health card của pipeline'} />
        <StatCard label="Lương thỏa thuận" value={pct(s.negotiable_salary_pct)} sub="Tính từ parquet staging" />
      </section>

      <RawQualityCharts summary={s} inventory={inventory.data} />
      <Card>
        <SectionTitle title="Kiểm kê trường trong raw" hint="Tính trên toàn bộ raw của lượt quét nguồn đang chọn; chỉ công bố khi COMPLETE." />
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
          <EmptyState message={origin === 'r2' ? `Chưa có kiểm kê hoàn tất của ${sourceName(source)}; xem tiến độ quét ở trên.` : `Máy này chưa có raw của ${sourceName(source)}. Chạy python scripts/sync_cloud_lakehouse.py --download --source ${source}.`} />
        )}
      </Card>

      {c.available ? (
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
          <Card>
            <SectionTitle title="Histogram · phân phối lương (triệu VND)" hint={`${fmt(c.salary_records)}/${fmt(c.records)} dòng staging có ít nhất một cận lương số hữu hạn. Mỗi dòng lấy trung bình các cận có số; gồm cả 0/âm để EDA. Không lấy mẫu, không cắt outlier hoặc chặn mức lương; trục X tự chia 10 khoảng phủ toàn bộ min–max.`} />
            {c.salary_records ? <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={c.salary_histogram} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid vertical={false} stroke="#EFEEF4" />
                  <XAxis dataKey="bin" tick={{ fill: '#6B6980', fontSize: 12 }} axisLine={{ stroke: '#D9D8E2' }} tickLine={false} />
                  <YAxis width={44} allowDecimals={false} tick={{ fill: '#6B6980', fontSize: 12 }} axisLine={false} tickLine={false} />
                  <Tooltip cursor={{ fill: '#F1EFFD' }} formatter={(v: number) => [`${fmt(v)} tin`, 'Số tin']} />
                  <Bar dataKey="count" fill="#5B4CE6" radius={[5, 5, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div> : <EmptyState message="Chưa có lương dạng số để vẽ histogram." />}
          </Card>
          <Card>
            <SectionTitle title="Bar chart · Top 10 kỹ năng" hint="Đếm nhãn skills_list trong Parquet; các biến thể chữ hoa/thường đang được giữ nguyên." />
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
      {c.available && <ExplorationCharts data={c.exploration} />}
    </>
  )
}

const CrossSource: React.FC<{ origin: 'local' | 'r2' }> = ({ origin }) => {
  const [tick, setTick] = useState(0)
  useEffect(() => {
    if (origin !== 'r2') return
    const id = setInterval(() => setTick(t => t + 1), 10000)
    return () => clearInterval(id)
  }, [origin])
  const { data, error } = useAsync(() => api.edaCompare(origin), [origin, tick])
  if (error) return <ErrorState message={origin === 'r2' ? 'Không đọc được dữ liệu R2. Kiểm tra kết nối, cấu hình và quyền đọc bucket; xem chi tiết phản hồi API để biết nguyên nhân.' : undefined} />
  if (!data) return <LoadingState />
  return (
    <Card>
      <SectionTitle
        title="So sánh độ đầy đủ giữa 8 nguồn"
        hint={origin === 'r2' ? 'Độ đầy đủ từ lượt quét toàn bộ raw hoàn tất trên R2; số bản ghi và lương dạng số từ Parquet staging. Chỉ số chưa đo hiển thị —.' : 'Đọc báo cáo Integration và health card trên máy.'}
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
                <td colSpan={6} className="py-2.5 pr-4 text-right text-ink-muted">{origin === 'r2' ? 'Chưa có dữ liệu trên R2' : 'Chưa có báo cáo Integration'}</td>
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
  const origin = 'r2' as const
  const [source, setSource] = useState<string>('topcv')
  const [mode, setMode] = useState<'single' | 'cross'>('single')

  return (
    <div className="flex flex-col gap-6">
      <p className="text-sm text-ink-muted">Dữ liệu Cloudflare R2 trực tiếp · khám phá toàn bộ Parquet staging của nguồn đang chọn · không lọc theo ngày.</p>
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
      {mode === 'single' ? <SourceDetail key={`${origin}-${source}`} source={source} origin={origin} /> : <CrossSource key={origin} origin={origin} />}
    </div>
  )
}

export default EDAPage
