import axios from 'axios'
import {
  AirflowStatusResponse,
  CloudHealth,
  R2Collection,
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
  StepResponse,
  StepRowsResponse,
  StorageResponse,
  StepSummary,
  Univariate,
} from '../types'

const http = axios.create({ baseURL: '/api/v1' })

const get = async <T,>(url: string, params?: Record<string, string | number>): Promise<T> =>
  (await http.get<T>(url, { params })).data

export const api = {
  collection: (days: number) => get<R2Collection>('/monitor/collection', { days }),
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
  preprocessingSteps: () => get<StepSummary[]>('/preprocessing/steps'),
  preprocessingStep: (step: string) => get<StepResponse>(`/preprocessing/steps/${step}`),
  preprocessingStepSource: (step: string, source: string) =>
    get<StepResponse>(`/preprocessing/steps/${step}/${source}`),
  preprocessingStorage: () => get<StorageResponse>('/preprocessing/storage'),
  preprocessingRows: (step: string, q: { source?: string | null; offset: number; limit: number; origin: 'r2' | 'local' }) =>
    get<StepRowsResponse>(
      `/preprocessing/steps/${step}/rows?${new URLSearchParams({
        ...(q.source ? { source: q.source } : {}),
        offset: String(q.offset),
        limit: String(q.limit),
        origin: q.origin,
      })}`,
    ),
  processing: () => get<ProcessingReport>('/processing/metrics'),
  dashboard: () => get<DashboardReport>('/dashboard'),
  refreshEdaScan: (source: string) => http.post(`/eda/${source}/scan`),
  edaInventory: (source: string, origin: 'local' | 'r2' = 'local') => get<FieldInventoryItem[]>(`/eda/${source}/inventory`, { origin }),
  edaSummary: (source: string, origin: 'local' | 'r2' = 'local') => get<EdaSummary>(`/eda/${source}/summary`, { origin }),
  edaCharts: (source: string, origin: 'local' | 'r2' = 'local') => get<EdaCharts>(`/eda/${source}/charts`, { origin }),
  edaCompare: (origin: 'local' | 'r2' = 'local') => get<EdaCompare>('/eda/compare', { origin }),
}
