// Admin-specific API response types
// Used by frontend/app/admin/page.tsx

export type QdrantStats = {
  status: string;
  collections_count: number | null;
  indexed_vacancies: number | null;
  profiled_vacancies: number | null;
  coverage_pct: number | null;
  preference_vectors_ready: number | null;
};

export type LastJobStats = {
  role: string | null;
  specialization: string | null;
  resume_embedded: boolean | null;
  vector_candidates_top300: number | null;
  relevant_over_55_top300: number | null;
  last_job_status: string | null;
  last_job_matches: number | null;
  last_job_analyzed: number | null;
  last_job_sources: string[] | null;
};

export type ProfileBackfillInfo = {
  total: number | null;
  done: number | null;
  pending: number | null;
};

export type WarmupInternals = {
  running: boolean;
  cycle: number | null;
  interval_seconds: number | null;
  last_duration_seconds: number | null;
  last_metrics: Record<string, unknown> | null;
  queries_per_cycle: number | null;
  max_analyzed_per_query: number | null;
  profile_backfill: ProfileBackfillInfo | null;
};

export type AdminStatsResponse = {
  generated_at: string;
  qdrant: QdrantStats;
  last_job: LastJobStats | null;
  warmup: WarmupInternals;
};

export type AdminRoleCount = {
  role: string;
  count: number;
};

export type AdminActiveJob = {
  id: string;
  user_id: number;
  user_email: string | null;
  resume_id: number;
  target_role: string | null;
  status: string;
  stage: string;
  progress: number;
  cancel_requested: boolean;
  created_at: string;
  started_at: string | null;
};

export type AdminRecentJob = {
  id: string;
  user_id: number;
  user_email: string | null;
  resume_id: number;
  target_role: string | null;
  status: string;
  stage: string;
  progress: number;
  query: string | null;
  matches_count: number;
  created_at: string;
  finished_at: string | null;
};

export type AdminDailyCount = {
  date: string;
  count: number;
};

export type AdminActivity = {
  signups_per_day: AdminDailyCount[];
  logins_per_day: AdminDailyCount[];
  dau: number;
  wau: number;
  mau: number;
};

export type AdminOverviewResponse = {
  generated_at: string;
  users_total: number;
  users_active_last_day: number;
  resumes_total: number;
  vacancies_total: number;
  vacancies_indexed: number;
  top_searched_roles: AdminRoleCount[];
  active_jobs: AdminActiveJob[];
  recent_jobs: AdminRecentJob[];
  activity?: AdminActivity;
};

export type AdminJobCancelResponse = {
  id: string;
  status: string;
  cancel_requested: boolean;
};

export type AdminFunnelStage = {
  key: string;
  label: string;
  value: number;
  kind: string;
};

export type AdminJobFunnel = {
  job_id: string;
  status: string;
  stage: string;
  user_id: number;
  user_email: string | null;
  resume_id: number;
  target_role: string | null;
  query: string | null;
  stages: AdminFunnelStage[];
  drops: AdminFunnelStage[];
  matcher_stages: AdminFunnelStage[];
  shown_to_user: number;
  fetched_raw: number;
  total_drops: number;
  residual: number;
  metrics: Record<string, number>;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};
