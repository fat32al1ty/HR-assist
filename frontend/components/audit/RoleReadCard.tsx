'use client';

import * as React from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { RoleRead } from '@/types/audit';

interface RoleReadCardProps {
  roleRead: RoleRead;
  className?: string;
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div
      className="mt-1.5 h-1.5 w-full rounded-[var(--radius-full)] bg-[var(--color-surface-muted)] overflow-hidden"
      role="meter"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={pct}
      aria-label={`Уверенность ${pct}%`}
    >
      <div
        className="h-full rounded-[var(--radius-full)] bg-[var(--color-accent)] transition-[width] duration-[var(--duration-slow)]"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export function RoleReadCard({ roleRead, className }: RoleReadCardProps) {
  const { primary, alt } = roleRead;
  const primaryPct = Math.round(primary.confidence * 100);

  return (
    <Card className={cn('bg-[var(--color-surface)]', className)}>
      <CardHeader>
        <div className="flex items-start gap-3">
          <div className="flex-1 min-w-0">
            <span
              className="block text-[length:var(--text-xs)] font-bold tracking-[0.1em] uppercase text-[color:var(--color-ink-muted)] mb-1"
              aria-hidden="true"
            >
              Рынок видит вас как
            </span>
            <CardTitle className="text-[length:var(--text-3xl)] tracking-[-0.04em] leading-[var(--leading-tight)]">
              {primary.role_family}
            </CardTitle>
          </div>
          <Badge variant="accent" className="mt-1 shrink-0">
            {primary.seniority}
          </Badge>
        </div>
        <CardDescription className="mt-1">
          Уверенность: {primaryPct}%
        </CardDescription>
        <ConfidenceBar value={primary.confidence} />
      </CardHeader>

      {alt.length > 0 && (
        <CardContent>
          <p className="text-[length:var(--text-xs)] font-bold tracking-[0.08em] uppercase text-[color:var(--color-ink-muted)] mb-3">
            Альтернативные прочтения
          </p>
          <ul className="grid gap-2.5" role="list">
            {alt.map((entry) => (
              <li key={`${entry.role_family}-${entry.seniority}`}>
                <div className="flex items-center justify-between gap-2 mb-1">
                  <span className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">
                    {entry.role_family}
                  </span>
                  <span className="text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)] font-mono shrink-0">
                    {Math.round(entry.confidence * 100)}% · {entry.seniority}
                  </span>
                </div>
                <ConfidenceBar value={entry.confidence} />
              </li>
            ))}
          </ul>
        </CardContent>
      )}
    </Card>
  );
}
