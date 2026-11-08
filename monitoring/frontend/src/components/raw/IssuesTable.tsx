import React from 'react'
import { sourceName } from '../../constants/sources'
import { FeatureIssue } from '../../types'
import { Card, SectionTitle } from '../ui'

const WHERE_CLASS: Record<string, string> = {
  Scraper: 'bg-state-partial-bg text-state-partial-fg',
  Normalizer: 'bg-state-running-bg text-state-running-fg',
  'Luật chuẩn hóa': 'bg-state-done-bg text-state-done-fg',
}

export const IssuesTable: React.FC<{ source: string; issues: FeatureIssue[] }> = ({ source, issues }) => (
  <Card>
    <SectionTitle
      title={`Vấn đề của ${sourceName(source)} và hướng xử lý`}
      hint="Mỗi feature ghi vấn đề chính ở nguồn này, chỗ cần sửa trong pipeline và cách xử lý."
    />
    <div className="overflow-x-auto">
      <table className="w-full min-w-[820px] border-collapse">
        <thead>
          <tr className="text-left text-xs text-ink-muted">
            <th scope="col" className="font-semibold p-2.5 border-b border-line-strong w-44">Feature</th>
            <th scope="col" className="font-semibold p-2.5 border-b border-line-strong">Vấn đề ở nguồn này</th>
            <th scope="col" className="font-semibold p-2.5 border-b border-line-strong w-40">Sửa ở</th>
            <th scope="col" className="font-semibold p-2.5 border-b border-line-strong">Hướng xử lý</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((row) => (
            <tr key={row.code}>
              <th scope="row" className="text-left font-semibold p-3 border-b border-line align-top">{row.label}</th>
              <td className="p-3 border-b border-line align-top text-ink-soft">{row.problem}</td>
              <td className="p-3 border-b border-line align-top">
                <span className={`inline-block px-2.5 py-0.5 rounded-md text-[13px] font-semibold ${WHERE_CLASS[row.where] ?? 'bg-state-idle-bg text-state-idle-fg'}`}>
                  {row.where}
                </span>
              </td>
              <td className="p-3 border-b border-line align-top">{row.fix}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </Card>
)
