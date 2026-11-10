import React from 'react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { EdaExploration } from '../../types'
import { Card, EmptyState, SectionTitle, fmt } from '../ui'

const tooltipStyle = { backgroundColor: '#1C1B26', border: 'none', borderRadius: 8, color: '#fff' }

const Matrix: React.FC<{ cells: { x: string; y: string; value: number | null; count?: number }[]; correlation?: boolean }> = ({ cells, correlation }) => {
  if (!cells.length) return <EmptyState message="Thiếu tỉnh/thành hoặc cấp bậc đã chuẩn hóa." />
  const columns = [...new Set(cells.map(c => c.x))]
  const rows = [...new Set(cells.map(c => c.y))]
  const max = Math.max(1, ...cells.map(c => Math.abs(c.value ?? 0)))
  return <div className="overflow-x-auto"><table className="w-full text-xs border-separate border-spacing-1">
    <thead><tr><th scope="col" className="p-2 text-left">{correlation ? 'Biến' : 'Tỉnh/thành'}</th>{columns.map(c => <th scope="col" className="p-2 min-w-24" key={c}>{c}</th>)}</tr></thead>
    <tbody>{rows.map(y => <tr key={y}><th scope="row" className="text-left p-2 font-medium">{y}</th>{columns.map(x => {
      const cell = cells.find(c => c.x === x && c.y === y)
      const v = cell?.value ?? null
      const strength = v === null ? 0 : Math.abs(v) / max
      return <td key={x} className="p-3 text-center rounded font-semibold tabular-nums" style={{ backgroundColor: v === null ? '#F4F4F7' : `rgba(${v < 0 ? '219,91,60' : '91,76,230'},${0.08 + strength * 0.85})`, color: strength > .55 ? '#fff' : '#1C1B26' }}>
        <span tabIndex={0} title={`${y} × ${x}: ${v === null ? 'Không đủ dữ liệu hoặc biến không đổi' : v.toFixed(correlation ? 3 : 0)}${cell?.count !== undefined ? `; n=${cell.count}` : ''}`}>{v === null ? '—' : correlation ? v.toFixed(2) : fmt(v)}</span>
      </td>
    })}</tr>)}</tbody>
  </table></div>
}

