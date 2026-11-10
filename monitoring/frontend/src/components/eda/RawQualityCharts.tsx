import React from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { EdaSummary, FieldInventoryItem } from '../../types'
import { Card, EmptyState, SectionTitle, StatCard, fmt } from '../ui'

export const RawQualityCharts: React.FC<{ summary: EdaSummary; inventory: FieldInventoryItem[] }> = ({ summary, inventory }) => {
  const ready = summary.raw_scan?.status === 'COMPLETE'
  const duplicates = ready ? summary.raw_scan?.duplicates : null
  const rows = [...inventory].sort((a,b) => b.null_rate_pct - a.null_rate_pct)
  return <>
    <Card><SectionTitle title="Duplicate · bản ghi raw trùng nội dung" hint="Đối chiếu SHA-256 của toàn bộ payload JSON đã sắp xếp key; bỏ metadata envelope. Bản ghi dư = tổng bản ghi − payload khác nhau. Bao gồm mọi phiên bản trong nguồn đang chọn; chưa đo trùng ngữ nghĩa hoặc trùng liên nguồn." />
      {duplicates ? <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard label="Raw đã quét" value={fmt(duplicates.records)} sub="Từng bản ghi trong file batch được đếm riêng." />
        <StatCard label="Payload khác nhau" value={fmt(duplicates.unique_payloads)} sub="So nội dung JSON chính xác, không phải số tin unique." />
        <StatCard label="Bản ghi trùng dư" value={fmt(duplicates.duplicate_records)} sub={`${duplicates.duplicate_pct ?? '—'}% tổng raw · ${fmt(duplicates.duplicate_groups)} nhóm trùng.`} />
        <StatCard label="Object dư theo ID filename" value={fmt(duplicates.extra_version_objects)} sub={`${fmt(duplicates.filename_ids)} ID filename; bỏ hậu tố _vN, không khẳng định nội dung giống nhau.`} />
      </div> : <EmptyState message={ready
        ? 'Backend đã quét xong nhưng chưa trả thống kê duplicate. Khởi động lại backend để nạp code mới, rồi quét lại nguồn này.'
        : summary.raw_scan?.status === 'ERROR'
          ? 'Lượt quét raw bị lỗi; chưa thể tính duplicate. Kiểm tra lỗi ở phần tiến độ và thử quét lại.'
          : `Đang chờ quét raw hoàn tất · ${fmt(summary.raw_scan?.records)} bản ghi đã đọc. Thống kê duplicate chỉ xuất hiện khi COMPLETE.`} />}
    </Card>
    <Card><SectionTitle title="Bar chart · missing value theo trường" hint={`Mẫu số: ${fmt(summary.sampled_records)} bản ghi raw của toàn bộ lượt quét nguồn đang chọn. Thiếu trường, null và chuỗi rỗng được tính thiếu; mảng/dict rỗng và chuỗi 'N/A' chưa được quy về null. Hiển thị tất cả trường, không lấy Top N.`} />
      {ready && rows.length ? <div className="max-h-[640px] overflow-y-auto"><div style={{height:Math.max(240,rows.length*32)}}>
        <ResponsiveContainer width="100%" height="100%"><BarChart data={rows} layout="vertical" margin={{left:0,right:24,top:8,bottom:16}}>
          <CartesianGrid horizontal={false} stroke="#ECEBF2" /><XAxis type="number" domain={[0,100]} unit="%" /><YAxis type="category" dataKey="field_name" width={150} tick={{fontSize:11}} interval={0} />
          <Tooltip contentStyle={{background:'#1C1B26',border:0,color:'#fff'}} itemStyle={{color:'#fff'}} formatter={(v: number, _name: string, item) => [`${v.toFixed(2)}% · ${fmt(item.payload.null_count)} bản ghi thiếu`, 'Missing']} /><Bar dataKey="null_rate_pct" name="Missing (%)" fill="#5B4CE6" radius={[0,4,4,0]} />
        </BarChart></ResponsiveContainer>
      </div></div> : <EmptyState message="Chưa có kiểm kê raw hoàn tất." />}
    </Card>
  </>
}
