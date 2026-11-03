import React from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrowRight } from 'lucide-react'
import { api } from '../../api/client'
import { SOURCES, sourceName } from '../../constants/sources'
import { ItReview, StepReportData, StepRule, StepSummary, StorageItem } from '../../types'
import { PctBar, TableShell, pct } from '../reports'
import { Card, EmptyState, ErrorState, LoadingState, SectionTitle, StatCard, fmt, useAsync } from '../ui'

const RULE_COLORS = ['#5B4CE6', '#E08A1E', '#2F7D5B', '#C2362F', '#14A3A3', '#9C2F7A', '#2F6FD6', '#D4A72C']
const ACTION_TEXT: Record<StepRule['action'], string> = { drop: 'Bỏ', flag: 'Gắn cờ', modify: 'Sửa' }
// Luật bỏ dòng tô đỏ, luật gắn cờ tô cam: hai loại người dùng cần xem trước
const ACTION_ROW: Record<StepRule['action'], string> = { drop: 'bg-state-fail-bg/40', flag: 'bg-state-partial-bg/40', modify: '' }
const ACTION_BADGE: Record<StepRule['action'], string> = {
  drop: 'bg-state-fail-bg text-state-fail-fg',
  flag: 'bg-state-partial-bg text-state-partial-fg',
  modify: '',
}
const when = (iso?: string) => (iso ? new Date(iso).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' }) : '—')
const show = (v: unknown): string => {
  if (v === null || v === undefined || v === '') return '(trống)'
  const s = typeof v === 'string' ? v : JSON.stringify(v)
  return s.length > 120 ? `${s.slice(0, 120)}…` : s
}

const Command: React.FC<{ text?: string }> = ({ text }) =>
  text ? <code className="block mt-2 px-3 py-2 rounded-lg bg-panel text-ink-soft [overflow-wrap:anywhere]">{text}</code> : null

const stepLabel = (s: StepSummary): { text: string; cls: string } => {
  if (!s.available) return { text: 'Chưa chạy', cls: 'bg-state-idle-bg text-state-idle-fg' }
  if (s.stale) return { text: 'Cần chạy lại', cls: 'bg-state-fail-bg text-state-fail-fg' }
  return s.mode === 'dry_run'
    ? { text: 'Sẽ xử lý', cls: 'bg-state-partial-bg text-state-partial-fg' }
    : { text: 'Đã xử lý', cls: 'bg-state-done-bg text-state-done-fg' }
}

/** Dải 5 bước theo đúng thứ tự; output bước trước là input bước sau. */
export const StepStrip: React.FC<{ steps: StepSummary[]; selected: string; onSelect: (step: string) => void }> = ({
  steps,
  selected,
  onSelect,
}) => (
  <nav aria-label="Các bước pre-processing" className="grid grid-cols-1 sm:grid-cols-5 gap-2.5">
    {steps.map((s, i) => {
      const on = s.step === selected
      const label = stepLabel(s)
      return (
        <button
          key={s.step}
          type="button"
          aria-pressed={on}
          onClick={() => onSelect(s.step)}
          className={`relative flex flex-col items-start gap-1 min-w-0 px-3 py-2.5 rounded-xl text-left ${
            on ? 'bg-white border-2 border-brand-500 shadow-md' : 'bg-white border border-line-strong'
          }`}
        >
          <span className="text-xs text-ink-muted">Bước {i + 1}</span>
          <span className="font-semibold text-ink">{s.name}</span>
          <span className="text-[13px] tabular-nums text-ink-soft">
            {s.available ? `${fmt(s.input_rows)} → ${fmt(s.output_rows)}` : '—'}
          </span>
          <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${label.cls}`}>{label.text}</span>
        </button>
      )
    })}
  </nav>
)

const RuleTable: React.FC<{ rules: StepRule[]; inputRows: number }> = ({ rules, inputRows }) => (
  <TableShell head={['Luật', 'Việc', 'Hành động', 'Số dòng', '% input']} alignRightFrom={3}>
    {rules.map((r) => (
      <tr key={r.id} className={r.rows_affected > 0 ? ACTION_ROW[r.action] : ''}>
        <th scope="row" className="py-2.5 pr-4 font-semibold text-ink whitespace-nowrap">{r.id}</th>
        <td className="py-2.5 pr-4 min-w-[220px]">{r.name}</td>
        <td className="py-2.5 pr-4 whitespace-nowrap">
          <span className={r.rows_affected > 0 && r.action !== 'modify' ? `px-2 py-0.5 rounded-md text-xs font-semibold ${ACTION_BADGE[r.action]}` : ''}>
            {ACTION_TEXT[r.action]}
          </span>
        </td>
        <td className="py-2.5 pr-4 text-right tabular-nums">{fmt(r.rows_affected)}</td>
        <td className="py-2.5 pr-4 text-right tabular-nums">
          {pct(inputRows ? Math.round((1000 * r.rows_affected) / inputRows) / 10 : null)}
        </td>
      </tr>
    ))}
  </TableShell>
)

const DropChart: React.FC<{ rules: StepRule[] }> = ({ rules }) => {
  const drops = rules.filter((r) => r.action === 'drop' && r.rows_affected > 0)
  if (!drops.length) return <EmptyState message="Bước này không bỏ dòng nào." />
  const data = SOURCES.map((s) => ({
    source: s.name,
    ...Object.fromEntries(drops.map((r) => [r.id, r.by_source?.[s.id] ?? 0])),
  }))
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="#EFEEF4" />
          <XAxis dataKey="source" tick={{ fill: '#3A3850', fontSize: 11 }} interval={0} angle={-30} textAnchor="end" height={56} />
          <YAxis allowDecimals={false} tick={{ fill: '#6B6980', fontSize: 12 }} axisLine={false} tickLine={false} width={44} />
          <Tooltip cursor={{ fill: '#F1EFFD' }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {drops.map((r, i) => (
            <Bar key={r.id} dataKey={r.id} name={`${r.id} ${r.name}`} stackId="d" fill={RULE_COLORS[i % RULE_COLORS.length]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

/** Khối riêng của bước Clean: kết quả luật IT 2 tầng ở cả 8 nguồn, đo trên nhãn tay. */
export const ItReviewPanel: React.FC<{ report: StepReportData }> = ({ report }) => {
  const status = (report.extra.it_status ?? {}) as Record<string, Record<string, number>>
  const levels = (report.extra.it_levels ?? {}) as Record<string, Record<string, number>>
  const review = (report.extra.review ?? {}) as Record<string, ItReview>
  const policy = (report.extra.it_policy ?? {}) as Record<string, unknown>
  return (
    <Card>
      <SectionTitle
        title="Kiểm tin ngoài IT"
        hint="Tầng 1: từ khóa tiêu đề. Tầng 2 (tin tầng 1 không quyết được): nhóm nghề IT và ít nhất 2 kỹ năng trong JD. Chỉ bỏ theo preprocessing/clean/it_policy.json. Các cột 'đúng' đo trên tin đã gán nhãn tay."
      />
      <TableShell head={['Nguồn', 'IT', 'Ngoài IT', 'Tầng 2 quyết', 'Đã gán nhãn', 'Ngoài IT đúng', 'Tầng 1 đúng', 'Tầng 2 đúng', 'Chính sách']} alignRightFrom={1}>
        {SOURCES.map((s) => {
          const st = status[s.id] ?? {}
          const lv = levels[s.id] ?? {}
          const rv = review[s.id]
          const pol = policy[s.id]
          return (
            <tr key={s.id}>
              <th scope="row" className="py-2.5 pr-4 font-semibold text-ink whitespace-nowrap">{s.name}</th>
              <td className="py-2.5 pr-4 text-right tabular-nums">{fmt(st.it ?? 0)}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums">{fmt(st.non_it ?? 0)}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums">{fmt((lv.tang_2_it ?? 0) + (lv.tang_2_non_it ?? 0))}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums whitespace-nowrap">{rv ? `${rv.labeled}/${rv.rows}` : '—'}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums">{rv?.status_non_it ? `${rv.status_non_it_correct}/${rv.status_non_it}` : '—'}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums">{rv?.rule_decided ? `${rv.rule_correct}/${rv.rule_decided}` : '—'}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums">{rv?.level2_labeled ? `${rv.level2_correct}/${rv.level2_labeled}` : '—'}</td>
              <td className="py-2.5 pr-4 text-right whitespace-nowrap">{typeof pol === 'string' || !pol ? 'Chưa duyệt' : 'Đã duyệt'}</td>
            </tr>
          )
        })}
      </TableShell>
    </Card>
  )
}

/** Tầng 1: tổng 8 nguồn của bước đang chọn. */
export const StepOverview: React.FC<{ step: string }> = ({ step }) => {
  const { data, error, loading } = useAsync(() => api.preprocessingStep(step), [step])
  if (error) return <ErrorState />
  if (loading && !data) return <LoadingState />
  if (!data) return null
  if (!data.available || !data.report)
    return (
      <Card>
        <EmptyState message="Bước này chưa có báo cáo. Chạy lệnh dưới để tạo bản chạy thử." />
        <Command text={data.command} />
      </Card>
    )
  const r = data.report
  const dropped = r.dropped.reduce((n, d) => n + d.rows, 0)
  const flagged = r.rules.filter((x) => x.action === 'flag').reduce((n, x) => n + x.rows_affected, 0)
  const merged = step !== '01_clean' 
  return (
    <>
      <section aria-label="Tổng của bước" className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          label={merged ? 'Input (đã gộp 8 nguồn)' : 'Input (8 nguồn)'}
          value={fmt(r.input.rows)}
          sub={r.mode === 'dry_run' ? 'Chạy thử: sẽ xử lý' : 'Đã xử lý'}
        />
        <StatCard label="Output" value={fmt(r.output.rows)} sub={`Lần chạy ${when(r.generated_at)} · code ${r.code_version}`} />
        <StatCard label="Bị bỏ" value={fmt(dropped)} sub={r.checks.rows_conserved ? 'Input = output + bị bỏ ✓' : 'Chưa kiểm bảo toàn'} />
        <StatCard label="Lượt gắn cờ cần xem" value={fmt(flagged)} sub="Không bỏ, đi tiếp sang bước sau; xem cột cờ ở bảng dòng" />
      </section>
      <Card>
        <SectionTitle title="Dòng bị bỏ theo luật và nguồn" hint="Mỗi màu là một luật. Di chuột lên cột để xem số." />
        <DropChart rules={r.rules} />
      </Card>
      <Card>
        <SectionTitle title="Các luật của bước, đúng thứ tự chạy" />
        <RuleTable rules={r.rules} inputRows={r.input.rows} />
      </Card>
      {step === '01_clean' && <ItReviewPanel report={r} />}
      {merged && <RuleExamples rules={r.rules} hint="Ví dụ lấy từ các nguồn, tối đa 3 mỗi nguồn." />}
      {merged && <FieldCoverage fields={r.fields} hint="Tính trên bảng đã gộp 8 nguồn." />}
    </>
  )
}

/** Tầng 2: một nguồn, luật kèm ví dụ trước → sau và độ phủ trường. */
export const SourceDetail: React.FC<{
  step: string
  source: string
  prev?: StepSummary
  next?: StepSummary
  onGoStep: (step: string) => void
}> = ({ step, source, prev, next, onGoStep }) => {
  const { data, error, loading } = useAsync(() => api.preprocessingStepSource(step, source), [step, source])
  if (error) return <ErrorState />
  if (loading && !data) return <LoadingState />
  if (!data) return null
  if (!data.available || !data.report)
    return (
      <Card>
        <EmptyState message={`Chưa có báo cáo cho ${sourceName(source)} ở bước này.`} />
        <Command text={data.command} />
      </Card>
    )
  const r = data.report
  return (
    <>
      <Card>
        <SectionTitle
          title={`${sourceName(source)}: ${fmt(r.input.rows)} → ${fmt(r.output.rows)} dòng`}
          hint={<span className="[overflow-wrap:anywhere]">Input: {r.input.path ?? '—'} · Output: {r.output.path ?? '—'}</span>}
        />
        <div className="flex flex-wrap gap-2">
          {prev && (
            <button type="button" onClick={() => onGoStep(prev.step)} className="min-h-9 px-3 rounded-lg border border-line-strong bg-white text-[13px]">
              Input này là output của bước {prev.name}
            </button>
          )}
          {next && (
            <button type="button" onClick={() => onGoStep(next.step)} className="inline-flex items-center gap-1.5 min-h-9 px-3 rounded-lg bg-brand-500 text-white text-[13px] font-medium">
              Xem ở bước {next.name} <ArrowRight className="w-4 h-4" aria-hidden="true" />
            </button>
          )}
        </div>
        {r.checks.notes.map((n) => (
          <p key={n} className="m-0 px-3 py-2 rounded-lg bg-state-partial-bg text-state-partial-fg">{n}</p>
        ))}
      </Card>
      <RuleExamples rules={r.rules} hint="Tối đa 3 ví dụ mỗi luật, chọn ổn định theo job_id." />
      <FieldCoverage fields={r.fields} />
    </>
  )
}

const RuleExamples: React.FC<{ rules: StepRule[]; hint: string }> = ({ rules, hint }) => (
  <Card>
    <SectionTitle title="Luật và ví dụ trước → sau" hint={hint} />
    <div className="flex flex-col gap-4">
      {rules.map((rule) => (
        <div key={rule.id} className="flex flex-col gap-2 min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-3">
            <span className="font-semibold text-ink">{rule.id}</span>
            <span className="text-ink-soft">{rule.name}</span>
            <span className={`tabular-nums ${rule.rows_affected > 0 && rule.action !== 'modify' ? `px-2 rounded-md text-xs font-semibold ${ACTION_BADGE[rule.action]}` : 'text-ink-muted'}`}>
              {ACTION_TEXT[rule.action]} {fmt(rule.rows_affected)} dòng
            </span>
          </div>
          {rule.examples.map((e, i) => (
            <div key={`${rule.id}-${e.job_id}-${i}`} className="pl-3 border-l-2 border-line-strong text-[13px] min-w-0 [overflow-wrap:anywhere]">
              <span className="text-ink-muted">{e.field}: </span>
              <span className="line-through text-ink-faint">{show(e.before)}</span>
              <span className="text-ink-muted"> → </span>
              <span className="font-medium text-brand-700">{show(e.after)}</span>
              {e.url && (
                <a href={e.url} target="_blank" rel="noreferrer" className="ml-2 text-brand-600 underline">
                  tin {e.job_id}
                </a>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  </Card>
)

const FieldCoverage: React.FC<{ fields: StepReportData['fields']; hint?: string }> = ({ fields, hint }) =>
  fields.length ? (
    <Card>
      <SectionTitle title="Độ phủ trường sau bước" hint={hint} />
      <TableShell head={['Trường', 'Có giá trị']} alignRightFrom={2}>
        {fields.map((f) => (
          <tr key={f.field}>
            <th scope="row" className="py-2 pr-4 font-medium text-ink whitespace-nowrap">{f.field}</th>
            <td className="py-2 pr-4 w-full"><PctBar value={f.fill_pct_out ?? null} /></td>
          </tr>
        ))}
      </TableShell>
    </Card>
  ) : null

const STATUS: Record<StorageItem['status'], { text: string; cls: string }> = {
  khop: { text: 'Khớp', cls: 'bg-state-done-bg text-state-done-fg' },
  lech: { text: 'Lệch', cls: 'bg-state-fail-bg text-state-fail-fg' },
  chua_day: { text: 'Chưa đẩy', cls: 'bg-state-partial-bg text-state-partial-fg' },
  khong_ro: { text: 'Không rõ', cls: 'bg-state-idle-bg text-state-idle-fg' },
}

/** So từng key của bước: file trên máy với object trên R2 (silver theo nguồn, gold ở curated/). */
export const StoragePanel: React.FC<{ step: string }> = ({ step }) => {
  const { data, error, loading } = useAsync(() => api.preprocessingStorage(), [])
  if (error) return <ErrorState />
  if (loading && !data) return <LoadingState />
  if (!data) return null
  const items = data.items.filter((i) => i.step === step)
  const count = (st: StorageItem['status']) => items.filter((i) => i.status === st).length
  return (
    <Card>
      <SectionTitle
        title="Lưu trữ: trên máy và trên R2"
        hint={`Bucket ${data.bucket}. So từng key theo thời điểm chạy bước và số dòng ghi trong metadata.`}
      />
      {data.reason && <p className="m-0 px-3 py-2 rounded-lg bg-state-partial-bg text-state-partial-fg">{data.reason}</p>}
      {!items.length ? (
        <EmptyState message="Bước này chưa có file output trên máy." />
      ) : (
        <>
          <p className="m-0 text-ink-soft">
            {count('khop')} khớp · {count('lech')} lệch · {count('chua_day')} chưa đẩy, trên tổng {items.length} key.
          </p>
          <TableShell head={['Nguồn', 'Key trên R2', 'Trên máy', 'Trên R2', 'Trạng thái']} alignRightFrom={2}>
            {items.map((i) => (
              <tr key={i.key}>
                <th scope="row" className="py-2 pr-4 font-medium text-ink whitespace-nowrap">{i.source ? sourceName(i.source) : 'Tất cả'}</th>
                <td className="py-2 pr-4 text-ink-soft [overflow-wrap:anywhere] min-w-[200px]"><code>{i.key}</code></td>
                <td className="py-2 pr-4 text-right tabular-nums">{fmt(i.local_rows)}</td>
                <td className="py-2 pr-4 text-right tabular-nums">{fmt(i.r2_rows)}</td>
                <td className="py-2 pr-4 text-right whitespace-nowrap">
                  <span className={`px-2 py-0.5 rounded-md text-xs font-semibold ${STATUS[i.status].cls}`}>{STATUS[i.status].text}</span>
                </td>
              </tr>
            ))}
          </TableShell>
          {count('khop') < items.length && (
            <p className="m-0 text-ink-muted">
              Đẩy lên R2 cần bạn duyệt: chạy thử bằng lệnh dưới, rồi thêm <code>--push</code>.
              <Command text={data.command} />
            </p>
          )}
        </>
      )}
    </Card>
  )
}

const pick = (row: Record<string, unknown>, path: string): unknown =>
  path.split('.').reduce<unknown>((v, k) => (v && typeof v === 'object' ? (v as Record<string, unknown>)[k] : undefined), row)

// Cột hiện trong bảng dòng theo từng bước; cột cờ tô cam khi bật
const COLUMNS: Record<string, [string, string][]> = {
  '01_clean': [['metadata.source_job_id', 'Mã tin'], ['raw_payload.title', 'Tiêu đề'], ['metadata.clean.it_status', 'IT'], ['metadata.clean.dedup_key', 'Khóa trùng']],
  '02_integration': [['source_platform', 'Nguồn'], ['job_title', 'Tiêu đề'], ['company_name', 'Công ty'], ['raw_salary_text', 'Lương (chữ)'], ['raw_location_text', 'Địa điểm (chữ)'], ['it_status', 'IT']],
  '03_transformation': [['source_platform', 'Nguồn'], ['job_title_clean', 'Tiêu đề'], ['salary_min_vnd', 'Lương từ'], ['salary_max_vnd', 'Lương đến'], ['salary_source', 'Lấy lương từ'], ['language', 'Ngôn ngữ'], ['locations', 'Tỉnh'], ['salary_suspect', 'Nghi sai lương']],
  '04_normalization': [['source_platform', 'Nguồn'], ['job_title_clean', 'Tiêu đề'], ['seniority', 'Cấp bậc'], ['job_family', 'Nhóm nghề'], ['tinh_chinh', 'Tỉnh'], ['salary_max_vnd_capped', 'Lương (đã cắt)'], ['salary_suspect', 'Nghi sai lương'], ['seniority_can_kiem', 'Cấp bậc cần kiểm'], ['job_family_can_kiem', 'Nhóm nghề cần kiểm']],
  '05_encoding': [['job_id_global', 'Mã tin'], ['seniority_ord', 'Cấp bậc (số)'], ['is_remote', 'Remote'], ['tinh__other', 'Tỉnh khác'], ['skills__other_count', 'Kỹ năng khác']],
}
const FLAG_COLS = new Set(['salary_suspect', 'seniority_can_kiem', 'job_family_can_kiem'])

const WIDE_COLS = new Set(['job_title', 'job_title_clean', 'raw_payload.title', 'metadata.clean.dedup_key'])
const IT_TEXT: Record<string, string> = { it: 'IT', non_it: 'Ngoài IT', can_kiem: 'Cần kiểm' }

const needsLook = (row: Record<string, unknown>, cols: [string, string][]) =>
  cols.some(([c]) => (FLAG_COLS.has(c) && pick(row, c)) || (c.endsWith('it_status') && pick(row, c) !== 'it'))

const cell = (col: string, v: unknown): React.ReactNode => {
  if (v === null || v === undefined || v === '') return <span className="text-ink-faint">—</span>
  if (col === 'source_platform' && typeof v === 'string') return sourceName(v)
  if ((col === 'it_status' || col === 'metadata.clean.it_status') && typeof v === 'string')
    return v === 'it' ? IT_TEXT.it : <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-state-partial-bg text-state-partial-fg">{IT_TEXT[v] ?? v}</span>
  if (FLAG_COLS.has(col)) return v ? <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-state-partial-bg text-state-partial-fg">Có</span> : '—'
  if (col === 'locations' && Array.isArray(v)) return v.map((l) => (l as { tinh_thanh?: string }).tinh_thanh ?? '?').join(', ') || '—'
  if (typeof v === 'number') return fmt(Math.round(v * 100) / 100)
  return show(v)
}

/** Bảng dòng dữ liệu của bước (silver 01–04, gold 05), đọc từ R2, chưa có thì đọc file trên máy. */
export const RowSample: React.FC<{ step: string; source: string | null; onSource: (s: string | null) => void }> = ({ step, source, onSource }) => {
  const [offset, setOffset] = React.useState(0)
  const [open, setOpen] = React.useState<number | null>(null)
  const limit = 20
  React.useEffect(() => {
    setOffset(0)
    setOpen(null)
  }, [step, source])
  const { data, error, loading } = useAsync(() => api.preprocessingRows(step, { source, offset, limit, origin: 'r2' }), [step, source, offset])
  const cols = COLUMNS[step] ?? []
  const needSource = step === '01_clean'
  return (
    <Card>
      <SectionTitle
        title={step === '05_encoding' ? 'Dòng dữ liệu gold' : 'Dòng dữ liệu silver'}
        hint="Bấm một dòng để xem đủ các trường. Cột cờ màu cam là tin cần xem lại."
      />
      {step !== '05_encoding' && (
        <div role="group" aria-label="Lọc theo nguồn" className="flex flex-wrap gap-2">
          {!needSource && (
            <button
              type="button"
              aria-pressed={!source}
              onClick={() => onSource(null)}
              className={`min-h-9 px-3 rounded-full text-[13px] border bg-white ${!source ? 'font-semibold border-2 border-brand-500' : 'border-line-strong'}`}
            >
              Tất cả
            </button>
          )}
          {SOURCES.map((s) => (
            <button
              key={s.id}
              type="button"
              aria-pressed={source === s.id}
              onClick={() => onSource(s.id)}
              style={{ borderColor: source === s.id ? s.color : undefined }}
              className={`inline-flex items-center gap-2 min-h-9 px-3 rounded-full text-[13px] border bg-white ${source === s.id ? 'font-semibold border-2' : 'border-line-strong'}`}
            >
              <span className="w-2.5 h-2.5 rounded-sm" style={{ background: s.color }} />
              {s.name}
            </button>
          ))}
        </div>
      )}
      {error && <ErrorState />}
      {loading && !data && <LoadingState />}
      {data && (
        <>
          <p className="m-0 text-ink-soft">
            Đọc từ <strong>{data.origin === 'r2' ? 'R2' : 'file trên máy'}</strong>
            {data.note ? ` (${data.note})` : ''} · dòng {fmt(data.total ? data.offset + 1 : 0)}–{fmt(Math.min(data.offset + data.limit, data.total))} / {fmt(data.total)}
          </p>
          <TableShell head={cols.map(([, h]) => h)} alignRightFrom={99}>
            {data.rows.map((row, i) => (
              <React.Fragment key={i}>
                <tr
                  tabIndex={0}
                  onClick={() => setOpen(open === i ? null : i)}
                  onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), setOpen(open === i ? null : i))}
                  aria-expanded={open === i}
                  className={`cursor-pointer hover:bg-panel ${needsLook(row, cols) ? 'bg-state-partial-bg/30' : ''}`}
                >
                  {cols.map(([c]) => (
                    <td key={c} className={`py-2 pr-4 align-top [overflow-wrap:anywhere] ${WIDE_COLS.has(c) ? 'min-w-[260px] max-w-[420px]' : 'whitespace-nowrap'}`}>
                      {cell(c, pick(row, c))}
                    </td>
                  ))}
                </tr>
                {open === i && (
                  <tr>
                    <td colSpan={cols.length} className="py-2">
                      <pre className="m-0 max-h-96 overflow-auto p-3 rounded-lg bg-panel text-[12px] text-ink-soft whitespace-pre-wrap [overflow-wrap:anywhere]">
                        {JSON.stringify(row, null, 2)}
                      </pre>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </TableShell>
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - limit))} className="min-h-9 px-3 rounded-lg border border-line-strong bg-white text-[13px] disabled:opacity-40">
              Trang trước
            </button>
            <button type="button" disabled={offset + limit >= data.total} onClick={() => setOffset(offset + limit)} className="min-h-9 px-3 rounded-lg border border-line-strong bg-white text-[13px] disabled:opacity-40">
              Trang sau
            </button>
          </div>
        </>
      )}
    </Card>
  )
}
