import React from 'react'
import { api } from '../../api/client'
import { sourceName } from '../../constants/sources'
import { StepReportData, StepSample } from '../../types'
import { TableShell } from '../reports'
import { Card, EmptyState, ErrorState, LoadingState, SectionTitle, fmt, useAsync } from '../ui'

const show = (v: unknown): string => {
  if (v === null || v === undefined || v === '') return '(trống)'
  const s = typeof v === 'string' ? v : JSON.stringify(v)
  return s.length > 120 ? `${s.slice(0, 120)}…` : s
}

/** Khối `samples` của báo cáo bước: mỗi dòng một mẫu trước → sau. Báo cáo chưa có khối này thì Empty State. */
export const SamplesTable: React.FC<{ samples?: StepSample[] }> = ({ samples }) => (
  <Card>
    <SectionTitle title="Mẫu trước → sau" hint="Lấy nguyên từ khối samples của báo cáo bước, không tính lại." />
    {samples?.length ? (
      <TableShell head={['Mã tin', 'Nguồn', 'Trường', 'Trước', 'Sau']} alignRightFrom={99}>
        {samples.map((s, i) => (
          <tr key={`${s.job_id}-${s.field}-${i}`}>
            <th scope="row" className="py-2 pr-4 font-medium text-ink whitespace-nowrap">{s.job_id}</th>
            <td className="py-2 pr-4 whitespace-nowrap">{sourceName(s.source)}</td>
            <td className="py-2 pr-4 whitespace-nowrap">{s.field}</td>
            <td className="py-2 pr-4 min-w-[160px] [overflow-wrap:anywhere] line-through text-ink-faint">{show(s.before)}</td>
            <td className="py-2 pr-4 min-w-[160px] [overflow-wrap:anywhere] font-medium text-brand-700">{show(s.after)}</td>
          </tr>
        ))}
      </TableShell>
    ) : (
      <EmptyState message="Báo cáo bước này chưa có khối samples (NO_DATA)." />
    )}
  </Card>
)

const Scalar: React.FC<{ v: unknown }> = ({ v }) => <>{typeof v === 'number' ? fmt(v) : show(v)}</>

/** Bảng khóa-giá trị cho một khối extra; giá trị lồng nhau hiện dạng JSON ngắn. */
const KeyValues: React.FC<{ title: string; hint?: string; data: unknown }> = ({ title, hint, data }) => (
  <Card>
    <SectionTitle title={title} hint={hint} />
    {data && typeof data === 'object' ? (
      <TableShell head={['Khóa', 'Giá trị']} alignRightFrom={99}>
        {Object.entries(data as Record<string, unknown>).map(([k, v]) => (
          <tr key={k}>
            <th scope="row" className="py-2 pr-4 font-medium text-ink whitespace-nowrap">{k}</th>
            <td className="py-2 pr-4 [overflow-wrap:anywhere]"><Scalar v={v} /></td>
          </tr>
        ))}
      </TableShell>
    ) : (
      <EmptyState message="Bước này không ghi khối này (NO_DATA): chưa dịch hoặc chưa chạy." />
    )}
  </Card>
)

/** Khối extra theo bước: dịch (extra.translation), ngôn ngữ fastText, và tóm tắt khử trùng 01b. */
export const ExtraBlocks: React.FC<{ step: string; extra: StepReportData['extra'] }> = ({ step, extra }) => (
  <>
    {step === '03_transformation' && (
      <>
        <KeyValues title="Dịch JD tiếng Anh (envit5)" hint="extra.translation của báo cáo bước." data={extra.translation} />
        <KeyValues title="Nhận diện ngôn ngữ (fastText)" hint="extra.language_fasttext của báo cáo bước." data={extra.language_fasttext} />
      </>
    )}
    {step === '01b_deduplication' && (
      <KeyValues
        title="Tóm tắt khử trùng"
        hint="Các số vô hướng của extra; chuỗi CDC theo nguồn nằm trong báo cáo từng nguồn."
        data={Object.fromEntries(Object.entries(extra).filter(([, v]) => v === null || typeof v !== 'object'))}
      />
    )}
  </>
)

const PAGE = 20

