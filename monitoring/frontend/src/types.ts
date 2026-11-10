// TypeScript Interfaces for VN-IT-Job-Mining Central Observatory

export interface SourceStatus {
  id: string
  name: string
  status: 'idle' | 'running' | 'completed' | 'error'
  total_urls: number
  total_raw: number
  engine: string
}

export interface FieldInventoryItem {
  field_name: string
  data_type: string
  null_count: number
  null_rate_pct: number
  unique_count: number
  sample_value: string | null
}

export interface CloudHealth {
  configured: boolean
  connected: boolean
  latency_ms?: number
  bucket: string
  endpoint: string
  message: string
  error?: string
}

export interface StorageBreakdown {
  bucket: string
  connected: boolean
  total_objects: number
  total_size_mb: number
  layers: Record<string, { count: number; size_bytes: number; size_mb: number }>
  error?: string
}

export interface AirflowSchedulerStatus {
  running: boolean
  pid: number | null
  status: 'ONLINE' | 'STOPPED'
  pid_file: string
}

export interface AirflowWebserverStatus {
  running: boolean
  port: number
  status: 'ONLINE' | 'STOPPED'
}

export interface AirflowDatabaseStatus {
  connected: boolean
  engine: string
  host?: string
  port?: number
  name?: string
  path?: string
  size_mb?: number
}

export interface AirflowStatusResponse {
  scheduler: AirflowSchedulerStatus
  webserver: AirflowWebserverStatus
  database: AirflowDatabaseStatus
  active_dags_count: number
  last_checked: string
}

export interface AirflowDAGItem {
  dag_id: string
  source: string
  schedule_day: string
  is_active: boolean
  is_paused: boolean
  last_run_state: 'success' | 'running' | 'failed' | null
  last_run_start: string | null
  last_run_end: string | null
  duration_seconds: number | null
}

export interface R2DiffResult {
  source: string
  local_count: number
  cloud_count: number
  missing_in_cloud: string[]
  missing_count: number
  synced_pct: number
  status: 'IN_SYNC' | 'DESYNC'
}

export interface R2SyncResponse {
  source: string
  status: 'completed' | 'failed'
  uploaded_count: number
  errors_count?: number
  message?: string
}



export interface StatusMetricItem {
  count: number
  pct: number
}

export interface EnumStatusSummary {
  total: number
  pending: StatusMetricItem
  done: StatusMetricItem
  recheck_due: StatusMetricItem
  closed: StatusMetricItem
  failed: StatusMetricItem
  by_source: Record<string, {
    total: number
    pending: number
    done: number
    recheck_due: number
    closed: number
    failed: number
  }>
  generated_at?: string
}

export interface Phase1DiscoveryItem {
  focal_source: string
  dag_id: string
  task_id: string
  scheduled_time: string
  quota_pages: number
  total_discovered: number
  status: 'SUCCESS' | 'RUNNING' | 'SCHEDULED' | 'FAILED' | 'UNKNOWN' | string
}

export interface Phase2DetailItem {
  focal_source: string
  dag_id: string
  scheduled_time: string
  batch_limit: number
  actual_crawled: number
  uncrawled_pending: number
  batches_needed: number
  last_run_start: string | null
  engine: string
  status: 'SUCCESS' | 'RUNNING' | 'SCHEDULED' | 'FAILED' | 'UNKNOWN' | string
}

// Backward-compatibility alias
export type WeeklyScheduleDay = Phase2DetailItem

export interface WeeklyScheduleResponse {
  phase1_discovery?: Phase1DiscoveryItem[]
  phase2_detail?: Phase2DetailItem[]
  airflow_available: boolean
  batch_limit: number
  cooldown_minutes: number
  next_detail_slot: string
  total_actual_crawled: number
  total_uncrawled_pending?: number
  days?: Phase2DetailItem[]
  generated_at?: string
}

export interface LedgerItem {
  job_id: string | null
  url_hash: string
  job_title?: string | null
  company?: string | null
  url: string | null
  status: 'PENDING' | 'DONE' | 'RECHECK_DUE' | 'CLOSED' | 'FAILED' | string
  scraped_at: string | null
  http_status: number | null
  content_hash: string | null
  repost_of_url_hash: string | null
}

