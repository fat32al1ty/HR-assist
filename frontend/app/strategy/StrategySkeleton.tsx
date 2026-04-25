'use client';

import * as React from 'react';

function SkeletonBlock({ height }: { height: string }) {
  return (
    <div
      className="animate-pulse rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface-muted)]"
      style={{ height }}
      aria-hidden="true"
    >
      {/* Inner lines */}
      <div className="p-5 flex flex-col gap-3">
        <div
          className="rounded-[var(--radius-sm)] bg-[var(--color-surface)]"
          style={{ height: '10px', width: '30%', opacity: 0.6 }}
        />
        <div
          className="rounded-[var(--radius-sm)] bg-[var(--color-surface)]"
          style={{ height: '20px', width: '60%', opacity: 0.6 }}
        />
        <div
          className="rounded-[var(--radius-sm)] bg-[var(--color-surface)]"
          style={{ height: '10px', width: '90%', opacity: 0.4 }}
        />
        <div
          className="rounded-[var(--radius-sm)] bg-[var(--color-surface)]"
          style={{ height: '10px', width: '75%', opacity: 0.4 }}
        />
      </div>
    </div>
  );
}

export function StrategySkeleton() {
  return (
    <div
      style={{
        display: 'grid',
        gap: 'var(--space-6)',
        maxWidth: 'var(--content-width)',
        margin: '0 auto',
        paddingTop: 'var(--space-8)',
      }}
      aria-label="Загрузка стратегии…"
      aria-busy="true"
    >
      {/* Block 1: match highlights placeholder */}
      <SkeletonBlock height="160px" />
      {/* Block 2: gap mitigations placeholder */}
      <SkeletonBlock height="140px" />
      {/* Block 3: cover letter editor placeholder */}
      <SkeletonBlock height="300px" />
    </div>
  );
}
