import React from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import { SourceDetail, StepOverview, StepStrip } from '../components/preprocessing'
import { ReportStamp, TableShell, pct } from '../components/reports'
import { Card, ErrorState, LoadingState, SectionTitle, SourcePills, StatCard, fmt, useAsync } from '../components/ui'
import { sourceName } from '../constants/sources'

const date = (iso: string | null | undefined): string =>
  iso ? new Date(iso).toLocaleDateString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) : '—'

/** Trang theo docs/monitoring/preprocessing_page_spec.md: dải 5 bước → tổng 8 nguồn → từng nguồn. */
export const PreprocessingPage: React.FC = () => {
  const [params, setParams] = useSearchParams()
  const step = params.get('step') ?? '01_clean'
  const source = params.get('source') ?? 'topdev'
  const set = (next: Record<string, string>) => setParams({ step, source, ...next }, { replace: true })
  const steps = useAsync(() => api.preprocessingSteps(), [])
  if (steps.error && !steps.data) return <ErrorState />
  if (!steps.data) return <LoadingState />
  const i = steps.data.findIndex((s) => s.step === step)

  return (
    <div className="flex flex-col gap-6">
      <StepStrip steps={steps.data} selected={step} onSelect={(s) => set({ step: s })} />
      <StepOverview step={step} />
      <Card>
        <SectionTitle title="Đi sâu một nguồn" hint="Input của bước này là output của bước trước." />
        <SourcePills label="Chọn nguồn" selected={source} onSelect={(s) => set({ source: s })} />
      </Card>
      <SourceDetail
        step={step}
        source={source}
        prev={i > 0 ? steps.data[i - 1] : undefined}
        next={i >= 0 && i < steps.data.length - 1 ? steps.data[i + 1] : undefined}
        onGoStep={(s) => set({ step: s })}
      />
      <LegacyHealthCards />
    </div>
  )
}

/** Pipeline cũ (scripts/run_staging_integration_pipeline.py): giữ để so đến khi P5 xong. */
const LegacyHealthCards: React.FC = () => {
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
          title="Pipeline cũ: kết quả làm sạch theo nguồn"
          hint="Đọc từ reports/<nguồn>/<nguồn>_quality_health_card.json do pipeline cũ ghi. Giữ để so với pipeline 5 bước."
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