/** Chi tiết một tin: JD và giá trị gốc cạnh giá trị đã chuẩn hóa, tra theo job_id trong parquet trên máy. */
const JobViewer: React.FC<{ source: string; jobId: string; globalId?: string | null; url?: string | null }> = ({ source, jobId, globalId, url }) => {
  const { data, error, loading } = useAsync(() => api.job(source, jobId, globalId), [source, jobId, globalId])
  if (error) return <ErrorState />
  if (loading && !data) return <LoadingState />
  if (!data || !data.available || !data.row)
    return <EmptyState message={`Không tìm thấy tin ${jobId} (${sourceName(source)}) trong dữ liệu trên máy (NO_DATA).`} />
  const r = data.row
  const pairs: [string, unknown][] = [
    ['job_title', r.job_title], ['company_name', r.company_name],
    ['raw_salary_text', r.raw_salary_text], ['salary_min_vnd', r.salary_min_vnd], ['salary_max_vnd', r.salary_max_vnd],
    ['raw_experience_text', r.raw_experience_text], ['exp_min_years', r.exp_min_years], ['exp_max_years', r.exp_max_years],
    ['raw_seniority_text', r.raw_seniority_text], ['seniority', r.seniority], ['raw_location_text', r.raw_location_text], ['tinh_chinh', r.tinh_chinh],
  ].filter(([, v]) => v !== undefined) as [string, unknown][]
  return (
    <div className="flex flex-col gap-3 min-w-0">
      <p className="m-0 text-ink-soft [overflow-wrap:anywhere]">
        <strong>job_id {jobId}</strong> · {sourceName(source)} · đọc từ bước {data.step}
        {url && <> · <a href={url} target="_blank" rel="noreferrer" className="text-brand-600 underline">mở tin gốc</a></>}
      </p>
      <TableShell head={['Trường', 'Giá trị']} alignRightFrom={99}>
        {pairs.map(([k, v]) => (
          <tr key={k}>
            <th scope="row" className="py-1.5 pr-4 font-medium text-ink whitespace-nowrap">{k}</th>
            <td className="py-1.5 pr-4 [overflow-wrap:anywhere]"><Scalar v={v} /></td>
          </tr>
        ))}
      </TableShell>
      {(['raw_description_text', 'raw_requirements_text'] as const).map((k) =>
        r[k] ? (
          <div key={k}>
            <div className="text-xs text-ink-muted">{k}</div>
            <pre className="m-0 max-h-72 overflow-auto p-3 rounded-lg bg-panel text-[12px] text-ink-soft whitespace-pre-wrap [overflow-wrap:anywhere]">{String(r[k])}</pre>
          </div>
        ) : null,
      )}
    </div>
  )
}

/** Bất thường bước 04: danh sách theo loại, bấm một dòng để mở đúng tin. */
export const AnomaliesPanel: React.FC = () => {
  const [kind, setKind] = React.useState<string | null>(null)
  const [offset, setOffset] = React.useState(0)
  const [open, setOpen] = React.useState<number | null>(null)
  const { data, error, loading } = useAsync(() => api.anomalies({ kind, offset, limit: PAGE }), [kind, offset])
  const pick = (k: string | null) => (setKind(k), setOffset(0), setOpen(null))
  const chip = (on: boolean) => `min-h-9 px-3 rounded-full text-[13px] border bg-white ${on ? 'font-semibold border-2 border-brand-500' : 'border-line-strong'}`
  return (
    <Card>
      <SectionTitle title="Bất thường bước 04: mở đúng tin" hint="Đọc reports/preprocessing/04_normalization/anomalies.json. Bấm một dòng để xem JD và job_id." />
      {error && <ErrorState />}
      {loading && !data && <LoadingState />}
      {data && !data.available && <EmptyState message="Chưa có anomalies.json của bước 04 (NO_DATA): chạy bước Normalization để tạo." />}
      {data?.available && (
        <>
          <div role="group" aria-label="Lọc theo loại" className="flex flex-wrap gap-2">
            <button type="button" aria-pressed={!kind} onClick={() => pick(null)} className={chip(!kind)}>Tất cả</button>
            {Object.entries(data.by_kind).map(([k, n]) => (
              <button key={k} type="button" aria-pressed={kind === k} onClick={() => pick(k)} className={chip(kind === k)}>
                {k} <span className="tabular-nums text-ink-muted">{fmt(n)}</span>
              </button>
            ))}
          </div>
          {!data.items.length ? (
            <EmptyState message="Không có bất thường nào ở bộ lọc này." />
          ) : (
            <TableShell head={['Loại', 'Nguồn', 'job_id', 'Trường', 'Giá trị', 'Chi tiết']} alignRightFrom={99}>
              {data.items.map((a, i) => (
                <React.Fragment key={`${a.job_id_global ?? a.job_id}-${a.kind}-${i}`}>
                  <tr
                    tabIndex={0}
                    aria-expanded={open === i}
                    onClick={() => setOpen(open === i ? null : i)}
                    onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), setOpen(open === i ? null : i))}
                    className="cursor-pointer hover:bg-panel"
                  >
                    <td className="py-2 pr-4 whitespace-nowrap">{a.kind}</td>
                    <td className="py-2 pr-4 whitespace-nowrap">{sourceName(a.source)}</td>
                    <td className="py-2 pr-4 font-medium text-ink whitespace-nowrap">{a.job_id}</td>
                    <td className="py-2 pr-4 whitespace-nowrap">{a.field}</td>
                    <td className="py-2 pr-4 [overflow-wrap:anywhere]">{show(a.value)}</td>
                    <td className="py-2 pr-4 min-w-[160px] [overflow-wrap:anywhere]">{show(a.detail)}</td>
                  </tr>
                  {open === i && (
                    <tr>
                      <td colSpan={6} className="py-2"><JobViewer source={a.source} jobId={a.job_id} globalId={a.job_id_global} url={a.url} /></td>
                    </tr>
                  )}
                </React.Fragment>
              ))}
            </TableShell>
          )}
          <p className="m-0 text-ink-soft">
            {fmt(data.total ? offset + 1 : 0)}–{fmt(Math.min(offset + PAGE, data.total))} / {fmt(data.total)}
          </p>
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={offset === 0} onClick={() => (setOffset(Math.max(0, offset - PAGE)), setOpen(null))} className="min-h-9 px-3 rounded-lg border border-line-strong bg-white text-[13px] disabled:opacity-40">Trang trước</button>
            <button type="button" disabled={offset + PAGE >= data.total} onClick={() => (setOffset(offset + PAGE), setOpen(null))} className="min-h-9 px-3 rounded-lg border border-line-strong bg-white text-[13px] disabled:opacity-40">Trang sau</button>
          </div>
        </>
      )}
    </Card>
  )
}