export const ExplorationCharts: React.FC<{ data?: EdaExploration }> = ({ data }) => {
  if (!data) return <Card><EmptyState message="Chưa có kết quả phân tích mở rộng. Cập nhật và khởi động lại backend." /></Card>
  const maxBox = Math.max(1, ...data.boxes.map(b => b.high))
  const scale = (v: number) => 165 + v / maxBox * 600
  return <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
    <Card><SectionTitle title="Scatter · kinh nghiệm và lương" hint={`${fmt(data.scatter.length)}/${fmt(data.scatter_total)} tin đủ hai biến; tối đa ${fmt(data.scatter_limit)} dòng đầu tiên, không phải mẫu ngẫu nhiên. Lương là trung bình các cận dương (triệu VND).`} />
      {data.scatter.length ? <div className="h-72"><ResponsiveContainer width="100%" height="100%"><ScatterChart margin={{ bottom: 24, right: 20 }}>
        <CartesianGrid stroke="#ECEBF2" /><XAxis type="number" dataKey="experience" name="Kinh nghiệm tối thiểu" unit=" năm" /><YAxis type="number" dataKey="salary" name="Lương" unit=" tr" width={60} />
        <Tooltip contentStyle={tooltipStyle} itemStyle={{ color: '#fff' }} cursor={{ strokeDasharray: '3 3' }} /><Scatter data={data.scatter} fill="#5B4CE6" fillOpacity={.55} />
      </ScatterChart></ResponsiveContainer></div> : <EmptyState message="Chưa có tin đủ lương dạng số và kinh nghiệm tối thiểu." />}
    </Card>
    <Card><SectionTitle title="Line chart · phân phối lương tích lũy" hint="Trục X: triệu VND. Trục Y: % tin có lương ≤ mức đang xem. Chỉ tính tin có cận lương dương; không phân tích theo ngày." />
      {data.salary_curve.length ? <div className="h-72"><ResponsiveContainer width="100%" height="100%"><LineChart data={data.salary_curve} margin={{ bottom: 24, right: 20 }}>
        <CartesianGrid stroke="#ECEBF2" /><XAxis type="number" dataKey="salary" unit=" tr" /><YAxis domain={[0, 100]} unit="%" width={55} /><Tooltip contentStyle={tooltipStyle} itemStyle={{ color: '#fff' }} labelFormatter={v => `${v} triệu VND`} /><Line name="Tỉ lệ tích lũy (%)" type="stepAfter" dataKey="cumulative_pct" stroke="#5B4CE6" dot={false} />
      </LineChart></ResponsiveContainer></div> : <EmptyState message="Chưa có lương dạng số." />}
    </Card>
    <Card className="xl:col-span-2"><SectionTitle title="Box plot · lương và ngoại lai IQR theo tỉnh/thành" hint="Hộp: Q1–Q3; vạch giữa: trung vị. Râu kết thúc tại giá trị thực trong Q1 − 1,5×IQR đến Q3 + 1,5×IQR. Chỉ nhóm có ít nhất 4 tin có lương; ngoại lai được đếm, không bị xóa." />
      {data.boxes.length ? <><div className="overflow-x-auto"><svg role="img" aria-label="Box plot lương theo tỉnh thành, đơn vị triệu VND" viewBox={`0 0 820 ${data.boxes.length * 54 + 32}`} className="w-full min-w-[600px]">
        {data.boxes.map((b, i) => { const y = i * 54 + 24; return <g key={b.label}><title>{`${b.label}: n=${b.count}; Q1=${b.q1.toFixed(2)}; median=${b.median.toFixed(2)}; Q3=${b.q3.toFixed(2)}; râu ${b.low.toFixed(2)}–${b.high.toFixed(2)}; ${b.outliers} ngoại lai`}</title>
          <text x={0} y={y + 4} fontSize={12} fill="#1C1B26">{b.label}</text><line x1={scale(b.low)} x2={scale(b.high)} y1={y} y2={y} stroke="#5B4CE6" />
          {[b.low, b.high].map((v, j) => <line key={j} x1={scale(v)} x2={scale(v)} y1={y - 8} y2={y + 8} stroke="#5B4CE6" />)}
          <rect x={scale(b.q1)} y={y - 12} width={Math.max(1, scale(b.q3) - scale(b.q1))} height={24} fill="#DAD5FA" stroke="#5B4CE6" /><line x1={scale(b.median)} x2={scale(b.median)} y1={y - 12} y2={y + 12} stroke="#1C1B26" strokeWidth={2} />
        </g> })}
        {[0, .25, .5, .75, 1].map(t => <text key={t} x={scale(t * maxBox)} y={data.boxes.length * 54 + 20} fontSize={12} textAnchor="middle">{(t * maxBox).toFixed(1)}</text>)}
      </svg></div><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr>{['Tỉnh/thành', 'Tin có lương', 'Trung vị (triệu)', 'IQR (triệu)', 'Ngưỡng dưới / trên', 'Ngoại lai'].map(h => <th className="text-left p-2" key={h}>{h}</th>)}</tr></thead><tbody>{data.boxes.map(b => <tr key={b.label} className="border-t border-line"><th scope="row" className="text-left p-2 font-medium">{b.label}</th><td className="p-2">{fmt(b.count)}</td><td className="p-2">{b.median.toFixed(2)}</td><td className="p-2">{(b.q3 - b.q1).toFixed(2)}</td><td className="p-2">{b.lower_fence.toFixed(2)} / {b.upper_fence.toFixed(2)}</td><td className="p-2">{fmt(b.outliers)}</td></tr>)}</tbody></table></div></> : <EmptyState message="Chưa có tỉnh/thành đủ 4 tin có lương dạng số." />}
    </Card>
    <Card><SectionTitle title="Heatmap · tỉnh/thành × cấp bậc" hint="Số tin theo Top 8 tỉnh/thành và Top 6 cấp bậc có dữ liệu. Ô 0 là không có tin cho tổ hợp đó; giá trị thiếu không được điền thành nhóm giả." /><Matrix cells={data.heatmap} /></Card>
    <Card><SectionTitle title="Ma trận tương quan Pearson" hint="Lương min/max/trung bình, kinh nghiệm min/max, số lượng tuyển, số kỹ năng và số từ mô tả JD. Mỗi cặp dùng các dòng đủ hai giá trị; cần ≥3 dòng và biến có phương sai. Cam: âm, tím: dương; —: không tính được. Tương quan không thể hiện quan hệ nhân quả." /><Matrix cells={data.correlation} correlation /></Card>
  </div>
}
