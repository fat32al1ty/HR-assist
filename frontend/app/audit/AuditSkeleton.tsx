'use client';

import * as React from 'react';

function SkeletonCard({ wide }: { wide?: boolean }) {
  return (
    <div
      className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface)] p-6"
      style={{ minHeight: wide ? '180px' : '220px' }}
      aria-hidden="true"
    >
      {/* Header line */}
      <div
        className="rounded-[var(--radius-sm)] bg-[var(--color-surface-muted)] mb-3"
        style={{ height: '12px', width: '40%' }}
      />
      {/* Title line */}
      <div
        className="rounded-[var(--radius-sm)] bg-[var(--color-surface-muted)] mb-5"
        style={{ height: '22px', width: '70%' }}
      />
      {/* Body lines */}
      <div className="flex flex-col gap-3">
        <div className="rounded-[var(--radius-sm)] bg-[var(--color-surface-muted)]" style={{ height: '10px', width: '100%' }} />
        <div className="rounded-[var(--radius-sm)] bg-[var(--color-surface-muted)]" style={{ height: '10px', width: '85%' }} />
        <div className="rounded-[var(--radius-sm)] bg-[var(--color-surface-muted)]" style={{ height: '10px', width: '60%' }} />
      </div>
    </div>
  );
}

export function AuditSkeleton() {
  return (
    <div
      style={{
        display: 'grid',
        gap: 'var(--space-6)',
        maxWidth: 'var(--content-width)',
        margin: '0 auto',
      }}
      aria-label="Загрузка аудита…"
      aria-busy="true"
    >
      {/* Heading placeholder */}
      <div>
        <div
          className="rounded-[var(--radius-sm)] bg-[var(--color-surface-muted)] mb-3 animate-pulse"
          style={{ height: '14px', width: '120px' }}
          aria-hidden="true"
        />
        <div
          className="rounded-[var(--radius-sm)] bg-[var(--color-surface-muted)] animate-pulse"
          style={{ height: '40px', width: '55%' }}
          aria-hidden="true"
        />
      </div>

      {/* Top row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))',
          gap: 'var(--space-5)',
          alignItems: 'start',
        }}
      >
        <div className="animate-pulse"><SkeletonCard /></div>
        <div className="animate-pulse"><SkeletonCard /></div>
      </div>

      {/* Bottom row */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))',
          gap: 'var(--space-5)',
          alignItems: 'start',
        }}
      >
        <div className="animate-pulse"><SkeletonCard /></div>
        <div className="animate-pulse"><SkeletonCard /></div>
      </div>
    </div>
  );
}