export interface LedgerListResponse {
  source: string
  total: number
  counts: Record<string, number>
  page: number
  page_size: number
  items: LedgerItem[]
}

export interface SourceCloudSyncStatus {
  source: string
  ledger_local: boolean
  ledger_cloud: boolean
  local_raw_count: number
  cloud_raw_count: number
  sync_pct: number
  status: 'SYNCED' | 'OUT_OF_SYNC'
}

export interface CloudSyncOverview {
  connected: boolean
  latency_ms: number
  bucket: string
  overall_sync_pct: number
  total_local_raw: number
  total_cloud_raw: number
  sources: Record<string, SourceCloudSyncStatus>
  last_synced_at?: string
}


export interface AlertItem {
  id: string
  severity: 'CRITICAL' | 'WARNING' | 'INFO'
  category: 'AIRFLOW' | 'STORAGE' | 'DATABASE' | 'CRAWLER'
  title: string
  message: string
  source?: string
  timestamp: string
  action_url?: string
}

export interface AlertSummary {
  total_alerts: number
  critical_count: number
  warning_count: number
  alerts: AlertItem[]
  last_checked: string
}


// ── Trang Collection và Raw (/api/v1/monitor) ─────────────────────
export type RunStatus = 'done' | 'partial' | 'fail' | 'running' | null

export interface SourceDayCell {
  count: number
  status: RunStatus
  runs: number
  failed_runs: number
  first_start: string | null
  last_end: string | null
}

export interface CollectionDay {
  date: string
  dow: string
  is_today: boolean
  total: number
  by_source: Record<string, SourceDayCell>
}

export interface CollectionKpi {
  today: number
  yesterday: number
  total: number
  avg_per_day: number
  runs_ok: number | null
  runs_total: number | null
  unique_total: number | null
  unique_reason: string | null
}

export interface ProgressPoint {
  date: string
  actual: number
  plan: number | null
}

export interface ScheduleItem {
  label: string
  times: string[]
  note: string
}

export interface TodayStep {
  time: string | null
  name: string
  status: RunStatus
  detail: string
}

export interface CollectionMonitor {
  generated_at: string
  days: CollectionDay[]
  count_origin: Record<string, 'ledger' | 'raw' | null>
  kpi: CollectionKpi
  queue: { pending: number; recheck_due: number; failed: number; done: number; total: number }
  progress: { target: number; target_date: string; points: ProgressPoint[] }
  schedule: ScheduleItem[]
  today_steps: TodayStep[]
  airflow_available: boolean
  unavailable_reason: string | null
  has_data: boolean
}

export interface SourceOverviewItem {
  source: string
  completeness_pct: number | null
}

export interface FeatureTarget {
  code: string
  name: string
  use: string
  std: string
  raw_key: string | null
}

export interface FeatureIssue {
  code: string
  label: string
  problem: string
  where: string
  fix: string
}

export interface SourceReport {
  source: string
  domain: string
  overview: {
    integrated_records: number | null
    clean_records: number | null
    stub_removed: number | null
    report_time: string | null
    completeness_pct: number | null
    weakest: string | null
    weakest_pct: number | null
    ledger: { total: number; pending: number; done: number; recheck_due: number; failed: number } | null
  }
  unavailable_reason: string | null
  targets: FeatureTarget[]
  issues: FeatureIssue[]
}

export interface UnivariateItem {
  label: string
  count: number
  pct: number
}

export interface Univariate {
  code: string
  kind: 'num' | 'cat' | 'empty'
  title?: string
  unit?: string
  base?: number
  items?: UnivariateItem[]
  stats?: { k: string; v: string | number | null }[]
  unavailable_reason: string | null
}

export interface SampleList {
  source: string
  origin: 'local' | 'r2' | null
  items: { id: string; title: string | null }[]
  unavailable_reason: string | null
}

export type JsonPath = (string | number)[]

export interface SampleHighlight {
  path: JsonPath
  kind: 'feature' | 'dup'
  feature: string | null
}

