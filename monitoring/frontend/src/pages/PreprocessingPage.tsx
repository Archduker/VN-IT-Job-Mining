import React from 'react'
import { api } from '../api/client'
import { ReportStamp, TableShell, pct } from '../components/reports'
import { Card, ErrorState, LoadingState, SectionTitle, StatCard, fmt, useAsync } from '../components/ui'
import { sourceName } from '../constants/sources'

const date = (iso: string | null | undefined): string =>
  iso ? new Date(iso).toLocaleDateString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) : '—'

export const PreprocessingPage: React.FC = () => {
  const { data, error, loading } = useAsync(() => api.preprocessing(), [])
  if (error && !data) return <ErrorState />
  if (loading && !data) return <LoadingState />
  if (!data) return null
  const { totals } = data

  return (
    <div className="flex flex-col gap-6">
      <ReportStamp generatedAt={data.generated_at} reason={data.unavailable_reason} />

      <section aria-label="Tổng các nguồn" className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label="Envelope raw đã đọc" value={fmt(totals.raw_envelopes)} sub="Tổng các nguồn có health card" />
        <StatCard label="Tin bị loại vì JD rỗng" value={fmt(totals.stub_removed)} sub="JD dưới 30 từ (chính sách 1.B)" />
        <StatCard label="Bản ghi sạch" value={fmt(totals.clean_records)} sub="Sau khử trùng lặp trong từng nguồn" />
        <StatCard label="Bản ghi được imputer bù" value={fmt(totals.imputed_records)} sub="Có cờ is_imputed_by_genai" />
      </section>

      <Card>
        <SectionTitle
          title="Kết quả làm sạch theo nguồn"
          hint="Đọc từ reports/<nguồn>/<nguồn>_quality_health_card.json. Nguồn chưa có file thì để trống."
        />
        <TableShell head={['Nguồn', 'Raw', 'Loại JD rỗng', 'Bản ghi sạch', 'Có lương dạng số', 'Được imputer bù', 'Ngôn ngữ (vi / song ngữ / en)', 'Ngày chạy']}>
          {data.sources.map((row) => (
            <tr key={row.source}>
              <th scope="row" className="py-2.5 pr-4 font-semibold text-ink whitespace-nowrap">{sourceName(row.source)}</th>
              {row.available ? (
                <>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{fmt(row.raw_envelopes)}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{fmt(row.stub_removed)}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums font-semibold">{fmt(row.clean_records)}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums">{pct(row.salary_coverage_pct)}</td>
                  <td className="py-2.5 pr-4 text-right tabular-nums whitespace-nowrap">
                    {fmt(row.imputed_records)} ({pct(row.imputation_rate_pct)})
                  </td>
                  <td className="py-2.5 pr-4 text-right tabular-nums whitespace-nowrap">
                    {fmt(row.language_distribution?.vi ?? null)} / {fmt(row.language_distribution?.bilingual ?? null)} /{' '}
                    {fmt(row.language_distribution?.en ?? null)}
                  </td>
                  <td className="py-2.5 pr-4 text-right whitespace-nowrap">{date(row.audit_timestamp)}</td>
                </>
              ) : (
                <td colSpan={7} className="py-2.5 pr-4 text-right text-ink-muted">Chưa có health card</td>
              )}
            </tr>
          ))}
        </TableShell>
      </Card>
    </div>
  )
}

export default PreprocessingPage
