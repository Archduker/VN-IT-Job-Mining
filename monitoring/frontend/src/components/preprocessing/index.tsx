import React from 'react'
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { ArrowRight } from 'lucide-react'
import { api } from '../../api/client'
import { SOURCES, sourceName } from '../../constants/sources'
import { ItReview, StepApiUsage, StepReportData, StepRule, StepSummary } from '../../types'
import { PctBar, TableShell, pct } from '../reports'
import { Card, EmptyState, ErrorState, LoadingState, SectionTitle, StatCard, fmt, useAsync } from '../ui'

const RULE_COLORS = ['#5B4CE6', '#E08A1E', '#2F7D5B', '#C2362F', '#14A3A3', '#9C2F7A', '#2F6FD6', '#D4A72C']
const ACTION_TEXT: Record<StepRule['action'], string> = { drop: 'Bỏ', flag: 'Gắn cờ', modify: 'Sửa' }
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
      <tr key={r.id}>
        <th scope="row" className="py-2.5 pr-4 font-semibold text-ink whitespace-nowrap">{r.id}</th>
        <td className="py-2.5 pr-4 min-w-[220px]">{r.name}</td>
        <td className="py-2.5 pr-4 whitespace-nowrap">{ACTION_TEXT[r.action]}</td>
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

export const ApiUsage: React.FC<{ api: StepApiUsage }> = ({ api: a }) => (
  <p className="m-0 text-ink-soft [overflow-wrap:anywhere]">
    {a.used
      ? `API ${a.model ?? ''}: ${fmt(a.calls)} lần gọi, ${fmt(a.cache_hits)} lần lấy từ cache, ${a.cost_usd ?? 0} USD.`
      : a.would_call
        ? `Chạy thử: sẽ gọi API ${fmt(a.would_call)} lần, ước tính ${a.estimated_cost_usd} USD.`
        : `Không dùng API${a.reason ? `: ${a.reason}` : ''}.`}
  </p>
)

/** Khối riêng của bước Clean: kiểm tin ngoài IT ở cả 8 nguồn, chưa bỏ khi chưa có chính sách được duyệt. */
export const ItReviewPanel: React.FC<{ report: StepReportData }> = ({ report }) => {
  const status = (report.extra.it_status ?? {}) as Record<string, Record<string, number>>
  const review = (report.extra.review ?? {}) as Record<string, ItReview>
  const policy = (report.extra.it_policy ?? {}) as Record<string, unknown>
  return (
    <Card>
      <SectionTitle
        title="Kiểm tin ngoài IT"
        hint="Phân loại bằng luật từ khóa và JEV. Chỉ bỏ theo preprocessing/clean/it_policy.json do bạn duyệt. 'Ngoài IT đúng': trong các tin đã gán nhãn mà hệ thống xếp ngoài IT (nhóm chính sách sẽ bỏ), bao nhiêu tin đúng là ngoài IT."
      />
      <TableShell head={['Nguồn', 'IT', 'Ngoài IT', 'Cần kiểm', 'Đã gán nhãn', 'Ngoài IT đúng', 'Luật đúng', 'JEV đúng', 'Chính sách']} alignRightFrom={1}>
        {SOURCES.map((s) => {
          const st = status[s.id] ?? {}
          const rv = review[s.id]
          const pol = policy[s.id]
          return (
            <tr key={s.id}>
              <th scope="row" className="py-2.5 pr-4 font-semibold text-ink whitespace-nowrap">{s.name}</th>
              <td className="py-2.5 pr-4 text-right tabular-nums">{fmt(st.it ?? 0)}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums">{fmt(st.non_it ?? 0)}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums">{fmt(st.can_kiem ?? 0)}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums whitespace-nowrap">{rv ? `${rv.labeled}/${rv.rows}` : '—'}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums">{rv?.status_non_it ? `${rv.status_non_it_correct}/${rv.status_non_it}` : '—'}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums">{rv?.rule_decided ? `${rv.rule_correct}/${rv.rule_decided}` : '—'}</td>
              <td className="py-2.5 pr-4 text-right tabular-nums">{rv?.jev_labeled ? `${rv.jev_correct}/${rv.jev_labeled}` : '—'}</td>
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
  const flagged = r.rules.filter((x) => x.action !== 'drop').reduce((n, x) => n + x.rows_affected, 0)
  return (
    <>
      <section aria-label="Tổng của bước" className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label="Input (8 nguồn)" value={fmt(r.input.rows)} sub={r.mode === 'dry_run' ? 'Chạy thử: sẽ xử lý' : 'Đã xử lý'} />
        <StatCard label="Output" value={fmt(r.output.rows)} sub={`Lần chạy ${when(r.generated_at)} · code ${r.code_version}`} />
        <StatCard label="Bị bỏ" value={fmt(dropped)} sub={r.checks.rows_conserved ? 'Input = output + bị bỏ ✓' : 'Chưa kiểm bảo toàn'} />
        <StatCard label="Gắn cờ hoặc sửa" value={fmt(flagged)} sub="Không bỏ, đi tiếp sang bước sau" />
      </section>
      <Card>
        <SectionTitle title="Dòng bị bỏ theo luật và nguồn" hint="Mỗi màu là một luật. Di chuột lên cột để xem số." />
        <DropChart rules={r.rules} />
      </Card>
      <Card>
        <SectionTitle title="Các luật của bước, đúng thứ tự chạy" />
        <RuleTable rules={r.rules} inputRows={r.input.rows} />
        <ApiUsage api={r.api} />
      </Card>
      {step === '01_clean' && <ItReviewPanel report={r} />}
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
      <Card>
        <SectionTitle title="Luật và ví dụ trước → sau" hint="Tối đa 3 ví dụ mỗi luật, chọn ổn định theo job_id." />
        <div className="flex flex-col gap-4">
          {r.rules.map((rule) => (
            <div key={rule.id} className="flex flex-col gap-2 min-w-0">
              <div className="flex flex-wrap items-baseline gap-x-3">
                <span className="font-semibold text-ink">{rule.id}</span>
                <span className="text-ink-soft">{rule.name}</span>
                <span className="text-ink-muted tabular-nums">
                  {ACTION_TEXT[rule.action]} {fmt(rule.rows_affected)} dòng
                </span>
              </div>
              {rule.examples.map((e) => (
                <div key={`${rule.id}-${e.job_id}`} className="pl-3 border-l-2 border-line-strong text-[13px] min-w-0 [overflow-wrap:anywhere]">
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
      {r.fields.length > 0 && (
        <Card>
          <SectionTitle title="Độ phủ trường trước và sau bước" />
          <TableShell head={['Trường', 'Trước', 'Sau']} alignRightFrom={3}>
            {r.fields.map((f) => (
              <tr key={f.field}>
                <th scope="row" className="py-2 pr-4 font-medium text-ink whitespace-nowrap">{f.field}</th>
                <td className="py-2 pr-4"><PctBar value={f.fill_pct_in ?? null} /></td>
                <td className="py-2 pr-4"><PctBar value={f.fill_pct_out ?? null} /></td>
              </tr>
            ))}
          </TableShell>
        </Card>
      )}
    </>
  )
}