export interface SampleNote {
  code: string
  name: string
  status: 'ok' | 'warn' | 'fallback' | 'fail' | 'missing'
  path: string | null
  raw: string | null
  normalized: string | null
  how: string
}

export interface RawSample {
  source: string
  id: string
  origin: 'local' | 'r2'
  raw: unknown
  title: string | null
  scraped_at: string | null
  highlights: SampleHighlight[]
  notes: SampleNote[]
  features_in_raw: number
}

// ── Số liệu pipeline thật: /preprocessing/metrics, /processing/metrics, /dashboard, /eda ──

export interface RankItem {
  label: string
  count: number
}

export interface PreprocessingSource {
  source: string
  available: boolean
  audit_timestamp?: string | null
  raw_envelopes?: number | null
  stub_removed?: number | null
  clean_records?: number | null
  salary_coverage_pct?: number | null
  salary_jd_hits?: number | null
  imputed_records?: number | null
  imputation_rate_pct?: number | null
  language_distribution?: Record<string, number>
}

export interface PreprocessingReport {
  available: boolean
  unavailable_reason: string | null
  generated_at: string | null
  sources: PreprocessingSource[]
  totals: {
    raw_envelopes: number | null
    stub_removed: number | null
    clean_records: number | null
    imputed_records: number | null
  }
}

export interface FieldCompletenessItem {
  field: string
  filled: number | null
  missing: number | null
  completeness_pct: number | null
}

export interface ProcessingReport {
  available: boolean
  unavailable_reason: string | null
  generated_at: string | null
  integrated_records: number | null
  dedup: {
    input_records: number | null
    golden_records: number | null
    duplicates_removed: number | null
    deduplication_rate_pct: number | null
    cross_platform_clusters: number | null
  } | null
  field_completeness: FieldCompletenessItem[]
  not_recorded: string[]
}

export interface DashboardReport {
  available: boolean
  unavailable_reason: string | null
  generated_at: string | null
  totals: {
    integrated_records: number | null
    staging_records: number | null
    golden_records: number
    deduplication_rate_pct: number | null
    salary_coverage_pct: number | null
  } | null
  platform_breakdown: { source: string; golden_records: number; share_pct: number | null }[]
  salary_vnd_million: { p1: number | null; q1: number | null; median: number | null; q3: number | null; p99: number | null } | null
  job_family: RankItem[]
  seniority: RankItem[]
  top_cities: RankItem[]
  lineage: { step: string; records: number }[]
}

export interface EdaSummary {
  raw_scan?: { status: 'QUEUED' | 'RUNNING' | 'COMPLETE' | 'ERROR'; records: number; objects: number; reason: string | null; completed_at: string | null; scope: string; duplicates?: { records: number; unique_payloads: number; duplicate_records: number; duplicate_groups: number; duplicate_pct: number | null; filename_ids: number; extra_version_objects: number } | null }
  source: string
  total_records: number | null
  sampled_records: number
  fields_count: number
  completeness_score_pct: number | null
  salary_parse_rate_pct: number | null
  negotiable_salary_pct: number | null
  reason: string | null
}

export interface EdaCharts {
  exploration?: EdaExploration
  available: boolean
  unavailable_reason: string | null
  records: number
  salary_records?: number
  salary_histogram: { bin: string; count: number }[]
  skills_pareto: { label: string; count: number; cumulative_pct: number }[]
  locations: RankItem[]
}

export interface EdaExploration {
  scatter: { experience: number; salary: number }[]
  scatter_total: number
  scatter_limit: number
  salary_curve: { salary: number; cumulative_pct: number }[]
  boxes: { label: string; count: number; low: number; high: number; q1: number; median: number; q3: number; lower_fence: number; upper_fence: number; outliers: number }[]
  heatmap: { x: string; y: string; value: number }[]
  correlation: { x: string; y: string; value: number | null; count: number }[]
}

export interface EdaCompareRow {
  source: string
  available: boolean
  records: number | null
  completeness_pct: number | null
  salary_text_pct: number | null
  salary_numeric_pct: number | null
  experience_pct: number | null
  seniority_pct: number | null
}

