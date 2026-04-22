'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useSession } from '@/lib/session';
import { apiFetch } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import type { AdminStatsResponse } from '@/types/admin';

export default function AdminPage() {
  const { token, user } = useSession();
  const [stats, setStats] = useState<AdminStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token || !user?.is_admin) {
      setLoading(false);
      return;
    }

    async function loadStats() {
      setLoading(true);
      setError(null);
      try {
        const data = await apiFetch<AdminStatsResponse>('/api/admin/stats', {
          token: token ?? undefined,
        });
        setStats(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Не удалось загрузить статистику');
      } finally {
        setLoading(false);
      }
    }

    void loadStats();
  }, [token, user]);

  // Not authenticated — nothing to show (Topbar handles login redirect)
  if (!token) {
    return null;
  }

  // Not admin — 403 empty state
  if (!user?.is_admin) {
    return (
      <main
        style={{
          minHeight: '60vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '1rem',
          fontFamily: 'var(--font-body)',
          color: 'var(--color-ink)',
        }}
      >
        <p style={{ fontSize: 'var(--text-2xl)', fontWeight: 600 }}>Нет доступа</p>
        <p style={{ color: 'var(--color-ink-secondary)' }}>
          Этот раздел доступен только администраторам.
        </p>
        <Link
          href="/"
          style={{ color: 'var(--color-accent)', textDecoration: 'none' }}
        >
          ← На главную
        </Link>
      </main>
    );
  }

  if (loading) {
    return (
      <main
        style={{
          padding: '2rem',
          fontFamily: 'var(--font-body)',
          color: 'var(--color-ink-secondary)',
        }}
      >
        Загружаем данные...
      </main>
    );
  }

  if (error) {
    return (
      <main
        style={{
          padding: '2rem',
          fontFamily: 'var(--font-body)',
          color: 'var(--color-danger)',
        }}
      >
        {error}
      </main>
    );
  }

  const qdrant = stats?.qdrant;
  const lastJob = stats?.last_job;
  const warmup = stats?.warmup;

  return (
    <main
      style={{
        maxWidth: '1200px',
        margin: '0 auto',
        padding: '2rem 1.5rem',
        fontFamily: 'var(--font-body)',
      }}
    >
      <h1
        style={{
          fontFamily: 'var(--font-display)',
          fontSize: 'var(--text-3xl)',
          fontWeight: 600,
          color: 'var(--color-ink)',
          marginBottom: '1.5rem',
          letterSpacing: '-0.03em',
        }}
      >
        Админ-панель
      </h1>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '1.5rem',
        }}
      >
        {/* Qdrant card */}
        <Card>
          <CardHeader>
            <CardTitle
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 'var(--text-xl)',
                color: 'var(--color-ink)',
              }}
            >
              Qdrant
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
              }}
            >
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
        <Card>
          <CardHeader>
            <CardTitle
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 'var(--text-xl)',
                color: 'var(--color-ink)',
              }}
            >
              Последний job
            </CardTitle>
          </CardHeader>
          <CardContent>
            {lastJob == null ? (
              <p
                style={{
                  color: 'var(--color-ink-muted)',
                  fontSize: 'var(--text-sm)',
                }}
              >
                Нет данных. Передайте ?resume_id=N в URL.
              </p>
            ) : (
              <dl
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '0.5rem',
                }}
              >
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
        <Card>
          <CardHeader>
            <CardTitle
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: 'var(--text-xl)',
                color: 'var(--color-ink)',
              }}
            >
              Warmup internals
            </CardTitle>
          </CardHeader>
          <CardContent>
            <dl
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '0.5rem',
              }}
            >
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
              {warmup?.last_metrics != null ? (
                <div>
                  <dt
                    style={{
                      fontSize: 'var(--text-xs)',
                      color: 'var(--color-ink-muted)',
                      marginBottom: '2px',
                    }}
                  >
                    Метрики последнего прогона
                  </dt>
                  <dd>
                    <pre
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 'var(--text-xs)',
                        color: 'var(--color-ink-secondary)',
                        background: 'var(--color-surface-muted)',
                        padding: '0.5rem',
                        borderRadius: 'var(--radius-sm, 4px)',
                        overflowX: 'auto',
                        margin: 0,
                      }}
                    >
                      {JSON.stringify(warmup.last_metrics, null, 2)}
                    </pre>
                  </dd>
                </div>
              ) : null}
              {warmup?.profile_backfill != null ? (
                <>
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
                </>
              ) : null}
            </dl>
          </CardContent>
        </Card>
      </div>

      {stats?.generated_at ? (
        <p
          style={{
            marginTop: '1.5rem',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-ink-muted)',
            fontFamily: 'var(--font-body)',
          }}
        >
          Данные на: {new Date(stats.generated_at).toLocaleString('ru-RU')}
        </p>
      ) : null}
    </main>
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
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        gap: '1rem',
      }}
    >
      <dt
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--color-ink-secondary)',
          flexShrink: 0,
        }}
      >
        {label}
      </dt>
      <dd
        style={{
          fontSize: 'var(--text-sm)',
          color: 'var(--color-ink)',
          fontFamily: mono ? 'var(--font-mono)' : 'var(--font-body)',
          textAlign: 'right',
          margin: 0,
        }}
      >
        {value}
      </dd>
    </div>
  );
}
