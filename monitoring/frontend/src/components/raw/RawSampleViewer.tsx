import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client'
import { SOURCES, sourceName } from '../../constants/sources'
import { JsonPath, RawSample, SampleHighlight, SampleNote } from '../../types'
import { Card, EmptyState, ErrorState, LoadingState, SectionTitle, useAsync } from '../ui'

interface JsonLine {
  text: string
  tag: SampleHighlight | null
}

const pathKey = (path: JsonPath): string => JSON.stringify(path)

/** Dựng các dòng JSON nguyên bản; phần tử con kế thừa tô màu của phần tử cha. */
const buildLines = (root: unknown, highlights: SampleHighlight[]): JsonLine[] => {
  const tags = new Map(highlights.map((h) => [pathKey(h.path), h]))
  const lines: JsonLine[] = []
  const walk = (value: unknown, key: string | null, depth: number, last: boolean, path: JsonPath, parent: SampleHighlight | null) => {
    const indent = '  '.repeat(depth)
    const prefix = indent + (key !== null ? `${JSON.stringify(key)}: ` : '')
    const comma = last ? '' : ','
    const tag = tags.get(pathKey(path)) ?? parent
    if (Array.isArray(value) || (value !== null && typeof value === 'object')) {
      const isArray = Array.isArray(value)
      const entries: [string | number, unknown][] = isArray
        ? (value as unknown[]).map((v, i) => [i, v])
        : Object.entries(value as Record<string, unknown>)
      if (entries.length === 0) {
        lines.push({ text: `${prefix}${isArray ? '[]' : '{}'}${comma}`, tag })
        return
      }
      lines.push({ text: `${prefix}${isArray ? '[' : '{'}`, tag })
      entries.forEach(([k, v], i) =>
        walk(v, isArray ? null : String(k), depth + 1, i === entries.length - 1, [...path, k], tag),
      )
      lines.push({ text: `${indent}${isArray ? ']' : '}'}${comma}`, tag })
      return
    }
    lines.push({ text: `${prefix}${JSON.stringify(value)}${comma}`, tag })
  }
  walk(root, null, 0, true, [], null)
  return lines
}

const STATUS: Record<SampleNote['status'], { text: string; cls: string }> = {
  ok: { text: 'Chuẩn hóa được', cls: 'bg-state-done-bg text-state-done-fg' },
  warn: { text: 'Cần xem lại', cls: 'bg-state-partial-bg text-state-partial-fg' },
  fallback: { text: 'Suy từ trường khác', cls: 'bg-state-partial-bg text-state-partial-fg' },
  fail: { text: 'Chưa có giá trị', cls: 'bg-state-fail-bg text-state-fail-fg' },
  missing: { text: 'Không có trong raw', cls: 'bg-state-idle-bg text-state-idle-fg' },
}

const lineBackground = (tag: SampleHighlight | null, hover: string | null): string => {
  if (!tag) return ''
  if (tag.kind === 'dup') return 'bg-state-fail-bg'
  return tag.feature === hover ? 'bg-[#FFD966] border-l-[#B07A00]' : 'bg-[#FFF1C2]'
}

