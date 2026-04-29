'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSession } from '@/lib/session';
import { apiFetch } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import type {
  AdminActiveJob,
  AdminActivity,
  AdminDailyCount,
  AdminFunnelStage,
  AdminJobCancelResponse,
  AdminJobFunnel,
  AdminOverviewResponse,
  AdminRecentJob,
  AdminStatsResponse,
} from '@/types/admin';

export default function AdminPage() {
  const { token, user } = useSession();
  const [stats, setStats] = useState<AdminStatsResponse | null>(null);
  const [overview, setOverview] = useState<AdminOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [cancellingJobId, setCancellingJobId] = useState<string | null>(null);
  const [cancelError, setCancelError] = useState<string | null>(null);
  const [funnelJob, setFunnelJob] = useState<AdminJobFunnel | null>(null);
  const [funnelLoading, setFunnelLoading] = useState(false);
  const [funnelError, setFunnelError] = useState<string | null>(null);

  const reloadOverview = useCallback(async () => {
    if (!token) return;
    const data = await apiFetch<AdminOverviewResponse>('/api/admin/overview', {
      token: token ?? undefined,
    });
    setOverview(data);
  }, [token]);

  useEffect(() => {
    if (!token || !user?.is_admin) {
      setLoading(false);
      return;
    }

    async function loadAll() {
      setLoading(true);
      setError(null);
      try {
        const [statsData, overviewData] = await Promise.all([
          apiFetch<AdminStatsResponse>('/api/admin/stats', {
            token: token ?? undefined,
          }),
          apiFetch<AdminOverviewResponse>('/api/admin/overview', {
            token: token ?? undefined,
          }),
        ]);
        setStats(statsData);
        setOverview(overviewData);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Не удалось загрузить статистику');
      } finally {
        setLoading(false);
      }
    }

    void loadAll();
  }, [token, user]);

  const handleCancelJob = useCallback(
    async (jobId: string) => {
      if (!token) return;
      setCancellingJobId(jobId);
      setCancelError(null);
      try {
        await apiFetch<AdminJobCancelResponse>(`/api/admin/jobs/${jobId}/cancel`, {
          method: 'POST',
          token: token ?? undefined,
        });
        await reloadOverview();
      } catch (err) {
        setCancelError(err instanceof Error ? err.message : 'Не удалось остановить подбор');
      } finally {
        setCancellingJobId(null);
      }
    },
    [token, reloadOverview]
  );

  const handleOpenFunnel = useCallback(
    async (jobId: string) => {
      if (!token) return;
      setFunnelLoading(true);
      setFunnelError(null);
      setFunnelJob(null);
      try {
        const data = await apiFetch<AdminJobFunnel>(`/api/admin/jobs/${jobId}/funnel`, {
          token: token ?? undefined,
        });
        setFunnelJob(data);
      } catch (err) {
        setFunnelError(err instanceof Error ? err.message : 'Не удалось загрузить воронку');
      } finally {
        setFunnelLoading(false);
      }
    },
    [token]
  );

  const handleCloseFunnel = useCallback(() => {
    setFunnelJob(null);
    setFunnelError(null);
  }, []);

  // Not authenticated — nothing to show (Topbar handles login redirect)
  if (!token) {
    return null;
  }

  // Not admin — 403 empty state
  if (!user?.is_admin) {
    return (
      <main className="min-h-[60vh] flex flex-col items-center justify-center gap-4 px-4">
        <Card className="w-full max-w-sm text-center">
          <CardHeader>
            <CardTitle>
              Нет доступа
            </CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col items-center gap-4">
            <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
              Этот раздел доступен только администраторам.
            </p>
            <Button variant="ghost" size="sm" asChild>
              <Link href="/">← На главную</Link>
            </Button>
          </CardContent>
        </Card>
      </main>
    );
  }

  if (loading) {
    return (
      <main className="px-8 py-10 text-[color:var(--color-ink-secondary)] text-[length:var(--text-sm)]">
        Загружаем данные...
      </main>
    );
  }

  if (error) {
    return (
      <main className="px-8 py-10 text-[color:var(--color-danger)] text-[length:var(--text-sm)]">
        {error}
      </main>
    );
  }

  const qdrant = stats?.qdrant;
  const lastJob = stats?.last_job;
  const warmup = stats?.warmup;

  return (
    <main className="w-full max-w-[var(--content-width)] mx-auto px-4 py-10">
      <h1
        className={cn(
          'font-[var(--font-display)] text-[length:var(--text-3xl)]',
          'font-semibold text-[color:var(--color-ink)] tracking-[-0.03em]',
          'leading-[var(--leading-tight)] mb-8'
        )}
      >
        Админ-панель
      </h1>

      {overview ? (
        <section className="mb-10 space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <OverviewStat label="Пользователей" value={overview.users_total} />
            <OverviewStat
              label="Активны за 24 ч"
              value={overview.users_active_last_day}
            />
            <OverviewStat label="Резюме" value={overview.resumes_total} />
            <OverviewStat
              label="Вакансий"
              value={overview.vacancies_total}
              hint={`индексированы: ${overview.vacancies_indexed}`}
            />
          </div>

          <Card className="animate-fade-in">
            <CardHeader>
              <CardTitle>Топ ролей по запросам подбора</CardTitle>
            </CardHeader>
            <CardContent>
              {overview.top_searched_roles.length === 0 ? (
                <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-muted)] italic py-2">
                  Пока нет ни одного подбора.
                </p>
              ) : (
                <dl className="flex flex-col divide-y divide-[var(--color-border)]">
                  {overview.top_searched_roles.map((row) => (
                    <StatRow
                      key={row.role}
                      label={row.role}
                      value={row.count}
                      mono
                    />
                  ))}
                </dl>
              )}
            </CardContent>
          </Card>

          <Card className="animate-fade-in">
            <CardHeader>
              <CardTitle>
                Активные фоновые подборы
                <span
                  className={cn(
                    'ml-2 text-[length:var(--text-xs)]',
                    'text-[color:var(--color-ink-secondary)] font-normal'
                  )}
                >
                  ({overview.active_jobs.length})
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {cancelError ? (
                <p className="text-[length:var(--text-sm)] text-[color:var(--color-danger)] mb-3">
                  {cancelError}
                </p>
              ) : null}
              {overview.active_jobs.length === 0 ? (
                <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-muted)] italic py-2">
                  Нет активных подборов.
                </p>
              ) : (
                <ul className="flex flex-col divide-y divide-[var(--color-border)]">
                  {overview.active_jobs.map((job) => (
                    <ActiveJobRow
                      key={job.id}
                      job={job}
                      onCancel={handleCancelJob}
                      onOpenFunnel={handleOpenFunnel}
                      isCancelling={cancellingJobId === job.id}
                    />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          <Card className="animate-fade-in">
            <CardHeader>
              <CardTitle>
                Последние подборы
                <span
                  className={cn(
                    'ml-2 text-[length:var(--text-xs)]',
                    'text-[color:var(--color-ink-secondary)] font-normal'
                  )}
                >
                  ({overview.recent_jobs.length})
                </span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {overview.recent_jobs.length === 0 ? (
                <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-muted)] italic py-2">
                  Нет данных.
                </p>
              ) : (
                <ul className="flex flex-col divide-y divide-[var(--color-border)]">
                  {overview.recent_jobs.map((job) => (
                    <RecentJobRow
                      key={job.id}
                      job={job}
                      onOpenFunnel={handleOpenFunnel}
                    />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          {overview.activity ? (
            <ActivityCard activity={overview.activity} />
          ) : null}
        </section>
      ) : null}

      <FunnelDialog
        job={funnelJob}
        loading={funnelLoading}
        error={funnelError}
        onClose={handleCloseFunnel}
      />

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 stagger-children">
        {/* Qdrant card */}
        <Card className="animate-fade-in">
          <CardHeader>
            <CardTitle>
              Qdrant
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="flex flex-col divide-y divide-[var(--color-border)]">
              <StatRow label="Статус" value={qdrant?.status ?? '—'} />
              <StatRow
                label="Коллекций"
                value={qdrant?.collections_count ?? '—'}
                mono
              />
              <StatRow
                label="Проиндексировано вакансий"
                value={qdrant?.indexed_vacancies ?? '—'}
                mono
              />
              <StatRow
                label="Профилировано вакансий"
                value={qdrant?.profiled_vacancies ?? '—'}
                mono
              />
              <StatRow
                label="Покрытие"
                value={
                  qdrant?.coverage_pct != null
                    ? `${qdrant.coverage_pct.toFixed(1)}%`
                    : '—'
                }
                mono
              />
              <StatRow
                label="Preference-векторов"
                value={qdrant?.preference_vectors_ready ?? '—'}
                mono
              />
            </dl>
          </CardContent>
        </Card>

        {/* Last job card */}
        <Card className="animate-fade-in">
          <CardHeader>
            <CardTitle>
              Последний job
            </CardTitle>
          </CardHeader>
          <CardContent>
            {lastJob == null ? (
              <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-muted)] italic py-2">
                Нет данных. Передайте ?resume_id=N в URL.
              </p>
            ) : (
              <dl className="flex flex-col divide-y divide-[var(--color-border)]">
                <StatRow label="Роль" value={lastJob.role ?? '—'} />
                <StatRow
                  label="Специализация"
                  value={lastJob.specialization ?? '—'}
                />
                <StatRow
                  label="Резюме embedded"
                  value={lastJob.resume_embedded != null ? String(lastJob.resume_embedded) : '—'}
                />
                <StatRow
                  label="Кандидатов top-300"
                  value={lastJob.vector_candidates_top300 ?? '—'}
                  mono
                />
                <StatRow
                  label="Релевантных >55% top-300"
                  value={lastJob.relevant_over_55_top300 ?? '—'}
                  mono
                />
                <StatRow
                  label="Статус"
                  value={lastJob.last_job_status ?? '—'}
                />
                <StatRow
                  label="Совпадений"
                  value={lastJob.last_job_matches ?? '—'}
                  mono
                />
                <StatRow
                  label="Проанализировано"
                  value={lastJob.last_job_analyzed ?? '—'}
                  mono
                />
                <StatRow
                  label="Источники"
                  value={
                    lastJob.last_job_sources?.length
                      ? lastJob.last_job_sources.join(', ')
                      : '—'
                  }
                />
              </dl>
            )}
          </CardContent>
        </Card>

        {/* Warmup internals card */}
        <Card className="animate-fade-in">
          <CardHeader>
            <CardTitle>
              Warmup internals
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="flex flex-col divide-y divide-[var(--color-border)]">
              <StatRow
                label="Выполняется"
                value={warmup?.running != null ? String(warmup.running) : '—'}
              />
              <StatRow
                label="Цикл"
                value={warmup?.cycle ?? '—'}
                mono
              />
              <StatRow
                label="Интервал (сек)"
                value={warmup?.interval_seconds ?? '—'}
                mono
              />
              <StatRow
                label="Длительность последнего (сек)"
                value={warmup?.last_duration_seconds ?? '—'}
                mono
              />
              <StatRow
                label="Запросов на цикл"
                value={warmup?.queries_per_cycle ?? '—'}
                mono
              />
              <StatRow
                label="Макс. анализов на запрос"
                value={warmup?.max_analyzed_per_query ?? '—'}
                mono
              />
            </dl>
            {warmup?.last_metrics != null ? (
              <div className="mt-3 pt-3 border-t border-[var(--color-border)]">
                <dt
                  className={cn(
                    'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
                    'uppercase tracking-[0.1em] font-bold mb-2'
                  )}
                >
                  Метрики последнего прогона
                </dt>
                <dd>
                  <pre
                    className={cn(
                      'font-[var(--font-mono)] text-[length:var(--text-xs)]',
                      'text-[color:var(--color-ink-secondary)]',
                      'bg-[var(--color-surface-muted)]',
                      'p-3 rounded-[var(--radius-sm)]',
                      'overflow-x-auto m-0'
                    )}
                  >
                    {JSON.stringify(warmup.last_metrics, null, 2)}
                  </pre>
                </dd>
              </div>
            ) : null}
            {warmup?.profile_backfill != null ? (
              <dl className="flex flex-col divide-y divide-[var(--color-border)] mt-3 pt-3 border-t border-[var(--color-border)]">
                <StatRow
                  label="Backfill: всего"
                  value={warmup.profile_backfill.total ?? '—'}
                  mono
                />
                <StatRow
                  label="Backfill: готово"
                  value={warmup.profile_backfill.done ?? '—'}
                  mono
                />
                <StatRow
                  label="Backfill: ожидает"
                  value={warmup.profile_backfill.pending ?? '—'}
                  mono
                />
              </dl>
            ) : null}
          </CardContent>
        </Card>
      </div>

      {token && user?.is_admin ? <MetricsDashboard token={token} /> : null}

      {stats?.generated_at ? (
        <p
          className={cn(
            'mt-8 text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)]',
            'font-[var(--font-mono)]'
          )}
        >
          Данные на: {new Date(stats.generated_at).toLocaleString('ru-RU')}
        </p>
      ) : null}
    </main>
  );
}

// ---------------------------------------------------------------------------
// Metrics dashboard (v0.23.0)
// ---------------------------------------------------------------------------

type RangeLabel = '24h' | '7d' | '30d';

type LatencyResponse = {
  range: string;
  by_job_type: Record<
    string,
    {
      count: number;
      p50_seconds: number;
      p95_seconds: number;
      p99_seconds: number;
      max_seconds: number;
      fail_rate: number;
    }
  >;
};

type CostResponse = {
  range: string;
  total_usd: number;
  today_usd: number;
  yesterday_usd: number;
  by_day: Array<{ day: string; cost_usd: number; calls: number }>;
  by_model: Array<{ model: string; cost_usd: number; calls: number }>;
};

type ActivationResponse = {
  range: string;
  cohort_size: number;
  steps: Array<{ key: string; users: number; share: number }>;
};

type RetentionResponse = {
  d1: { retained: number; eligible: number; share: number };
  d7: { retained: number; eligible: number; share: number };
  d30: { retained: number; eligible: number; share: number };
};

type QualityResponse = {
  range: string;
  ctr_by_tier: Record<string, { impressions: number; clicks: number; ctr: number }>;
  score_distribution_by_tier: Record<string, number[]>;
};

type SegmentWarmupResponse = {
  range: string;
  by_status: Record<string, number>;
  mean_duration_seconds: Record<string, number>;
  daily_count: number;
  daily_cap: number;
  daily_utilization: number;
};

type FreshnessResponse = {
  range: string;
  runs: Array<{
    started_at: string | null;
    finished_at: string | null;
    checked: number;
    archived: number;
    stopped_early: number;
  }>;
};

type MatchEventsResponse = {
  range: string;
  events: Array<{ event: string; count: number }>;
};

function MetricsDashboard({ token }: { token: string }) {
  const [range, setRange] = useState<RangeLabel>('7d');
  const [latency, setLatency] = useState<LatencyResponse | null>(null);
  const [cost, setCost] = useState<CostResponse | null>(null);
  const [activation, setActivation] = useState<ActivationResponse | null>(null);
  const [retention, setRetention] = useState<RetentionResponse | null>(null);
  const [quality, setQuality] = useState<QualityResponse | null>(null);
  const [segmentWarmup, setSegmentWarmup] = useState<SegmentWarmupResponse | null>(null);
  const [freshness, setFreshness] = useState<FreshnessResponse | null>(null);
  const [matchEvents, setMatchEvents] = useState<MatchEventsResponse | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoadError(null);
    const fetchOne = async <T,>(path: string): Promise<T | null> => {
      try {
        return await apiFetch<T>(path, { token });
      } catch (err) {
        console.warn('admin metrics load failed', path, err);
        return null;
      }
    };
    const [
      latencyR,
      costR,
      activationR,
      retentionR,
      qualityR,
      segR,
      freshR,
      eventsR,
    ] = await Promise.all([
      fetchOne<LatencyResponse>(`/api/admin/metrics/latency?range=${range}`),
      fetchOne<CostResponse>(`/api/admin/metrics/cost?range=${range}`),
      fetchOne<ActivationResponse>(
        `/api/admin/metrics/activation-funnel?range=${range === '24h' ? '7d' : range}`
      ),
      fetchOne<RetentionResponse>('/api/admin/metrics/retention'),
      fetchOne<QualityResponse>(`/api/admin/metrics/quality?range=${range}`),
      fetchOne<SegmentWarmupResponse>(`/api/admin/metrics/segment-warmup?range=${range}`),
      fetchOne<FreshnessResponse>(`/api/admin/metrics/freshness?range=${range}`),
      fetchOne<MatchEventsResponse>(`/api/admin/metrics/match-events?range=${range}`),
    ]);
    setLatency(latencyR);
    setCost(costR);
    setActivation(activationR);
    setRetention(retentionR);
    setQuality(qualityR);
    setSegmentWarmup(segR);
    setFreshness(freshR);
    setMatchEvents(eventsR);
    if (
      !latencyR ||
      !costR ||
      !activationR ||
      !retentionR ||
      !qualityR ||
      !segR ||
      !freshR ||
      !eventsR
    ) {
      setLoadError('Часть метрик не загрузилась — см. console.warn для деталей.');
    }
  }, [range, token]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void reload();
  }, [reload]);

  return (
    <section className="mt-12 flex flex-col gap-4">
      <header className="flex items-center justify-between gap-3">
        <h2 className="text-[length:var(--text-xl)] font-[var(--font-display)] font-semibold m-0">
          Метрики и observability
        </h2>
        <div className="inline-flex items-center gap-2">
          {(['24h', '7d', '30d'] as const).map((r) => (
            <Button
              key={r}
              type="button"
              variant={range === r ? 'primary' : 'ghost'}
              size="sm"
              onClick={() => setRange(r)}
            >
              {r}
            </Button>
          ))}
          <Button type="button" size="sm" variant="ghost" onClick={() => void reload()}>
            ↻
          </Button>
        </div>
      </header>

      {loadError ? (
        <p className="text-[length:var(--text-xs)] text-[color:var(--color-warning)] m-0">
          {loadError}
        </p>
      ) : null}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <LatencyCard data={latency} />
        <CostCard data={cost} />
        <ActivationFunnelCard data={activation} />
        <RetentionCard data={retention} />
        <QualityCard data={quality} />
        <SegmentWarmupCard data={segmentWarmup} />
        <FreshnessCard data={freshness} />
        <MatchEventsCard data={matchEvents} />
      </div>
    </section>
  );
}

