'use client';

import * as React from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { MarketSalary } from '@/types/audit';

interface MarketSalaryCardProps {
  salary: MarketSalary | null;
  className?: string;
}

function formatRub(n: number): string {
  // e.g. 230000 -> "230 000"
  return n.toLocaleString('ru-RU');
}

// Renders the p25–p75 band as a visual track with a midpoint marker
function SalaryBand({ p25, p50, p75 }: { p25: number; p50: number; p75: number }) {
  const range = p75 - p25;
  const medianPct = range > 0 ? ((p50 - p25) / range) * 100 : 50;

  return (
    <div className="mt-5 mb-2" aria-hidden="true">
      {/* Band labels */}
      <div className="flex justify-between mb-1.5">
        <span className="text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)] font-semibold">
          P25 — {formatRub(p25)} ₽
        </span>
        <span className="text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)] font-semibold">
          P75 — {formatRub(p75)} ₽
        </span>
      </div>

      {/* Gradient track */}
      <div
        className="relative h-3 rounded-[var(--radius-full)] overflow-visible"
        style={{
          background: 'linear-gradient(to right, var(--color-salary-band-low), var(--color-salary-band-mid), var(--color-salary-band-high))',
        }}
        role="presentation"
      >
        {/* Median marker */}
        <div
          className="absolute top-1/2 -translate-y-1/2 -translate-x-1/2 w-4 h-4 rounded-full bg-[var(--color-surface)] border-2 border-[var(--color-salary-band-peak)] shadow-[var(--shadow-sm)]"
          style={{ left: `${medianPct}%` }}
          title={`Медиана: ${formatRub(p50)} ₽`}
        />
      </div>

      {/* Median label below track */}
      <div
        className="relative mt-1"
        style={{ paddingLeft: `${Math.max(0, Math.min(medianPct, 90))}%` }}
      >
        <span
          className="text-[length:var(--text-xs)] font-bold text-[color:var(--color-salary-band-peak)] whitespace-nowrap"
          style={{ display: 'inline-block', transform: 'translateX(-50%)' }}
        >
          Медиана
        </span>
      </div>
    </div>
  );
}

export function MarketSalaryCard({ salary, className }: MarketSalaryCardProps) {
  if (!salary) {
    return (
      <Card className={cn('bg-[var(--color-surface)]', className)}>
        <CardHeader>
          <span className="block text-[length:var(--text-xs)] font-bold tracking-[0.1em] uppercase text-[color:var(--color-ink-muted)] mb-1">
            Рыночная зарплата
          </span>
          <CardTitle>Данных недостаточно</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
            Не хватает данных по вашему сегменту для построения вилки. Попробуйте уточнить город и специализацию.
          </p>
        </CardContent>
      </Card>
    );
  }

  const { p25, p50, p75, currency, user_expectation, gap_to_median_pct, sample_size } = salary;
  const hasExpectation = user_expectation !== null;
  const hasGap = gap_to_median_pct !== null;
  const gapPositive = hasGap && gap_to_median_pct! >= 0;
  const gapAbs = hasGap ? Math.abs(gap_to_median_pct!) : 0;

  return (
    <Card className={cn('bg-[var(--color-surface)]', className)}>
      <CardHeader>
        <span className="block text-[length:var(--text-xs)] font-bold tracking-[0.1em] uppercase text-[color:var(--color-ink-muted)] mb-1">
          Рыночная зарплата
        </span>

        {/* Hero metric — p50, typeset large */}
        <div className="flex items-baseline gap-3 flex-wrap">
          <span
            className="font-bold leading-[1] tracking-[-0.04em] text-[color:var(--color-ink)]"
            style={{ fontSize: 'clamp(2.25rem, 5vw, 3.5rem)' }}
            aria-label={`Медиана ${formatRub(p50)} рублей в месяц`}
          >
            {formatRub(p50)}
          </span>
          <span className="text-[length:var(--text-2xl)] font-semibold text-[color:var(--color-ink-secondary)]">
            {currency === 'RUB' ? '₽' : currency}
            <span className="text-[length:var(--text-sm)] ml-1 font-normal">/мес</span>
          </span>
        </div>

        {/* Salary band gradient */}
        <SalaryBand p25={p25} p50={p50} p75={p75} />
      </CardHeader>

      <CardContent>
        <div className="grid gap-3">
          {/* Gap to median */}
          {hasExpectation && hasGap && (
            <div
              className={cn(
                'flex items-center justify-between gap-2 px-3 py-2.5 rounded-[var(--radius-md)] border text-[length:var(--text-sm)]',
                gapPositive
                  ? 'bg-[var(--color-success-subtle)] border-[color-mix(in_srgb,var(--color-success)_25%,transparent)] text-[color:var(--color-success)]'
                  : 'bg-[var(--color-warning-subtle)] border-[color-mix(in_srgb,var(--color-warning)_25%,transparent)] text-[color:var(--color-warning)]'
              )}
              role="status"
            >
              <span className="font-semibold">Ваши ожидания:</span>
              <span className="font-bold font-mono">
                {formatRub(user_expectation!)} ₽
                {' '}
                <span className="font-normal">
                  ({gapPositive ? '+' : '−'}{gapAbs.toFixed(0)}% к медиане)
                </span>
              </span>
            </div>
          )}

          {hasExpectation && !hasGap && (
            <div className="flex items-center justify-between gap-2 px-3 py-2.5 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-muted)] text-[length:var(--text-sm)]">
              <span className="font-semibold text-[color:var(--color-ink-secondary)]">Ваши ожидания:</span>
              <span className="font-bold font-mono text-[color:var(--color-ink)]">{formatRub(user_expectation!)} ₽</span>
            </div>
          )}

          {/* Sample size + disclaimer */}
          <div className="flex items-center gap-2 flex-wrap">
            {sample_size !== null && (
              <Badge variant="default">
                {sample_size.toLocaleString('ru-RU')} вакансий в выборке
              </Badge>
            )}
            <span className="text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)] leading-[var(--leading-snug)]">
              Оценка на основе проиндексированных вакансий. Данные за последние 30 дней.
            </span>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