export interface EdaCompare {
  available: boolean
  unavailable_reason: string | null
  sources: EdaCompareRow[]
}

// ---- Pre-processing theo bước (reports/preprocessing/<bước>/<nguồn>.json, schema P0 mục 4)
export interface StepExample {
  job_id: string
  field: string
  before: unknown
  after: unknown
  url?: string | null
}

export interface StepRule {
  id: string
  name: string
  action: 'drop' | 'flag' | 'modify'
  rows_affected: number
  examples: StepExample[]
  by_source?: Record<string, number>
}

export interface ItReview {
  file: string
  rows: number
  labeled: number
  labeled_non_it: number
  rule_decided: number
  rule_correct: number
  status_non_it: number
  status_non_it_correct: number
  level2_labeled: number
  level2_correct: number
}

export interface StepReportData {
  step: string
  source: string
  mode: 'dry_run' | 'applied'
  generated_at: string
  code_version: string
  input: { path: string | null; rows: number }
  output: { path: string | null; rows: number }
  dropped: { rule: string; reason: string; rows: number }[]
  rules: StepRule[]
  fields: { field: string; fill_pct_in?: number; fill_pct_out?: number }[]
  checks: { rows_conserved: boolean | null; notes: string[] }
  extra: {
    it_status?: Record<string, number> | Record<string, Record<string, number>>
    it_levels?: Record<string, number> | Record<string, Record<string, number>>
    it_policy?: string | Record<string, unknown>
    review?: ItReview | Record<string, ItReview>  // nguồn: một mục; _all: theo nguồn
    sources?: Record<string, { input: number; output: number }>
  }
}

export interface StepSummary {
  step: string
  name: string
  available: boolean
  command?: string
  mode?: 'dry_run' | 'applied'
  generated_at?: string
  input_rows?: number
  output_rows?: number
  stale?: boolean
}

export interface StepResponse {
  step: string
  source?: string
  available: boolean
  command?: string
  report?: StepReportData
}

export interface StorageItem {
  step: string
  source: string | null
  key: string
  local_rows: number | null
  local_generated_at: string | null
  status: 'khop' | 'lech' | 'chua_day' | 'khong_ro'
  r2_rows: number | null
  r2_size: number | null
}

export interface StorageResponse {
  bucket: string
  reason: string | null
  items: StorageItem[]
  command: string
}

export interface StepRowsResponse {
  step: string
  source: string | null
  origin: 'r2' | 'local'
  note: string | null
  total: number
  offset: number
  limit: number
  rows: Record<string, unknown>[]
}

export interface InsightResponse<T> { status: 'OK' | 'EMPTY'; reason: string | null; data: T[] | null }
export interface InsightOption { job_family: string; seniority_level: string | null; province_norm: string | null }
export interface SalaryCell { job_family: string; seniority_level: string | null; median: number | null; q25: number | null; q75: number | null; sample_count: number; negotiable_count: number }
export interface SkillRule { antecedents: string[]; consequents: string[]; support: number; confidence: number; lift: number; job_family_scope: string; duplicates?: { records: number; unique_payloads: number; duplicate_records: number; duplicate_groups: number; duplicate_pct: number | null; filename_ids: number; extra_version_objects: number } | null }
export interface ClusterPoint { job_id: string; job_title: string; cluster_id: number; cluster_name: string | null; pca_x: number; pca_y: number; pca_z: number | null; company_name: string | null; salary_avg_vnd: number | null; source_platform: string | null }

export interface R2CollectionDay {
  date: string
  dow: string
  total: number
  by_source: Record<string, { count: number }>
}
export interface R2Collection {
  origin: 'r2'
  generated_at: string
  cache_age_seconds: number
  days: R2CollectionDay[]
  raw_objects: number
  bytes: number
  undated_objects: number
  has_data: boolean
  unavailable_reason: string | null
  sources: { source: string; raw_objects: number; bytes: number; undated_objects: number; latest_upload: string | null; ledger: Record<string, number> | null; ledger_reason: string | null }[]
}