type MetricHelp = {
  what: string;
  good: string;
  bad: string;
  source?: string;
};

function MetricCardShell({
  title,
  help,
  children,
}: {
  title: string;
  help?: MetricHelp;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-2">
          <CardTitle className="text-[length:var(--text-sm)] font-semibold">{title}</CardTitle>
          {help ? <MetricHelpPopover title={title} help={help} /> : null}
        </div>
      </CardHeader>
      <CardContent className="text-[length:var(--text-xs)] text-[color:var(--color-ink)]">
        {children}
      </CardContent>
    </Card>
  );
}

/** Native <details>-based help affordance: a `?` icon next to the card title
 * that expands an inline panel with what/good/bad copy. Zero-dep, mobile-
 * friendly, accessible by default. Closing on outside-click is intentionally
 * skipped — the panel is short, the user closes by clicking `?` again. */
function MetricHelpPopover({ title, help }: { title: string; help: MetricHelp }) {
  return (
    <details className="relative">
      <summary
        className={cn(
          'list-none cursor-pointer select-none',
          'inline-flex items-center justify-center',
          'h-5 w-5 rounded-full',
          'border border-[color:var(--color-ink-muted)]',
          'text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)]',
          'hover:bg-[var(--color-surface-raised)] hover:text-[color:var(--color-ink)]',
          'transition-colors'
        )}
        aria-label={`Что показывает «${title}»`}
        title={`Что показывает «${title}»`}
      >
        ?
      </summary>
      <div
        className={cn(
          'absolute right-0 mt-2 z-30',
          'w-72 max-w-[80vw]',
          'rounded-[var(--radius-md)] border border-[color:var(--color-border)]',
          'bg-[var(--color-surface-raised)] shadow-[var(--shadow-md)]',
          'p-3 flex flex-col gap-2',
          'text-[length:var(--text-xs)] text-[color:var(--color-ink)] leading-snug'
        )}
      >
        <div>
          <div className="text-[color:var(--color-ink-muted)] uppercase tracking-wide text-[10px]">
            Что считает
          </div>
          <div>{help.what}</div>
        </div>
        <div>
          <div className="text-[color:var(--color-ink-muted)] uppercase tracking-wide text-[10px]">
            Хорошо
          </div>
          <div>{help.good}</div>
        </div>
        <div>
          <div className="text-[color:var(--color-ink-muted)] uppercase tracking-wide text-[10px]">
            Плохо
          </div>
          <div>{help.bad}</div>
        </div>
        {help.source ? (
          <div>
            <div className="text-[color:var(--color-ink-muted)] uppercase tracking-wide text-[10px]">
              Источник
            </div>
            <div className="font-[var(--font-mono)] text-[10px]">{help.source}</div>
          </div>
        ) : null}
      </div>
    </details>
  );
}