const Viewer: React.FC<{ sample: RawSample }> = ({ sample }) => {
  const [hover, setHover] = useState<string | null>(null)
  const lines = useMemo(() => buildLines(sample.raw, sample.highlights), [sample])
  return (
    <>
      <div className="flex flex-wrap justify-between items-center gap-3 p-4 rounded-xl bg-panel">
        <div className="flex flex-col gap-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="px-2 py-0.5 rounded-md text-xs font-semibold text-white" style={{ background: SOURCES.find((s) => s.id === sample.source)?.color }}>
              {sourceName(sample.source)}
            </span>
            <span className="text-[13px] text-ink-muted tabular-nums">#{sample.id}</span>
            <span className="px-2 py-0.5 rounded-md text-xs font-semibold bg-state-done-bg text-state-done-fg">
              Có {sample.features_in_raw}/8 feature trong raw
            </span>
          </div>
          <span className="text-base font-semibold">{sample.title ?? 'Không có tiêu đề'}</span>
          <span className="text-[13px] text-ink-muted">
            Cào lúc {sample.scraped_at ? new Date(sample.scraped_at).toLocaleString('vi-VN') : '—'} · đọc từ{' '}
            {sample.origin === 'local' ? 'máy này' : 'Cloudflare R2'}
          </span>
        </div>
        <div className="flex flex-wrap gap-3 text-[13px] text-[#4E4C5E]">
          <span className="inline-flex items-center gap-1.5"><span className="w-3.5 h-3 rounded-sm bg-[#FFF1C2]" />Chuẩn hóa được</span>
          <span className="inline-flex items-center gap-1.5"><span className="w-3.5 h-3 rounded-sm bg-state-fail-bg" />Dòng lặp, bỏ khi tách</span>
        </div>
      </div>
      <div className="flex flex-wrap gap-5 items-start">
        <div className="flex-[3_1_520px] min-w-0 rounded-xl border border-line-strong bg-[#FBFBFD] max-h-[640px] overflow-auto py-3">
          {lines.map((line, i) => (
            <div key={i} className={`flex items-start pr-3 text-[13px] leading-relaxed border-l-[3px] border-transparent ${lineBackground(line.tag, hover)}`}>
              <span className="flex-[0_0_40px] text-right text-[#A9A6BD] text-xs pr-3 select-none">{i + 1}</span>
              <span className="flex-1 min-w-0 whitespace-pre-wrap break-words">{line.text}</span>
              {line.tag && (
                <span className={`shrink-0 ml-2 px-1.5 rounded text-[11px] font-bold bg-white/70 ${line.tag.kind === 'dup' ? 'text-state-fail-fg' : 'text-state-partial-fg'}`}>
                  {line.tag.feature ?? 'lặp'}
                </span>
              )}
            </div>
          ))}
        </div>
        <div className="flex-[2_1_340px] min-w-0 flex flex-col gap-2 max-h-[640px] overflow-auto">
          {sample.notes.map((note) => (
            <button
              key={note.code}
              type="button"
              onMouseEnter={() => setHover(note.code)}
              onFocus={() => setHover(note.code)}
              onMouseLeave={() => setHover(null)}
              onBlur={() => setHover(null)}
              className={`text-left rounded-xl px-3.5 py-3 flex flex-col gap-1.5 border ${
                hover === note.code ? 'bg-[#FFF8E1] border-[#B07A00]' : 'bg-white border-line-strong'
              }`}
            >
              <span className="flex justify-between items-center gap-2">
                <span className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded-md bg-brand-50 text-brand-700 text-xs font-bold">{note.code}</span>
                  <span className="font-semibold">{note.name}</span>
                </span>
                <span className={`px-2 py-0.5 rounded-md text-xs font-semibold whitespace-nowrap ${STATUS[note.status].cls}`}>{STATUS[note.status].text}</span>
              </span>
              <span className="text-xs text-ink-faint break-words">{note.path ?? 'Không có trường tương ứng trong raw'}</span>
              <span className="text-[13px] break-words"><span className="text-ink-faint">Thô:</span> {note.raw ?? '—'}</span>
              <span className="text-[13px] break-words"><span className="text-ink-faint">Chuẩn hóa thành:</span> <b className="font-semibold">{note.normalized ?? '—'}</b></span>
              <span className="text-[13px] text-[#4E4C5E]">{note.how}</span>
            </button>
          ))}
        </div>
      </div>
    </>
  )
}

export const RawSampleViewer: React.FC<{ source: string; onSourceChange: (id: string) => void }> = ({ source, onSourceChange }) => {
  const list = useAsync(() => api.samples(source), [source])
  const [sampleId, setSampleId] = useState('')
  const ids = list.data?.source === source ? list.data.items : []
  const selected = ids.some((i) => i.id === sampleId) ? sampleId : ids[0]?.id ?? ''
  const detail = useAsync(() => (selected ? api.sample(source, selected) : Promise.resolve(null)), [source, selected])

  useEffect(() => setSampleId(''), [source])

  return (
    <Card>
      <div className="flex flex-wrap justify-between items-end gap-4">
        <SectionTitle
          title="Xem một mẫu dữ liệu raw"
          hint="Chọn nguồn, rồi chọn ID tin. Dòng tô vàng là phần chuẩn hóa được thành feature target; di chuột vào chú thích bên phải để làm nổi bật dòng tương ứng."
        />
        <div className="flex flex-wrap gap-3">
          <label className="flex flex-col gap-1 text-[13px] font-semibold text-ink-soft">
            Nguồn
            <select value={source} onChange={(e) => onSourceChange(e.target.value)} className="min-h-11 min-w-44 px-3 rounded-[10px] border border-[#D6D4E0] bg-white text-sm text-ink">
              {SOURCES.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[13px] font-semibold text-ink-soft">
            ID tin
            <select value={selected} onChange={(e) => setSampleId(e.target.value)} disabled={ids.length === 0} className="min-h-11 min-w-60 max-w-72 px-3 rounded-[10px] border border-[#D6D4E0] bg-white text-sm text-ink">
              {ids.map((item) => (
                <option key={item.id} value={item.id}>
                  #{item.id}{item.title ? ` · ${item.title.slice(0, 30)}` : ''}
                </option>
              ))}
            </select>
          </label>
        </div>
      </div>
      {list.error && <ErrorState />}
      {list.loading && <LoadingState />}
      {!list.loading && ids.length === 0 && !list.error && (
        <EmptyState message={list.data?.unavailable_reason ?? 'Chưa có bản ghi raw.'} />
      )}
      {detail.error && <ErrorState message="Không tải được bản ghi này." />}
      {detail.data && detail.data.id === selected && <Viewer sample={detail.data} />}
    </Card>
  )
}
