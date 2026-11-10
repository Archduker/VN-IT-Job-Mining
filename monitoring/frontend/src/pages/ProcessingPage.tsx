import React from 'react'
import { api } from '../api/client'
import { PctBar, ReportStamp, TableShell, pct } from '../components/reports'
import { Card, EmptyState, ErrorState, LoadingState, SectionTitle, StatCard, fmt, useAsync } from '../components/ui'

export const ProcessingPage: React.FC = () => {
  const { data, error, loading } = useAsync(() => api.processing(), [])
  if (error && !data) return <ErrorState />
  if (loading && !data) return <LoadingState />
  if (!data) return null
  const dedup = data.dedup

  return (
    <div className="flex flex-col gap-6">
      <ReportStamp generatedAt={data.generated_at} reason={data.unavailable_reason} />

      <section aria-label="Khử trùng lặp" className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label="Bản ghi sau Integration" value={fmt(data.integrated_records)} sub="master_integration_report.json" />
        <StatCard label="Đầu vào khử trùng lặp" value={fmt(dedup?.input_records)} sub={`Còn ${fmt(dedup?.golden_records)} bản ghi golden`} />
        <StatCard label="Bản ghi trùng đã gộp" value={fmt(dedup?.duplicates_removed)} sub={`Tỉ lệ trùng ${pct(dedup?.deduplication_rate_pct)}`} />
        <StatCard label="Cụm trùng liên nguồn" value={fmt(dedup?.cross_platform_clusters)} sub="MinHash Jaccard" />
      </section>

      <Card>
        <SectionTitle
          title="Độ đầy đủ của schema sau Integration"
          hint="Tỉ lệ bản ghi có giá trị ở từng trường, gộp cả 8 nguồn."
        />
        {data.field_completeness.length ? (
          <TableShell head={['Trường', 'Có giá trị', 'Thiếu', 'Độ đầy đủ']}>
            {data.field_completeness.map((row) => (
              <tr key={row.field}>
                <th scope="row" className="py-2 pr-4 font-medium text-ink whitespace-nowrap">{row.field}</th>
                <td className="py-2 pr-4 text-right tabular-nums">{fmt(row.filled)}</td>
                <td className="py-2 pr-4 text-right tabular-nums">{fmt(row.missing)}</td>
                <td className="py-2 pr-4">
                  <PctBar value={row.completeness_pct} />
                </td>
              </tr>
            ))}
          </TableShell>
        ) : (
          <EmptyState message="Chưa có báo cáo Integration nên chưa có độ đầy đủ theo trường." />
        )}
      </Card>

      <Card>
        <SectionTitle title="Chỉ số pipeline chưa ghi ra" hint="Muốn hiện các số này, cần bổ sung vào báo cáo của pipeline trước." />
        <ul className="m-0 pl-5 flex flex-col gap-1.5 text-ink-soft">
          {data.not_recorded.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </Card>
    </div>
  )
}

export default ProcessingPage