const HELP_LATENCY: MetricHelp = {
  what: 'Длительность завершённых рекомендательных job’ов (instant + segment_warmup + deep_scan), сгруппирована по типу. p50 — медиана, p95 — 95-й перцентиль, fail % — доля упавших.',
  good: 'instant: p95 ≤ 1 сек (acceptance Phase 6). segment_warmup: p95 ≤ 5 минут. fail % < 5.',
  bad: 'instant p95 > 2 сек — индекс холодеет или Postgres тормозит. fail % > 10 — смотреть recommendation_jobs.error_message.',
  source: 'recommendation_jobs.finished_at - started_at',
};

const HELP_COST: MetricHelp = {
  what: 'Дневные траты на OpenAI по дате и по модели. «Сегодня» / «Вчера» — суммы за UTC-сутки.',
  good: '≤ $1/день при 5 DAU (acceptance Phase 6). Резкого роста при стабильном DAU быть не должно.',
  bad: 'Сегодня > 2× от вчера — что-то жжёт токены (deep_scan loop, плохой prompt). Один model занимает > 80% — дрифт на дорогую модель.',
  source: 'openai_call_log',
};

const HELP_ACTIVATION: MetricHelp = {
  what: 'Воронка из 5 шагов для cohort’а юзеров, загрузивших первое резюме в окне. uploaded → first_search → first_match (есть ≥1 матч) → first_like → first_apply.',
  good: 'first_search ≥ 80% от uploaded, first_match ≥ 70%, first_like ≥ 30%, first_apply ≥ 10% (отраслевые ориентиры для job-board funnel’а).',
  bad: 'Большой обрыв upload → first_search — UX резюме / сайдбар. Большой обрыв first_search → first_match — холодные сегменты не прогреваются.',
  source: 'resumes × recommendation_jobs × user_vacancy_feedback × applications',
};

