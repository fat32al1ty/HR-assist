'use client';

import * as React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { SkillGap, SkillGapsData } from '@/types/audit';

/** Normalise the two possible shapes the backend may return. */
function normaliseSkillGaps(raw: SkillGapsData | SkillGap[]): { gaps: SkillGap[]; sampleSize: number | null } {
  if (Array.isArray(raw)) {
    return { gaps: raw, sampleSize: null };
  }
  return { gaps: raw.gaps, sampleSize: raw.sample_size };
}

interface SkillGapsCardProps {
  skillGaps: SkillGapsData | SkillGap[];
  className?: string;
}

interface SkillRowProps {
  gap: SkillGap;
  index: number;
}

function SkillRow({ gap, index }: SkillRowProps) {
  const pct = Math.round(gap.vacancies_with_skill_pct);
  const isOwned = gap.owned;

  // Stagger delay via inline style — respects the parent stagger-children if needed,
  // but we do it manually here for fine-grained control within a list
  const delay = `${index * 50}ms`;

  return (
    <li
      className="animate-fade-in flex items-center gap-3 py-3 border-b border-[color-mix(in_srgb,var(--color-border)_70%,transparent)] last:border-0"
      style={{ animationDelay: delay }}
    >
      {/* Rank index */}
      <span
        className="shrink-0 w-6 h-6 rounded-full flex items-center justify-center text-[length:var(--text-xs)] font-bold bg-[var(--color-surface-muted)] text-[color:var(--color-ink-muted)]"
        aria-hidden="true"
      >
        {index + 1}
      </span>

      {/* Skill name + bar */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1.5">
          <span
            className={cn(
              'text-[length:var(--text-sm)] font-semibold',
              isOwned ? 'text-[color:var(--color-success)]' : 'text-[color:var(--color-ink)]'
            )}
          >
            {gap.skill}
          </span>
          {isOwned && (
            <Badge variant="success" className="text-[10px] py-0">
              Есть в резюме
            </Badge>
          )}
        </div>

        {/* Frequency bar */}
        <div
          className="h-1.5 w-full rounded-[var(--radius-full)] bg-[var(--color-surface-muted)] overflow-hidden"
          role="meter"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={pct}
          aria-label={`${pct}% вакансий требуют этот навык`}
        >
          <div
            className={cn(
              'h-full rounded-[var(--radius-full)] transition-[width] duration-[var(--duration-slow)]',
              isOwned ? 'bg-[var(--color-success)]' : 'bg-[var(--color-skill-gap-bar)]'
            )}
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Percentage label */}
      <span
        className={cn(
          'shrink-0 text-[length:var(--text-sm)] font-bold font-mono tabular-nums',
          isOwned ? 'text-[color:var(--color-success)]' : 'text-[color:var(--color-ink)]'
        )}
      >
        {pct}%
      </span>
    </li>
  );
}

const THIN_DATA_THRESHOLD = 10;

export function SkillGapsCard({ skillGaps, className }: SkillGapsCardProps) {
  const { gaps, sampleSize } = normaliseSkillGaps(skillGaps);
  const isThinData = sampleSize !== null && sampleSize < THIN_DATA_THRESHOLD;
  const missingCount = gaps.filter((g) => !g.owned).length;

  return (
    <Card className={cn('bg-[var(--color-surface)]', className)}>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <span className="block text-[length:var(--text-xs)] font-bold tracking-[0.1em] uppercase text-[color:var(--color-ink-muted)] mb-1">
              Пробелы в навыках
            </span>
            <CardTitle>Топ-{gaps.length} навыков рынка</CardTitle>
          </div>
          {!isThinData && missingCount > 0 && (
            <Badge variant="warning" className="mt-1 shrink-0">
              {missingCount} не хватает
            </Badge>
          )}
          {!isThinData && missingCount === 0 && gaps.length > 0 && (
            <Badge variant="success" className="mt-1 shrink-0">
              Всё есть
            </Badge>
          )}
        </div>
        <CardDescription className="mt-1">
          Доля вакансий для вашей роли и уровня, где встречается каждый навык
        </CardDescription>
      </CardHeader>

      <CardContent>
        {isThinData ? (
          <p className="text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)] leading-[var(--leading-snug)]">
            Рынок для твоей роли в нашей базе пока тонок — не показываем «топ-N навыков», чтобы не вводить в заблуждение. Используй подбор для конкретных вакансий.
          </p>
        ) : gaps.length === 0 ? (
          <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] italic">
            Данных о навыках по вашему сегменту пока нет.
          </p>
        ) : (
          <ul className="list-none p-0 m-0" role="list" aria-label="Список навыков рынка">
            {gaps.map((gap, i) => (
              <SkillRow key={gap.skill} gap={gap} index={i} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
