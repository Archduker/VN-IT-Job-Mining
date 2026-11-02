import axios from 'axios'
import {
  AirflowStatusResponse,
  CloudHealth,
  CollectionMonitor,
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
}