const HELP_RETENTION: MetricHelp = {
  what: 'Доля юзеров, которые вернулись (хотя бы один логин) в день D+1 / D+7 / D+30 после регистрации. Учитываются только юзеры с достаточной историей.',
  good: 'D+1 ≥ 40%, D+7 ≥ 20%, D+30 ≥ 10% — нормально для job-seeker продукта.',
  bad: 'D+1 < 20% — юзер не возвращается даже на следующий день, продукт не залип. D+7 < 5% — отток.',
  source: 'user_login_events × users.created_at',
};

const HELP_QUALITY: MetricHelp = {
  what: 'Click-Through Rate по тирам (strong / good / maybe). Impressions — сколько раз показали, clicks — сколько раз юзер нажал на карточку. CTR = clicks/impressions.',
  good: 'CTR strong > CTR good > CTR maybe. Это значит ranker правильно ранжирует. Для strong ожидается ≥ 15%, для good ≥ 8%.',
  bad: 'CTR strong ≈ CTR maybe или strong < good — ranker сломан, тир-thresholds дрифтят. 0 impressions — telemetry не пишет.',
  source: 'match_impression × match_click',
};

const HELP_SEGMENT_WARMUP: MetricHelp = {
  what: 'Сколько segment_warmup-job’ов завершилось / упало / висит. daily — счётчик за UTC-сутки относительно cap (по умолчанию 100/день).',
  good: 'completed >> failed. daily utilization < 80%. mean_duration_seconds completed < 600.',
  bad: 'failed > 10% — HH-403/429 или таймауты. utilization 100% — упёрлись в cap, новые сегменты ждут до полуночи. running > 1 надолго — orphan от рестарта (sweep подметёт через 30 мин).',
  source: 'recommendation_jobs WHERE job_type=segment_warmup',
};

