'use client';

import * as React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { cn } from '@/lib/utils';
import type { QualityIssue, QualityIssueSeverity } from '@/types/audit';

interface ResumeQualityCardProps {
  qualityIssues: QualityIssue[];
  className?: string;
}

const SEVERITY_CONFIG: Record<
  QualityIssueSeverity,
  { label: string; tokenBg: string; tokenBorder: string; tokenText: string; dotColor: string }
> = {
  info: {
    label: 'Инфо',
    tokenBg:     'var(--color-status-info-subtle)',
    tokenBorder: 'color-mix(in srgb, var(--color-status-info) 20%, transparent)',
    tokenText:   'var(--color-status-info)',
    dotColor:    'var(--color-status-info)',
  },
  warn: {
    label: 'Внимание',
    tokenBg:     'var(--color-status-warn-subtle)',
    tokenBorder: 'color-mix(in srgb, var(--color-status-warn) 25%, transparent)',
    tokenText:   'var(--color-status-warn)',
    dotColor:    'var(--color-status-warn)',
  },
  error: {
    label: 'Проблема',
    tokenBg:     'var(--color-status-error-subtle)',
    tokenBorder: 'color-mix(in srgb, var(--color-status-error) 30%, transparent)',
    tokenText:   'var(--color-status-error)',
    dotColor:    'var(--color-status-error)',
  },
};

function QualityRow({ issue, index }: { issue: QualityIssue; index: number }) {
  const cfg = SEVERITY_CONFIG[issue.severity];
  const delay = `${index * 40}ms`;

  return (
    <li
      className="animate-fade-in flex items-start gap-3 py-3 border-b border-[color-mix(in_srgb,var(--color-border)_70%,transparent)] last:border-0"
      style={{ animationDelay: delay }}
    >
      {/* Severity dot */}
      <span
        className="mt-1.5 shrink-0 w-2 h-2 rounded-full"
        style={{ background: cfg.dotColor }}
        aria-hidden="true"
      />

      {/* Message */}
      <div className="flex-1 min-w-0">
        <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink)] leading-[var(--leading-snug)]">
          {issue.message}
        </p>
        <code className="mt-0.5 block text-[length:var(--text-xs)] font-mono text-[color:var(--color-ink-muted)]">
          {issue.rule_id}
        </code>
      </div>

      {/* Severity badge */}
      <span
        className="shrink-0 mt-0.5 px-2 py-0.5 rounded-[var(--radius-full)] text-[10px] font-bold tracking-[0.05em] uppercase whitespace-nowrap border"
        style={{
          background:   cfg.tokenBg,
          borderColor:  cfg.tokenBorder,
          color:        cfg.tokenText,
        }}
      >
        {cfg.label}
      </span>
    </li>
  );
}

function severityOrder(s: QualityIssueSeverity): number {
  return s === 'error' ? 0 : s === 'warn' ? 1 : 2;
}

export function ResumeQualityCard({ qualityIssues, className }: ResumeQualityCardProps) {
  const errorCount = qualityIssues.filter((i) => i.severity === 'error').length;
  const warnCount  = qualityIssues.filter((i) => i.severity === 'warn').length;

  const sorted = [...qualityIssues].sort(
    (a, b) => severityOrder(a.severity) - severityOrder(b.severity)
  );

  const summaryText =
    errorCount > 0
      ? `${errorCount} критических проблем${warnCount > 0 ? `, ${warnCount} предупреждений` : ''}`
      : warnCount > 0
      ? `${warnCount} предупреждений`
      : 'Критических замечаний нет';

  return (
    <Card className={cn('bg-[var(--color-surface)]', className)}>
      <CardHeader>
        <span className="block text-[length:var(--text-xs)] font-bold tracking-[0.1em] uppercase text-[color:var(--color-ink-muted)] mb-1">
          Сигнальное качество резюме
        </span>
        <CardTitle>Проверка структуры</CardTitle>
        <CardDescription className="mt-1">{summaryText}</CardDescription>
      </CardHeader>

      <CardContent>
        {sorted.length === 0 ? (
          <div
            className="flex items-center gap-2.5 px-4 py-3 rounded-[var(--radius-md)] border"
            style={{
              background:  'var(--color-status-info-subtle)',
              borderColor: 'color-mix(in srgb, var(--color-status-info) 20%, transparent)',
            }}
          >
            <span
              className="w-2 h-2 rounded-full shrink-0"
              style={{ background: 'var(--color-status-info)' }}
              aria-hidden="true"
            />
            <p
              className="text-[length:var(--text-sm)] font-semibold"
              style={{ color: 'var(--color-status-info)' }}
            >
              Структура резюме в порядке
            </p>
          </div>
        ) : (
          <ul className="list-none p-0 m-0" role="list" aria-label="Замечания к резюме">
            {sorted.map((issue, i) => (
              <QualityRow key={issue.rule_id} issue={issue} index={i} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
