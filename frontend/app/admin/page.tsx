'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useSession } from '@/lib/session';
import { apiFetch } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type {
  AdminActiveJob,
  AdminJobCancelResponse,
  AdminOverviewResponse,
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
                      isCancelling={cancellingJobId === job.id}
                    />
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>
        </section>
      ) : null}

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
  isCancelling,
}: {
  job: AdminActiveJob;
  onCancel: (jobId: string) => void;
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
      <Button
        variant="ghost"
        size="sm"
        onClick={() => onCancel(job.id)}
        disabled={isCancelling || terminal}
      >
        {terminal ? 'Остановка…' : isCancelling ? 'Останавливаю…' : 'Остановить'}
      </Button>
    </li>
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