const HELP_FRESHNESS: MetricHelp = {
  what: 'История ночных sweep’ов. checked — сколько вакансий перепроверили на HH, archived — сколько оказались в архиве, stopped_early=1 если упёрлись в wall-clock-budget.',
  good: 'archived/checked = 1–10% (нормальный отток). stopped_early=0. Sweep идёт раз в сутки.',
  bad: 'archived = 0 при checked > 100 — HH возвращает archived=false для всех (баг или TLS). stopped_early=1 регулярно — sweep не успевает, нужно увеличить max_runtime_seconds.',
  source: 'freshness_sweep_log',
};

const HELP_MATCH_EVENTS: MetricHelp = {
  what: 'События UI, которые фронтенд шлёт через POST /api/telemetry/event. До v0.23 они принимались и выкидывались — теперь персистятся.',
  good: 'Виден трафик по track_section_expanded / cover_letter_copied и т.п. — фронт жив.',
  bad: 'Все нули — либо никто не пользуется, либо frontend не зовёт endpoint. Resolve: глянуть Network в DevTools.',
  source: 'match_event',
};

function LatencyCard({ data }: { data: LatencyResponse | null }) {
  if (!data)
    return (
      <MetricCardShell title="Latency" help={HELP_LATENCY}>
        …
      </MetricCardShell>
    );
  const types = Object.keys(data.by_job_type);
  return (
    <MetricCardShell title={`Latency (${data.range})`} help={HELP_LATENCY}>
      {types.length === 0 ? (
        <p className="text-[color:var(--color-ink-muted)] m-0">Нет завершённых job’ов в окне.</p>
      ) : (
        <table className="w-full text-left">
          <thead>
            <tr className="text-[color:var(--color-ink-muted)]">
              <th className="font-normal pr-2">job_type</th>
              <th className="font-normal pr-2">n</th>
              <th className="font-normal pr-2">p50</th>
              <th className="font-normal pr-2">p95</th>
              <th className="font-normal">fail %</th>
            </tr>
          </thead>
          <tbody>
            {types.map((jt) => {
              const row = data.by_job_type[jt];
              return (
                <tr key={jt}>
                  <td className="pr-2 font-[var(--font-mono)]">{jt}</td>
                  <td className="pr-2 font-[var(--font-mono)]">{row.count}</td>
                  <td className="pr-2 font-[var(--font-mono)]">{row.p50_seconds}s</td>
                  <td className="pr-2 font-[var(--font-mono)]">{row.p95_seconds}s</td>
                  <td className="font-[var(--font-mono)]">{(row.fail_rate * 100).toFixed(1)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </MetricCardShell>
  );
}

function CostCard({ data }: { data: CostResponse | null }) {
  if (!data)
    return (
      <MetricCardShell title="Cost" help={HELP_COST}>
        …
      </MetricCardShell>
    );
  return (
    <MetricCardShell title={`OpenAI cost (${data.range})`} help={HELP_COST}>
      <div className="grid grid-cols-3 gap-2 mb-2">
        <div>
          <div className="text-[color:var(--color-ink-muted)]">Сегодня</div>
          <div className="font-[var(--font-mono)] text-[length:var(--text-base)]">
            ${data.today_usd.toFixed(2)}
          </div>
        </div>
        <div>
          <div className="text-[color:var(--color-ink-muted)]">Вчера</div>
          <div className="font-[var(--font-mono)] text-[length:var(--text-base)]">
            ${data.yesterday_usd.toFixed(2)}
          </div>
        </div>
        <div>
          <div className="text-[color:var(--color-ink-muted)]">За окно</div>
          <div className="font-[var(--font-mono)] text-[length:var(--text-base)]">
            ${data.total_usd.toFixed(2)}
          </div>
        </div>
      </div>
      {data.by_model.length > 0 ? (
        <div className="mt-1">
          <div className="text-[color:var(--color-ink-muted)] mb-1">По моделям</div>
          {data.by_model.map((m) => (
            <div key={m.model} className="flex justify-between font-[var(--font-mono)]">
              <span>{m.model}</span>
              <span>
                ${m.cost_usd.toFixed(4)} · {m.calls}
              </span>
            </div>
          ))}
        </div>
      ) : null}
    </MetricCardShell>
  );
}

function ActivationFunnelCard({ data }: { data: ActivationResponse | null }) {
  if (!data)
    return (
      <MetricCardShell title="Activation" help={HELP_ACTIVATION}>
        …
      </MetricCardShell>
    );
  return (
    <MetricCardShell
      title={`Activation funnel (${data.range}, n=${data.cohort_size})`}
      help={HELP_ACTIVATION}
    >
      {data.cohort_size === 0 ? (
        <p className="text-[color:var(--color-ink-muted)] m-0">Нет cohort’а в окне.</p>
      ) : (
        <div className="flex flex-col gap-1">
          {data.steps.map((step) => {
            const pct = Math.round(step.share * 100);
            return (
              <div key={step.key} className="flex items-center gap-2">
                <div className="w-28 font-[var(--font-mono)]">{step.key}</div>
                <div
                  className="h-3 rounded-sm bg-[var(--color-accent)]"
                  style={{ width: `${Math.max(2, pct)}%` }}
                />
                <div className="font-[var(--font-mono)]">
                  {step.users} ({pct}%)
                </div>
              </div>
            );
          })}
        </div>
      )}
    </MetricCardShell>
  );
}

function RetentionCard({ data }: { data: RetentionResponse | null }) {
  if (!data)
    return (
      <MetricCardShell title="Retention" help={HELP_RETENTION}>
        …
      </MetricCardShell>
    );
  const buckets: Array<{ key: 'd1' | 'd7' | 'd30'; label: string }> = [
    { key: 'd1', label: 'D+1' },
    { key: 'd7', label: 'D+7' },
    { key: 'd30', label: 'D+30' },
  ];
  return (
    <MetricCardShell title="Retention" help={HELP_RETENTION}>
      <div className="grid grid-cols-3 gap-3">
        {buckets.map((b) => {
          const slot = data[b.key];
          return (
            <div key={b.key}>
              <div className="text-[color:var(--color-ink-muted)]">{b.label}</div>
              <div className="font-[var(--font-mono)] text-[length:var(--text-base)]">
                {(slot.share * 100).toFixed(1)}%
              </div>
              <div className="text-[color:var(--color-ink-muted)] font-[var(--font-mono)]">
                {slot.retained}/{slot.eligible}
              </div>
            </div>
          );
        })}
      </div>
    </MetricCardShell>
  );
}

function QualityCard({ data }: { data: QualityResponse | null }) {
  if (!data)
    return (
      <MetricCardShell title="Quality (CTR)" help={HELP_QUALITY}>
        …
      </MetricCardShell>
    );
  const tiers = Object.keys(data.ctr_by_tier);
  return (
    <MetricCardShell title={`CTR by tier (${data.range})`} help={HELP_QUALITY}>
      {tiers.length === 0 ? (
        <p className="text-[color:var(--color-ink-muted)] m-0">Нет impressions в окне.</p>
      ) : (
        <table className="w-full text-left">
          <thead>
            <tr className="text-[color:var(--color-ink-muted)]">
              <th className="font-normal pr-2">tier</th>
              <th className="font-normal pr-2">impressions</th>
              <th className="font-normal pr-2">clicks</th>
              <th className="font-normal">CTR</th>
            </tr>
          </thead>
          <tbody>
            {tiers.map((tier) => {
              const row = data.ctr_by_tier[tier];
              return (
                <tr key={tier}>
                  <td className="pr-2 font-[var(--font-mono)]">{tier}</td>
                  <td className="pr-2 font-[var(--font-mono)]">{row.impressions}</td>
                  <td className="pr-2 font-[var(--font-mono)]">{row.clicks}</td>
                  <td className="font-[var(--font-mono)]">{(row.ctr * 100).toFixed(2)}%</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </MetricCardShell>
  );
}

function SegmentWarmupCard({ data }: { data: SegmentWarmupResponse | null }) {
  if (!data)
    return (
      <MetricCardShell title="Segment warmup" help={HELP_SEGMENT_WARMUP}>
        …
      </MetricCardShell>
    );
  return (
    <MetricCardShell title={`Segment warmup (${data.range})`} help={HELP_SEGMENT_WARMUP}>
      <div className="flex justify-between mb-1">
        <span className="text-[color:var(--color-ink-muted)]">daily {data.daily_count}/{data.daily_cap}</span>
        <span className="font-[var(--font-mono)]">{(data.daily_utilization * 100).toFixed(1)}%</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        {Object.entries(data.by_status).map(([status, n]) => (
          <div key={status} className="flex justify-between font-[var(--font-mono)]">
            <span>{status}</span>
            <span>{n}</span>
          </div>
        ))}
      </div>
    </MetricCardShell>
  );
}

function FreshnessCard({ data }: { data: FreshnessResponse | null }) {
  if (!data)
    return (
      <MetricCardShell title="Freshness sweeps" help={HELP_FRESHNESS}>
        …
      </MetricCardShell>
    );
  return (
    <MetricCardShell title={`Freshness sweeps (${data.range})`} help={HELP_FRESHNESS}>
      {data.runs.length === 0 ? (
        <p className="text-[color:var(--color-ink-muted)] m-0">Sweeps в окне ещё не было.</p>
      ) : (
        <table className="w-full text-left">
          <thead>
            <tr className="text-[color:var(--color-ink-muted)]">
              <th className="font-normal pr-2">started</th>
              <th className="font-normal pr-2">checked</th>
              <th className="font-normal">archived</th>
            </tr>
          </thead>
          <tbody>
            {data.runs.slice(0, 5).map((r, i) => (
              <tr key={i}>
                <td className="pr-2 font-[var(--font-mono)]">
                  {r.started_at ? new Date(r.started_at).toLocaleString('ru-RU') : '—'}
                </td>
                <td className="pr-2 font-[var(--font-mono)]">{r.checked}</td>
                <td className="font-[var(--font-mono)]">{r.archived}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </MetricCardShell>
  );
}

function MatchEventsCard({ data }: { data: MatchEventsResponse | null }) {
  if (!data)
    return (
      <MetricCardShell title="Match events" help={HELP_MATCH_EVENTS}>
        …
      </MetricCardShell>
    );
  return (
    <MetricCardShell title={`Match events (${data.range})`} help={HELP_MATCH_EVENTS}>
      {data.events.length === 0 ? (
        <p className="text-[color:var(--color-ink-muted)] m-0">Событий /event не было.</p>
      ) : (
        data.events.map((row) => (
          <div key={row.event} className="flex justify-between font-[var(--font-mono)]">
            <span>{row.event}</span>
            <span>{row.count}</span>
          </div>
        ))
      )}
    </MetricCardShell>
  );
}

function OverviewStat({
  label,
  value,
  hint,
}: {
  label: string;
  value: number;
  hint?: string;
}) {
  return (
    <Card className="animate-fade-in">
      <CardContent className="py-4">
        <div
          className={cn(
            'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
            'uppercase tracking-[0.1em] font-bold mb-1'
          )}
        >
          {label}
        </div>
        <div
          className={cn(
            'font-[var(--font-mono)] text-[length:var(--text-3xl)]',
            'font-semibold text-[color:var(--color-ink)] leading-none'
          )}
        >
          {value}
        </div>
        {hint ? (
          <div
            className={cn(
              'mt-1 text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)]',
              'font-[var(--font-mono)]'
            )}
          >
            {hint}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function ActiveJobRow({
  job,
  onCancel,
  onOpenFunnel,
  isCancelling,
}: {
  job: AdminActiveJob;
  onCancel: (jobId: string) => void;
  onOpenFunnel: (jobId: string) => void;
  isCancelling: boolean;
}) {
  const terminal = job.cancel_requested;
  const created = new Date(job.created_at).toLocaleString('ru-RU');
  return (
    <li className="flex flex-wrap items-center gap-3 justify-between py-3">
      <div className="flex flex-col gap-0.5 min-w-0">
        <div
          className={cn(
            'text-[length:var(--text-sm)] text-[color:var(--color-ink)]',
            'font-semibold truncate max-w-[60ch]'
          )}
        >
          {job.target_role ?? '— роль не указана —'}
        </div>
        <div
          className={cn(
            'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
            'font-[var(--font-mono)]'
          )}
        >
          {job.user_email ?? `user ${job.user_id}`} · {job.status}/{job.stage} ·{' '}
          {job.progress}% · {created}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => onOpenFunnel(job.id)}>
          Воронка
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onCancel(job.id)}
          disabled={isCancelling || terminal}
        >
          {terminal ? 'Остановка…' : isCancelling ? 'Останавливаю…' : 'Остановить'}
        </Button>
      </div>
    </li>
  );
}

function RecentJobRow({
  job,
  onOpenFunnel,
}: {
  job: AdminRecentJob;
  onOpenFunnel: (jobId: string) => void;
}) {
  const created = new Date(job.created_at).toLocaleString('ru-RU');
  return (
    <li className="flex flex-wrap items-center gap-3 justify-between py-3">
      <div className="flex flex-col gap-0.5 min-w-0">
        <div
          className={cn(
            'text-[length:var(--text-sm)] text-[color:var(--color-ink)]',
            'font-semibold truncate max-w-[60ch]'
          )}
        >
          {job.target_role ?? '— роль не указана —'}
        </div>
        <div
          className={cn(
            'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
            'font-[var(--font-mono)]'
          )}
        >
          {job.user_email ?? `user ${job.user_id}`} · {job.status} ·{' '}
          {job.matches_count} матчей · {created}
        </div>
      </div>
      <Button variant="ghost" size="sm" onClick={() => onOpenFunnel(job.id)}>
        Воронка
      </Button>
    </li>
  );
}

function FunnelStageBar({ stage, max }: { stage: AdminFunnelStage; max: number }) {
  const safeMax = Math.max(1, max);
  const pct = Math.min(100, Math.round((stage.value / safeMax) * 100));
  const accent =
    stage.kind === 'drop'
      ? 'var(--color-danger)'
      : stage.kind === 'meta'
      ? 'var(--color-ink-muted)'
      : 'var(--color-accent)';
  return (
    <div className="flex flex-col gap-1 py-1.5">
      <div className="flex items-baseline justify-between gap-3">
        <span
          className={cn(
            'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
            'truncate'
          )}
        >
          {stage.label}
        </span>
        <span
          className={cn(
            'font-[var(--font-mono)] text-[length:var(--text-sm)]',
            'text-[color:var(--color-ink)] tabular-nums shrink-0'
          )}
        >
          {stage.value}
        </span>
      </div>
      <div
        className="h-1.5 rounded-full bg-[var(--color-surface-muted)] overflow-hidden"
        aria-hidden
      >
        <div
          className="h-full rounded-full transition-[width] duration-[var(--duration-normal)]"
          style={{
            width: `${pct}%`,
            backgroundColor: accent,
          }}
        />
      </div>
    </div>
  );
}

function FunnelDialog({
  job,
  loading,
  error,
  onClose,
}: {
  job: AdminJobFunnel | null;
  loading: boolean;
  error: string | null;
  onClose: () => void;
}) {
  const open = loading || job !== null || error !== null;
  const maxFlow = job
    ? Math.max(...job.stages.map((s) => s.value), job.fetched_raw, 1)
    : 1;
  const maxDrop = job ? Math.max(...job.drops.map((s) => s.value), 1) : 1;
  const nonZeroDrops = job ? job.drops.filter((d) => d.value > 0) : [];
  const nonZeroMatcher = job
    ? job.matcher_stages.filter((s) => s.value > 0)
    : [];
  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (!nextOpen) onClose();
      }}
    >
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Воронка подбора</DialogTitle>
          {job ? (
            <DialogDescription>
              {job.target_role ?? 'роль не указана'} ·{' '}
              <span className="font-[var(--font-mono)]">{job.status}</span> ·{' '}
              {job.user_email ?? `user ${job.user_id}`}
            </DialogDescription>
          ) : null}
        </DialogHeader>

        {loading ? (
          <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
            Загружаем…
          </p>
        ) : error ? (
          <p className="text-[length:var(--text-sm)] text-[color:var(--color-danger)]">
            {error}
          </p>
        ) : job ? (
          <div className="flex flex-col gap-5">
            <div className="grid grid-cols-3 gap-3">
              <SummaryTile label="Fetched raw" value={job.fetched_raw} />
              <SummaryTile label="Всего отфильтровано" value={job.total_drops} />
              <SummaryTile label="Показано юзеру" value={job.shown_to_user} />
            </div>

            <section>
              <h3
                className={cn(
                  'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
                  'uppercase tracking-[0.1em] font-bold mb-2'
                )}
              >
                Основной поток
              </h3>
              <div className="flex flex-col">
                {job.stages.map((s) => (
                  <FunnelStageBar key={s.key} stage={s} max={maxFlow} />
                ))}
              </div>
            </section>

            {nonZeroDrops.length > 0 ? (
              <section>
                <h3
                  className={cn(
                    'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
                    'uppercase tracking-[0.1em] font-bold mb-2'
                  )}
                >
                  Отсев по причинам
                </h3>
                <div className="flex flex-col">
                  {nonZeroDrops.map((s) => (
                    <FunnelStageBar key={s.key} stage={s} max={maxDrop} />
                  ))}
                </div>
              </section>
            ) : null}

            {nonZeroMatcher.length > 0 ? (
              <section>
                <h3
                  className={cn(
                    'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
                    'uppercase tracking-[0.1em] font-bold mb-2'
                  )}
                >
                  Матчер
                </h3>
                <div className="flex flex-col">
                  {nonZeroMatcher.map((s) => (
                    <FunnelStageBar key={s.key} stage={s} max={maxDrop} />
                  ))}
                </div>
              </section>
            ) : null}

            <div
              className={cn(
                'text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)]',
                'font-[var(--font-mono)]'
              )}
            >
              Остаток (неклассифицированный): {job.residual}
            </div>

            <details className="text-[length:var(--text-xs)]">
              <summary
                className={cn(
                  'cursor-pointer text-[color:var(--color-ink-secondary)]',
                  'uppercase tracking-[0.1em] font-bold'
                )}
              >
                Сырые метрики
              </summary>
              <pre
                className={cn(
                  'mt-2 font-[var(--font-mono)] text-[length:var(--text-xs)]',
                  'text-[color:var(--color-ink-secondary)]',
                  'bg-[var(--color-surface-muted)] p-3 rounded-[var(--radius-sm)]',
                  'overflow-x-auto'
                )}
              >
                {JSON.stringify(job.metrics, null, 2)}
              </pre>
            </details>
          </div>
        ) : null}
      </DialogContent>
    </Dialog>
  );
}

function SummaryTile({ label, value }: { label: string; value: number }) {
  return (
    <div
      className={cn(
        'bg-[var(--color-surface-muted)] rounded-[var(--radius-md)] px-3 py-2'
      )}
    >
      <div
        className={cn(
          'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
          'uppercase tracking-[0.1em] font-bold mb-1'
        )}
      >
        {label}
      </div>
      <div
        className={cn(
          'font-[var(--font-mono)] text-[length:var(--text-lg)]',
          'font-semibold text-[color:var(--color-ink)]'
        )}
      >
        {value}
      </div>
    </div>
  );
}

function MiniBarChart({ data, label }: { data: AdminDailyCount[]; label: string }) {
  const maxCount = Math.max(...data.map((d) => d.count), 1);
  const total = data.reduce((sum, d) => sum + d.count, 0);
  const CHART_HEIGHT = 40;
  return (
    <div className="flex flex-col gap-2">
      <div
        className={cn(
          'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
          'uppercase tracking-[0.1em] font-bold'
        )}
      >
        {label}
      </div>
      <div className="flex items-end gap-px" style={{ height: `${CHART_HEIGHT}px` }}>
        {data.map((d) => {
          const barH = Math.max(2, Math.round((d.count / maxCount) * CHART_HEIGHT));
          return (
            <div
              key={d.date}
              title={`${d.date}: ${d.count}`}
              className="flex-1 rounded-sm bg-primary opacity-70 hover:opacity-100 transition-opacity cursor-default"
              style={{ height: `${barH}px` }}
            />
          );
        })}
      </div>
      <div
        className={cn(
          'text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)]',
          'font-[var(--font-mono)]'
        )}
      >
        Итого за 14 дней: {total}
      </div>
    </div>
  );
}

function ActivityCard({ activity }: { activity: AdminActivity }) {
  return (
    <Card className="animate-fade-in">
      <CardHeader>
        <CardTitle>Активность пользователей</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        <div className="grid grid-cols-3 gap-4">
          <div className="flex flex-col gap-1">
            <div
              className={cn(
                'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
                'uppercase tracking-[0.1em] font-bold'
              )}
            >
              За 24 часа
            </div>
            <div
              className={cn(
                'font-[var(--font-mono)] text-[length:var(--text-3xl)]',
                'font-semibold text-[color:var(--color-ink)] leading-none'
              )}
            >
              {activity.dau}
            </div>
            <div
              className={cn(
                'text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)]',
                'font-[var(--font-mono)]'
              )}
            >
              DAU
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <div
              className={cn(
                'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
                'uppercase tracking-[0.1em] font-bold'
              )}
            >
              За неделю
            </div>
            <div
              className={cn(
                'font-[var(--font-mono)] text-[length:var(--text-3xl)]',
                'font-semibold text-[color:var(--color-ink)] leading-none'
              )}
            >
              {activity.wau}
            </div>
            <div
              className={cn(
                'text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)]',
                'font-[var(--font-mono)]'
              )}
            >
              WAU
            </div>
          </div>
          <div className="flex flex-col gap-1">
            <div
              className={cn(
                'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
                'uppercase tracking-[0.1em] font-bold'
              )}
            >
              За месяц
            </div>
            <div
              className={cn(
                'font-[var(--font-mono)] text-[length:var(--text-3xl)]',
                'font-semibold text-[color:var(--color-ink)] leading-none'
              )}
            >
              {activity.mau}
            </div>
            <div
              className={cn(
                'text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)]',
                'font-[var(--font-mono)]'
              )}
            >
              MAU
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-2 border-t border-[var(--color-border)]">
          <MiniBarChart data={activity.signups_per_day} label="Регистрации" />
          <MiniBarChart data={activity.logins_per_day} label="Логины" />
        </div>
      </CardContent>
    </Card>
  );
}

function StatRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string | number;
  mono?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <dt
        className={cn(
          'text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]',
          'uppercase tracking-[0.1em] font-bold shrink-0'
        )}
      >
        {label}
      </dt>
      <dd
        className={cn(
          'text-[length:var(--text-sm)] text-[color:var(--color-ink)] text-right m-0',
          mono && 'font-[var(--font-mono)]'
        )}
      >
        {value}
      </dd>
    </div>
  );
}
