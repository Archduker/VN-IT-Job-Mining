export const SOURCES = [
  { id: 'topcv', name: 'TopCV', color: '#2F7D5B' },
  { id: 'vietnamworks', name: 'VietnamWorks', color: '#E08A1E' },
  { id: 'itviec', name: 'ITviec', color: '#C2362F' },
  { id: 'careerviet', name: 'CareerViet', color: '#2F6FD6' },
  { id: 'jobsgo', name: 'JobsGO', color: '#0E4C73' },
  { id: 'glints', name: 'Glints', color: '#14A3A3' },
  { id: 'vieclam24h', name: 'Vieclam24h', color: '#9C2F7A' },
  { id: 'topdev', name: 'TopDev', color: '#D4A72C' },
] as const

export type SourceId = (typeof SOURCES)[number]['id']

export const sourceName = (id: string): string =>
  SOURCES.find((s) => s.id === id)?.name ?? id
