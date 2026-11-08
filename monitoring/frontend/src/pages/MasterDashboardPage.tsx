import React from 'react'
import { ArrowRight } from 'lucide-react'
import { api } from '../api/client'
import { RankBars, ReportStamp, pct } from '../components/reports'
import { Card, ErrorState, LoadingState, SectionTitle, StatCard, fmt, useAsync } from '../components/ui'
import { SOURCES, sourceName } from '../constants/sources'

const million = (v: number | null | undefined): string =>
  v === null || v === undefined ? '—' : `${v.toLocaleString('vi-VN', { maximumFractionDigits: 1 })} tr`

export const MasterDashboardPage: React.FC = () => {
  const { data, error, loading } = useAsync(() => api.dashboard(), [])
  if (error && !data) return <ErrorState />
  if (loading && !data) return <LoadingState />
  if (!data) return null
  const { totals, salary_vnd_million: salary } = data

  return (
    <div className="flex flex-col gap-6">
      <ReportStamp generatedAt={data.generated_at} reason={data.unavailable_reason} />

      <section aria-label="Bộ golden" className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label="Bản ghi golden" value={fmt(totals?.golden_records)} sub="data/curated/curated_flat_golden_jobs.parquet" />
        <StatCard label="Tỉ lệ trùng đã gộp" value={pct(totals?.deduplication_rate_pct)} sub={`Từ ${fmt(totals?.staging_records)} bản ghi staging`} />
        <StatCard label="Có lương dạng số" value={pct(totals?.salary_coverage_pct)} sub="Lương thỏa thuận giữ NaN" />
        <StatCard label="Bản ghi sau Integration" value={fmt(totals?.integrated_records)} sub="Trước khi loại JD rỗng" />
      </section>

      {data.lineage.length > 0 && (
        <Card>
          <SectionTitle title="Luồng dữ liệu" hint="Số bản ghi còn lại sau từng bước." />
          <ol className="m-0 p-0 list-none flex flex-wrap items-center gap-3">
            {data.lineage.map((step, i) => (
              <li key={step.step} className="flex items-center gap-3">
                {i > 0 && <ArrowRight className="w-4 h-4 text-ink-faint" aria-hidden="true" />}
                <div className="px-4 py-3 rounded-xl bg-panel">
                  <div className="text-xs text-ink-muted">{step.step}</div>
                  <div className="text-xl font-bold tabular-nums">{fmt(step.records)}</div>
                </div>
              </li>
            ))}
          </ol>
        </Card>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <Card>
          <SectionTitle title="Đóng góp của từng nguồn" hint="Số bản ghi golden mà mỗi nguồn giữ lại sau khử trùng lặp." />
          <RankBars
            labelWidth={110}
            empty="Chưa có bộ golden."
            items={data.platform_breakdown.map((p) => ({
              label: sourceName(p.source),
              count: p.golden_records,
              color: SOURCES.find((s) => s.id === p.source)?.color,
            }))}
          />
        </Card>
        <Card>
          <SectionTitle title="Lương thị trường (triệu VND)" hint="Trung điểm dải lương của các tin có lương dạng số." />
          {salary ? (
            <dl className="m-0 grid grid-cols-2 sm:grid-cols-5 gap-3">
              {([
                ['P1', salary.p1],
                ['Q1', salary.q1],
                ['Trung vị', salary.median],
                ['Q3', salary.q3],
                ['P99', salary.p99],
              ] as const).map(([k, v]) => (
                <div key={k} className="px-3.5 py-3 rounded-xl bg-panel">
                  <dt className="text-xs text-ink-muted">{k}</dt>
                  <dd className="m-0 text-xl font-bold tabular-nums">{million(v)}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <p className="m-0 text-ink-muted">Chưa có số liệu lương.</p>
          )}
        </Card>
        <Card>
          <SectionTitle title="Nhóm nghề" />
          <RankBars items={data.job_family} empty="Chưa có phân loại nhóm nghề." labelWidth={130} />
        </Card>
        <Card>
          <SectionTitle title="Cấp bậc" />
          <RankBars items={data.seniority} empty="Chưa có phân loại cấp bậc." labelWidth={110} />
        </Card>
        <Card className="xl:col-span-2">
          <SectionTitle title="Top 10 tỉnh/thành" />
          <RankBars items={data.top_cities} empty="Chưa có số liệu địa điểm." labelWidth={120} />
        </Card>
      </div>
    </div>
  )
}

export default MasterDashboardPage
