import { useState } from 'react'
import type { ClusterPoint } from '../../types'
const colors = ['#5B4CE6', '#059669', '#D97706', '#DB2777', '#0284C7', '#9333EA', '#DC2626', '#475569']
export function CareerClusterScatterCard({ points }: { points: ClusterPoint[] }) {
 const [mode, setMode] = useState<'2D' | '3D'>('2D')
 const [angle, setAngle] = useState({ x: 0.35, y: 0.5 })
 const [zoom, setZoom] = useState(1)
 const has3D = points.some(p => p.pca_z != null && Number.isFinite(p.pca_z))
 const is3D = mode === '3D' && has3D
 const visible = points.filter(p => Number.isFinite(p.pca_x) && Number.isFinite(p.pca_y) && (!is3D || (p.pca_z != null && Number.isFinite(p.pca_z))))
 const scale = visible.reduce((max, p) => Math.max(max, Math.abs(p.pca_x), Math.abs(p.pca_y), Math.abs(p.pca_z ?? 0)), 1)
 const project = (x: number, y: number, z: number) => {
   const a = is3D ? angle.y : 0, b = is3D ? angle.x : 0
   const rx = x * Math.cos(a) + z * Math.sin(a)
   const rz = -x * Math.sin(a) + z * Math.cos(a)
   return [300 + rx / scale * 150 * zoom, 190 - (y * Math.cos(b) - rz * Math.sin(b)) / scale * 150 * zoom]
 }
 return <section className="bg-panel border border-line rounded-xl p-4 space-y-3">
  <h2 className="font-semibold">Phân cụm nghề nghiệp · PCA</h2>
  <div className="flex flex-wrap gap-3 items-center">
   {(['2D', '3D'] as const).map(m => <button className="border border-line rounded px-3 py-1 disabled:opacity-40" aria-pressed={mode === m} disabled={m === '3D' && !has3D} key={m} onClick={() => setMode(m)}>{m}</button>)}
   <label>Zoom <input aria-label="Zoom phân cụm" type="range" min="0.5" max="3" step="0.1" value={zoom} onChange={e => setZoom(Number(e.target.value))}/></label>
   <button onClick={() => { setAngle({x: 0.35, y: 0.5}); setZoom(1) }}>Đặt lại góc nhìn</button>
  </div>
  {!has3D && <p className="text-sm">Chưa có tọa độ PCA Z để xem 3D.</p>}
  {is3D && <p className="text-sm">Kéo để xoay. Chỉ hiển thị {visible.length}/{points.length} tin có đủ tọa độ 3D.</p>}
  {!visible.length ? <p>Chưa có dữ liệu phân cụm · NO_DATA</p> : <svg role="img" aria-label={`Phân cụm PCA ${is3D ? '3D' : '2D'}`} viewBox="0 0 600 380" className="w-full touch-none border border-line rounded" onPointerDown={e => { if(is3D) e.currentTarget.setPointerCapture(e.pointerId) }} onPointerMove={e => { if(is3D && e.currentTarget.hasPointerCapture(e.pointerId)) setAngle(a => ({x: a.x + e.movementY * 0.01, y: a.y + e.movementX * 0.01})) }} onPointerUp={e => { if(e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId) }}>
   {([[scale,0,0,'PC1'],[0,scale,0,'PC2'], ...(is3D ? [[0,0,scale,'PC3']] : [])] as [number,number,number,string][]).map(([x,y,z,label]) => { const [ex,ey] = project(x,y,z); return <g key={label}><line x1="300" y1="190" x2={ex} y2={ey} stroke="#999"/><text x={ex} y={ey}>{label}</text></g> })}
   {visible.map(p => { const [x,y] = project(p.pca_x,p.pca_y,is3D ? p.pca_z! : 0); return <circle key={p.job_id} cx={x} cy={y} r="4" fill={colors[((p.cluster_id % colors.length) + colors.length) % colors.length]} opacity="0.75"><title>{`${p.job_title} · ${p.company_name ?? 'Chưa rõ công ty'} · ${p.cluster_name ?? p.cluster_id} · ${p.salary_avg_vnd == null ? 'Chưa có lương' : p.salary_avg_vnd / 1000000 + ' triệu VNĐ/tháng'} · ${p.source_platform ?? ''}`}</title></circle> })}
  </svg>}
  <div className="flex flex-wrap gap-3 text-sm">{Array.from(new Map(points.map(p => [p.cluster_id,p])).values()).map(p => <span key={p.cluster_id} style={{color: colors[((p.cluster_id % colors.length)+colors.length)%colors.length]}}>{p.cluster_name ?? `Cụm ${p.cluster_id}`}</span>)}</div>
 </section>
}
