// TypeScript Interfaces for VN-IT-Job-Mining Central Observatory

export type TabType =
  | 'dashboard'
  | 'crawling'
  | 'airflow'
  | 'preprocessing'
  | 'processing'
  | 'eda'
  | 'ml3d'
  | 'cloud'


export interface DatasetMetadata {
  version: string
  storage_layer: string
  format: string
  total_raw_scraped: number
  total_preprocessed: number
  total_golden_unique: number
  deduplication_rate_pct: number
  overall_completeness_score: number
}

export interface PlatformBreakdown {
  source: string
  raw_count: number
  contributed_unique: number
  share_pct: number
}

export interface MarketSalaryBenchmark {
  currency: string
  unit: string
  p25: number
  median: number
  mean: number
  p75: number
  p90: number
  min_valid: number
  max_valid: number
}

export interface GoldenSkill {
  skill: string
  job_count: number
  percentage: number
}

export interface DataLineage {
  raw_input_files: number
  preprocessed_records: number
  filtered_spams: number
  cross_platform_duplicates_merged: number
  final_golden_records: number
}

export interface MasterDashboardData {
  status: string
  generated_at: string
  dataset_metadata: DatasetMetadata
  platform_breakdown: PlatformBreakdown[]
  schema_convergence: Record<string, number>
  market_salary_benchmark_vnd: MarketSalaryBenchmark
  top_golden_skills: GoldenSkill[]
  data_lineage: DataLineage
}

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

export interface SemanticVectorPoint3D {
  id: string
  title: string
  company: string
  job_family: string
  salary_vnd?: number
  x: number
  y: number
  z: number
  is_anomaly: boolean
  skills: string[]
}

export interface Spatial3DData {
  algorithm: string
  total_points: number
  points: SemanticVectorPoint3D[]
  decision_boundary_mesh?: {
    x: number[][]
    y: number[][]
    z: number[][]
    threshold_score: number
  }
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
  uploaded_count: number
  failed_count: number
  errors: string[]
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
  day_of_week: string
  day_index: number
  focal_source: string
  dag_id: string
  task_id: string
  scheduled_time: string
  quota_pages: number
  total_discovered: number
  status: 'SUCCESS' | 'RUNNING' | 'SCHEDULED' | 'FAILED' | string
}

export interface Phase2DetailItem {
  day_of_week: string
  day_index: number
  focal_source: string
  dag_id: string
  scheduled_time: string
  projected_quota: number
  actual_crawled: number
  uncrawled_pending: number
  progress_pct: number
  engine: string
  recrawl_strategy: string
  status: 'SUCCESS' | 'RUNNING' | 'SCHEDULED' | 'FAILED' | string
}

// Backward-compatibility alias
export type WeeklyScheduleDay = Phase2DetailItem

export interface WeeklyScheduleResponse {
  phase1_discovery?: Phase1DiscoveryItem[]
  phase2_detail?: Phase2DetailItem[]
  total_projected_weekly: number
  total_actual_crawled: number
  total_uncrawled_pending?: number
  overall_progress_pct: number
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


export interface ParsingRuleItem {
  rule_name: string
  target_field: string
  total_attempted: number
  successfully_parsed: number
  success_rate_pct: number
  failed_samples: string[]
}

export interface NullReductionItem {
  field: string
  raw_null_pct: number
  clean_null_pct: number
  improvement_pct: number
}

export interface PreprocessingMetricsData {
  total_records_processed?: number
  parsing_rules: ParsingRuleItem[]
  null_reduction_comparison: NullReductionItem[]
}

export interface CrossPlatformPair {
  pair: string
  duplicates_found: number
  pct: number
}

export interface DeduplicationMetrics {
  similarity_threshold: number
  total_comparisons: number
  detected_duplicates: number
  deduplication_rate_pct: number
  similarity_score_distribution: {
    ranges: string[]
    pairs_count: number[]
  }
  top_cross_platform_pairs: CrossPlatformPair[]
}

export interface SchemaMappingItem {
  target_field: string
  data_type: string
  unified_pct: number
  status: string
}

export interface ProcessingMetricsData {
  deduplication_metrics: DeduplicationMetrics
  schema_mapping_inventory: SchemaMappingItem[]
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

