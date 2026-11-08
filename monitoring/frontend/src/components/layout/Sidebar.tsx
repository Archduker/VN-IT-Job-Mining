import React from 'react'
import { NavLink } from 'react-router-dom'
import {
  BarChart3,
  Cloud,
  Cpu,
  Database,
  FileCheck2,
  GitMerge,
  LayoutDashboard,
  LucideIcon,
  Radio,
  Settings2,
  Table2,
} from 'lucide-react'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

const MAIN: NavItem[] = [
  { to: '/insights', label: 'Market Insights', icon: BarChart3 },
  { to: '/', label: 'Collection', icon: LayoutDashboard },
  { to: '/raw', label: 'Raw', icon: BarChart3 },
  { to: '/crawling', label: 'Cấu hình cào', icon: Settings2 },
]

const TOOLS: NavItem[] = [
  { to: '/airflow', label: 'Airflow', icon: Cpu },
  { to: '/cloud', label: 'Cloudflare R2', icon: Cloud },
  { to: '/eda', label: 'EDA', icon: Radio },
  { to: '/preprocessing', label: 'Pre-processing', icon: FileCheck2 },
  { to: '/processing', label: 'Processing', icon: GitMerge },
  { to: '/master', label: 'Master Dashboard', icon: Table2 },
]

const linkClass = ({ isActive }: { isActive: boolean }): string =>
  `flex items-center gap-3 min-h-11 px-3 rounded-[10px] no-underline whitespace-nowrap ${
    isActive ? 'bg-nav-active text-white font-semibold' : 'text-nav-text hover:bg-nav-active/60'
  }`

const Item: React.FC<{ item: NavItem }> = ({ item }) => (
  <NavLink to={item.to} end={item.to === '/'} className={linkClass}>
    <item.icon className="w-[18px] h-[18px]" aria-hidden="true" />
    <span>{item.label}</span>
  </NavLink>
)

export const Sidebar: React.FC = () => (
  <nav
    aria-label="Điều hướng chính"
    className="bg-nav text-[#E6E4F0] lg:w-60 lg:shrink-0 p-4 lg:pt-6 flex lg:flex-col gap-1 overflow-x-auto lg:sticky lg:top-0 lg:h-screen lg:overflow-y-auto"
  >
    <div className="flex items-center gap-2.5 px-2.5 lg:pb-6 shrink-0">
      <div className="w-[34px] h-[34px] rounded-[10px] bg-brand-500 flex items-center justify-center">
        <Database className="w-[18px] h-[18px] text-white" aria-hidden="true" />
      </div>
      <div className="hidden lg:flex flex-col">
        <span className="font-bold text-[15px]">JobCrawl</span>
        <span className="text-xs text-[#A9A6BD]">Dữ liệu tuyển dụng IT</span>
      </div>
    </div>
    {MAIN.map((item) => (
      <Item key={item.to} item={item} />
    ))}
    <p className="hidden lg:block mt-5 mb-1 px-3 text-xs font-semibold text-[#A9A6BD]">Công cụ khác</p>
    {TOOLS.map((item) => (
      <Item key={item.to} item={item} />
    ))}
  </nav>
)
