import axios from 'axios'
import {
  AirflowStatusResponse,
  CloudHealth,
  CollectionMonitor,
  DashboardReport,
  EdaCharts,
  EdaCompare,
  EdaSummary,
  FieldInventoryItem,
  PreprocessingReport,
  ProcessingReport,
  RawSample,
  SampleList,
  SourceOverviewItem,
  SourceReport,
  Univariate,
} from '../types'

const http = axios.create({ baseURL: '/api/v1' })

const get = async <T,>(url: string, params?: Record<string, string | number>): Promise<T> =>
  (await http.get<T>(url, { params })).data

export const api = {
  collection: (days: number) => get<CollectionMonitor>('/monitor/collection', { days }),
  sources: () => get<SourceOverviewItem[]>('/monitor/sources'),
  report: (source: string) => get<SourceReport>(`/monitor/sources/${source}/report`),
  univariate: (source: string, code: string) =>
    get<Univariate>(`/monitor/sources/${source}/univariate/${code}`),
  samples: (source: string) => get<SampleList>(`/monitor/sources/${source}/samples`),
  sample: (source: string, id: string) =>
    get<RawSample>(`/monitor/sources/${source}/samples/${encodeURIComponent(id)}`),
  r2Status: () => get<CloudHealth>('/cloud/r2/status'),
  airflowStatus: () => get<AirflowStatusResponse>('/orchestration/airflow/status'),
  preprocessing: () => get<PreprocessingReport>('/preprocessing/metrics'),
  processing: () => get<ProcessingReport>('/processing/metrics'),
  dashboard: () => get<DashboardReport>('/dashboard'),
  edaInventory: (source: string) => get<FieldInventoryItem[]>(`/eda/${source}/inventory`),
  edaSummary: (source: string) => get<EdaSummary>(`/eda/${source}/summary`),
  edaCharts: (source: string) => get<EdaCharts>(`/eda/${source}/charts`),
  edaCompare: () => get<EdaCompare>('/eda/compare'),
}
