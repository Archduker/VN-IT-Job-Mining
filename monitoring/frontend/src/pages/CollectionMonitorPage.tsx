import React, { useEffect, useState } from 'react'
import { api } from '../api/client'
import { DailyChart } from '../components/collection/DailyChart'
import { Card, EmptyState, ErrorState, LoadingState, SectionTitle, StatCard, fmt, useAsync } from '../components/ui'
import { sourceName } from '../constants/sources'

export const CollectionMonitorPage: React.FC = () => {
  const [days, setDays] = useState<7 | 14>(14)
  const [tick, setTick] = useState(0)
  const { data, error, loading } = useAsync(() => api.collection(days), [days, tick])
  useEffect(() => { const id = setInterval(() => setTick(t => t + 1), 60000); return () => clearInterval(id) }, [])
  if (error) return <ErrorState message="Không đọc được Collection từ R2. Kiểm tra cấu hình và quyền đọc bucket; không dùng số liệu local để thay thế." />
  if (loading || !data) return <LoadingState />
  const totalWindow = data.days.reduce((sum, d) => sum + d.total, 0)
  return <div className="flex flex-col gap-6">
    <div className="flex flex-wrap justify-between gap-3 items-center">
      <p className="text-sm text-ink-muted">Cloudflare R2 trực tiếp · cache 60 giây · tuổi cache {data.cache_age_seconds} giây</p>
      <div role="group" aria-label="Khoảng thời gian" className="flex gap-2">{([7,14] as const).map(n => <button key={n} aria-pressed={days===n} onClick={() => setDays(n)} className={`rounded-lg px-4 py-2 border border-line ${days===n ? 'bg-brand-500 text-white' : 'bg-panel'}`}>{n} ngày</button>)}</div>
    </div>
    <section className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4" aria-label="Thống kê R2">
      <StatCard label="Object raw JSON trên R2" value={fmt(data.raw_objects)} sub="Có thể gồm nhiều phiên bản của một tin; không phải số tin unique." />
      <StatCard label={`Object thuộc ${days} ngày gần nhất`} value={fmt(totalWindow)} sub="Theo ngày trong key raw/nguồn/YYYY-MM-DD/." />
      <StatCard label="Dung lượng raw (MiB)" value={(data.bytes / 1048576).toFixed(2)} sub="Tổng dung lượng object JSON được liệt kê." />
      <StatCard label="Nguồn có Ledger" value={`${data.sources.filter(s => s.ledger !== null).length}/${data.sources.length}`} sub={`${fmt(data.undated_objects)} object không có ngày hợp lệ trong key.`} />
    </section>
    <Card><SectionTitle title="Dữ liệu thu thập trên R2" hint="Ngày trong key thể hiện phân vùng raw, LastModified thể hiện lần upload/ghi gần nhất. Ledger là ảnh chụp trạng thái URL hiện tại. Các chỉ số này không xác định lịch sử chạy DAG hoặc tỷ lệ chạy thành công." /></Card>
    <DailyChart days={data.days} hasData={data.has_data} />
    <Card><SectionTitle title="Kiểm kê theo nguồn và trạng thái URL Ledger" hint="PENDING/DONE/RECHECK_DUE/FAILED/CLOSED lấy nguyên trạng thái đã ghi; FAILED là trạng thái URL, không phải số lần DAG thất bại. Thiếu Ledger hiển thị —." />
      <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr>{['Nguồn','Raw JSON','URL Ledger','PENDING','DONE','RECHECK_DUE','FAILED','CLOSED','Khác','Upload raw gần nhất'].map(h => <th key={h} className="p-3 text-left whitespace-nowrap">{h}</th>)}</tr></thead><tbody>
        {data.sources.map(s => <tr key={s.source} className="border-t border-line"><th scope="row" className="p-3 text-left">{sourceName(s.source)}</th><td className="p-3">{fmt(s.raw_objects)}</td><td className="p-3">{s.ledger === null ? '—' : fmt(Object.values(s.ledger).reduce((a,b) => a+b,0))}</td>{['PENDING','DONE','RECHECK_DUE','FAILED','CLOSED'].map(status => <td key={status} className="p-3">{s.ledger === null ? '—' : fmt(s.ledger[status] ?? 0)}</td>)}<td className="p-3">{s.ledger === null ? '—' : fmt(Object.entries(s.ledger).filter(([k]) => !['PENDING','DONE','RECHECK_DUE','FAILED','CLOSED'].includes(k)).reduce((a,[,v]) => a+v,0))}</td><td className="p-3 whitespace-nowrap">{s.latest_upload ? new Date(s.latest_upload).toLocaleString('vi-VN', {timeZone:'Asia/Ho_Chi_Minh'}) : '—'}</td></tr>)}
      </tbody></table></div>
      {!data.has_data && <EmptyState message="R2 chưa có object raw JSON của các nguồn đang theo dõi." />}
    </Card>
  </div>
}
