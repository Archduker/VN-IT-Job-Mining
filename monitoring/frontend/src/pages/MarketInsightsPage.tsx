import { useEffect, useState } from 'react'
import axios from 'axios'
import type { InsightResponse, InsightOption, SalaryCell, SkillRule, ClusterPoint } from '../types'
import { CareerClusterScatterCard } from '../components/insights/CareerClusterScatterCard'
function useInsight<T>(path: string, params: Record<string, string | number>) {
 const [data, setData] = useState<T[]>([]), [state, setState] = useState('Đang tải…')
 const key = JSON.stringify(params)
 useEffect(() => {
  const controller = new AbortController()
  setData([]); setState('Đang tải…')
  axios.get<InsightResponse<T>>(`/api/v1/insights/${path}`, {params: JSON.parse(key), signal: controller.signal})
   .then(r => { setData(r.data.data ?? []); setState(r.data.status === 'EMPTY' ? 'Chưa có dữ liệu · NO_DATA' : '') })
   .catch(e => { if (!controller.signal.aborted) setState(axios.isAxiosError(e) && e.response?.status === 503 ? 'Không kết nối được Analytics Mart hoặc schema chưa sẵn sàng · MART_UNAVAILABLE' : 'Không tải được dữ liệu. Hãy thử lại bằng nút Làm mới.') })
  return () => controller.abort()
 }, [path, key])
 return {data, state}
}
const levels = ['Thực tập', 'Mới tốt nghiệp', 'Junior', 'Middle', 'Senior', 'Trưởng nhóm/Quản lý']
export function MarketInsightsPage() {
 const [city,setCity] = useState(''), [level,setLevel] = useState(''), [family,setFamily] = useState('')
 const [scope,setScope] = useState('ALL'), [antecedent,setAntecedent] = useState('')
 const [sort,setSort] = useState<'support' | 'confidence' | 'lift'>('lift')
 const [support,setSupport] = useState(0.02), [confidence,setConfidence] = useState(0.5), [lift,setLift] = useState(1.2)
 const options = useInsight<InsightOption>('filters/options', {})
 const salary = useInsight<SalaryCell>('salary-heatmap', {city,level,job_family: family})
 const clusters = useInsight<ClusterPoint>('clusters', {city,level,job_family: family})
 const rules = useInsight<SkillRule>('skill-combos', {min_support: support,min_confidence: confidence,min_lift: lift,job_family_scope:scope,...(antecedent ? {antecedent} : {})})
 const canonicalFamilies = ['Backend', 'Frontend', 'Fullstack', 'Mobile', 'Data/AI', 'DevOps/Cloud', 'Kiểm thử (QA/QC)', 'Bảo mật (Security)', 'Hệ thống/Mạng', 'Phân tích nghiệp vụ (BA)', 'Quản lý SP/DA (PM/PO)', 'Thiết kế UI/UX']
 const families = [...new Set([...canonicalFamilies,...options.data.map(o=>o.job_family).filter(Boolean)])].sort()
 const cities = [...new Set(options.data.map(o=>o.province_norm).filter((v): v is string => Boolean(v)))].sort()
 const actualLevels = [...new Set([...levels,...options.data.map(o=>o.seniority_level).filter((v): v is string => Boolean(v))])]
 const rows = family ? [family] : [...new Set([...canonicalFamilies,...salary.data.map(c=>c.job_family)])]
 return <div className="space-y-5 min-w-0 text-ink">
 <section className="bg-panel border border-line rounded-xl p-4 space-y-3">
  <h1 className="text-xl font-bold">Market Insights</h1><p className="text-sm">Dữ liệu từ PostgreSQL Analytics Mart · kết quả của lần nạp gần nhất.</p>
  <div className="flex flex-wrap gap-3">{[{name:'Tỉnh thành',value:city,set:setCity,items:cities},{name:'Cấp bậc',value:level,set:setLevel,items:actualLevels},{name:'Nhóm nghề',value:family,set:setFamily,items:families}].map(f=><label key={f.name} className="flex flex-col gap-1 w-full sm:w-52">{f.name}<select className="border border-line rounded p-2" value={f.value} onChange={e=>f.set(e.target.value)}><option value="">Tất cả</option>{f.items.map(v=><option key={v}>{v}</option>)}</select></label>)}</div>
  {options.state && <p role="status">{options.state}</p>}
 </section>
 <section className="bg-panel border border-line rounded-xl p-4 space-y-3">
  <h2 className="font-semibold">Lương theo nhóm nghề và cấp bậc · triệu VNĐ/tháng</h2>
  <p className="text-sm">Trung vị; di chuột hoặc chạm vào ô để xem P25–P75 và số mẫu. Lương thỏa thuận và lương ngoài 1–500 triệu không tính vào trung vị.</p>
  {salary.state ? <p role="status">{salary.state}</p> : <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr><th>Nhóm nghề</th>{actualLevels.map(l=><th className="p-2" key={l}>{l}</th>)}</tr></thead><tbody>{rows.map(f=><tr key={f}><th className="p-2 text-left">{f}</th>{actualLevels.map(l=>{const c=salary.data.find(c=>c.job_family===f && c.seniority_level===l); const label=c ? `P25–P75: ${c.q25?.toFixed(1) ?? '—'}–${c.q75?.toFixed(1) ?? '—'}; N=${c.sample_count}; thỏa thuận=${c.negotiable_count}` : 'Chưa có dữ liệu';return <td key={l} className="border border-line text-center p-2" style={{background:c?.median==null ? undefined : `rgba(91,76,230,${0.08+Math.min(c.median/100,0.65)})`}}><details><summary className="cursor-pointer" title={label}>{c?.median?.toFixed(1) ?? '—'}</summary><span className="text-xs">{label}</span></details></td>})}</tr>)}</tbody></table></div>}
 </section>
 <section className="bg-panel border border-line rounded-xl p-4 space-y-3">
  <h2 className="font-semibold">Combo kỹ năng · FP-Growth</h2>
  <label>Sắp xếp giảm dần <select value={sort} onChange={e=>setSort(e.target.value as 'support' | 'confidence' | 'lift')} className="border border-line rounded p-2"><option value="lift">Lift</option><option value="confidence">Confidence</option><option value="support">Support</option></select></label>
  <p className="text-sm">Bộ lọc riêng cho luật đã khai phá; tỉnh và cấp bậc phía trên áp dụng cho lương và phân cụm.</p>
  <div className="flex flex-wrap gap-3"><label>Phạm vi <select className="border border-line p-2 rounded" value={scope} onChange={e=>setScope(e.target.value)}><option value="ALL">Toàn thị trường</option>{families.map(f=><option key={f}>{f}</option>)}</select></label><label>Kỹ năng đã có <input className="border border-line p-2 rounded w-full sm:w-40" value={antecedent} onChange={e=>setAntecedent(e.target.value)} placeholder="Tên kỹ năng chuẩn"/></label>
  {[{name:'Support',value:support,set:setSupport,max:1},{name:'Confidence',value:confidence,set:setConfidence,max:1},{name:'Lift',value:lift,set:setLift,max:100}].map(f=><label key={f.name}>{f.name}<input className="border border-line rounded p-2 w-24 block" type="number" min="0" max={f.max} step="0.01" value={f.value} onChange={e=>{const n=Number(e.target.value);if(Number.isFinite(n)&&n>=0&&n<=f.max)f.set(n)}}/></label>)}</div>
  {rules.state ? <p role="status">{rules.state}</p> : <div className="overflow-x-auto"><table className="w-full text-sm text-left"><thead><tr>{['Kỹ năng đã có','Kỹ năng đi kèm','Support','Confidence','Lift'].map(h=><th className="p-2" key={h}>{h}</th>)}</tr></thead><tbody>{[...rules.data].sort((a,b)=>b[sort]-a[sort]).map((r,i)=><tr key={i}>{[r.antecedents.join(', '),r.consequents.join(', '),(r.support*100).toFixed(1)+'%',(r.confidence*100).toFixed(1)+'%',r.lift.toFixed(2)].map((v,j)=><td className="p-2 border-t border-line" key={j}>{v}</td>)}</tr>)}</tbody></table></div>}
 </section>
 {clusters.state ? <section className="bg-panel border border-line rounded-xl p-4"><h2 className="font-semibold">Phân cụm nghề nghiệp</h2><p role="status">{clusters.state}</p></section> : <CareerClusterScatterCard points={clusters.data}/>}
 </div>
}
