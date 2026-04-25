'use client';

/**
 * /strategy — Phase 5.2.2 (wired)
 *
 * State machine:
 *   loading  → StrategySkeleton
 *   401      → redirect to login
 *   404      → "недоступна" message with back button
 *   429      → rate-limit message with Retry-After
 *   200      → <StrategyView />
 *   5xx/net  → error with retry button
 *   no params → redirect to /
 */

import * as React from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { StrategyView } from '@/components/strategy/StrategyView';
import { StrategySkeleton } from './StrategySkeleton';
import { apiFetch, ApiError } from '@/lib/api';
import { useSession } from '@/lib/session';
import { trackEvent } from '@/lib/telemetry';
import { Button } from '@/components/ui/button';
import type { VacancyStrategyOut, RecommendationCorrectionCreate } from '@/types/strategy';

// ─── Clipboard helper ─────────────────────────────────────────────────────────

function copyToClipboard(text: string): void {
  if (typeof navigator !== 'undefined' && navigator.clipboard) {
    void navigator.clipboard.writeText(text).catch(() => {
      copyViaExecCommand(text);
    });
  } else {
    copyViaExecCommand(text);
  }
}

function copyViaExecCommand(text: string): void {
  const el = document.createElement('textarea');
  el.value = text;
  el.style.position = 'fixed';
  el.style.opacity = '0';
  document.body.appendChild(el);
  el.select();
  document.execCommand('copy');
  document.body.removeChild(el);
}

// ─── Error / info message cards ───────────────────────────────────────────────

function MessageCard({
  message,
  onAction,
  actionLabel,
}: {
  message: string;
  onAction?: () => void;
  actionLabel?: string;
}) {
  const router = useRouter();
  return (
    <div
      className="flex flex-col items-center gap-4 px-6 py-10 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface)] text-center"
      style={{ maxWidth: 'var(--content-width)', margin: '0 auto' }}
    >
      <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] m-0">
        {message}
      </p>
      <div className="flex gap-3 flex-wrap justify-center">
        {onAction && actionLabel && (
          <Button variant="primary" size="sm" onClick={onAction}>
            {actionLabel}
          </Button>
        )}
        <Button variant="secondary" size="sm" onClick={() => router.push('/')}>
          На главную
        </Button>
      </div>
    </div>
  );
}

// ─── Inner page (needs Suspense for useSearchParams) ──────────────────────────

type PageStatus =
  | { kind: 'loading' }
  | { kind: 'ok'; data: VacancyStrategyOut }
  | { kind: '404' }
  | { kind: '429'; retryAfterSeconds: number | null }
  | { kind: 'error'; message: string };

function StrategyPageInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { token, clearSession } = useSession();

  const resumeIdRaw = searchParams.get('resume_id');
  const vacancyIdRaw = searchParams.get('vacancy_id');

  const resumeId = resumeIdRaw ? parseInt(resumeIdRaw, 10) : null;
  const vacancyId = vacancyIdRaw ? parseInt(vacancyIdRaw, 10) : null;

  const [status, setStatus] = React.useState<PageStatus>({ kind: 'loading' });

  // Prevent strategy_view from firing more than once per mount
  const strategyViewFired = React.useRef(false);
  // Prevent cover_letter_edited from firing more than once per mount
  const coverLetterEditFired = React.useRef(false);
  // Debounce timer ref for cover letter edits
  const editDebounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  // Redirect if params are invalid
  React.useEffect(() => {
    if (!resumeId || !Number.isFinite(resumeId) || !vacancyId || !Number.isFinite(vacancyId)) {
      router.replace('/');
    }
  }, [resumeId, vacancyId, router]);

  // Fetch strategy from backend
  const fetchStrategy = React.useCallback(async () => {
    if (!resumeId || !Number.isFinite(resumeId) || !vacancyId || !Number.isFinite(vacancyId)) {
      return;
    }
    setStatus({ kind: 'loading' });
    try {
      const data = await apiFetch<VacancyStrategyOut>(
        `/api/resumes/${resumeId}/vacancies/${vacancyId}/strategy`,
        { token }
      );
      setStatus({ kind: 'ok', data });

      // Write sessionStorage key so apply-after-strategy-view can detect it
      try {
        sessionStorage.setItem(`strategy_seen:${resumeId}:${vacancyId}`, '1');
      } catch {
        // sessionStorage may be blocked in private mode — not critical
      }

      // Fire strategy_view once
      if (!strategyViewFired.current) {
        strategyViewFired.current = true;
        trackEvent('strategy_view', { resume_id: resumeId, vacancy_id: vacancyId });
      }
    } catch (err) {
      if (err instanceof ApiError) {
        if (err.status === 401) {
          clearSession('Сессия истекла. Войдите снова.');
          return;
        }
        if (err.status === 404) {
          setStatus({ kind: '404' });
          return;
        }
        if (err.status === 429) {
          // The endpoint sets no Retry-After header on the 2/hour cap, so we
          // surface a generic message instead of issuing a second request just
          // to read a header that won't be there.
          setStatus({ kind: '429', retryAfterSeconds: null });
          return;
        }
      }
      const message =
        err instanceof Error ? err.message : 'Не удалось загрузить стратегию';
      setStatus({ kind: 'error', message });
    }
  }, [resumeId, vacancyId, token, clearSession]);

  React.useEffect(() => {
    void fetchStrategy();
  }, [fetchStrategy]);

  // ── Guard: no valid params
  if (!resumeId || !vacancyId) return null;

  // ── Loading
  if (status.kind === 'loading') {
    return (
      <main className="main" aria-label="Загрузка стратегии…">
        <StrategySkeleton />
      </main>
    );
  }

  // ── 404
  if (status.kind === '404') {
    return (
      <main className="main" aria-label="Стратегия недоступна">
        <MessageCard message="Стратегия для этой вакансии недоступна." />
      </main>
    );
  }

  // ── 429
  if (status.kind === '429') {
    const minutes =
      status.retryAfterSeconds !== null
        ? Math.ceil(status.retryAfterSeconds / 60)
        : null;
    const detail = minutes !== null ? `через ${minutes} мин.` : 'позже';
    return (
      <main className="main" aria-label="Лимит стратегий">
        <MessageCard message={`Лимит стратегий: 2 в час. Попробуйте ${detail}`} />
      </main>
    );
  }

  // ── Generic error
  if (status.kind === 'error') {
    return (
      <main className="main" aria-label="Ошибка загрузки стратегии">
        <MessageCard
          message="Не удалось загрузить стратегию."
          onAction={() => void fetchStrategy()}
          actionLabel="Попробовать снова"
        />
      </main>
    );
  }

  // ── 200 OK
  const { data } = status;

  function handleCorrectionEvent(kind: 'highlight' | 'gap', index: number) {
    const correctionType =
      kind === 'highlight' ? 'match_highlight_invalid' : 'gap_mitigation_invalid';

    const body: RecommendationCorrectionCreate = {
      resume_id: resumeId as number,
      vacancy_id: vacancyId as number,
      correction_type: correctionType,
      subject_index: index,
    };

    void apiFetch('/api/recommendation-corrections', {
      method: 'POST',
      token,
      body: JSON.stringify(body),
    }).catch(() => {
      // best-effort — UI already optimistically greys the card
    });

    const eventName =
      kind === 'highlight'
        ? 'strategy_match_highlight_corrected'
        : 'strategy_gap_mitigation_corrected';
    trackEvent(eventName, {
      resume_id: resumeId as number,
      vacancy_id: vacancyId as number,
      subject_index: index,
    });
  }

  function handleCopyDraft(text: string) {
    copyToClipboard(text);
    trackEvent('cover_letter_copied', {
      resume_id: resumeId as number,
      vacancy_id: vacancyId as number,
      length: text.length,
    });
  }

  function handleEditDraft(text: string) {
    // Debounce 1s, fire on first edit only
    if (editDebounceRef.current !== null) {
      clearTimeout(editDebounceRef.current);
    }
    editDebounceRef.current = setTimeout(() => {
      if (!coverLetterEditFired.current) {
        coverLetterEditFired.current = true;
        trackEvent('cover_letter_edited', {
          resume_id: resumeId as number,
          vacancy_id: vacancyId as number,
          length: text.length,
        });
      }
    }, 1000);
  }

  return (
    <StrategyView
      data={data}
      onCorrectionEvent={handleCorrectionEvent}
      onCopyDraft={handleCopyDraft}
      onEditDraft={handleEditDraft}
    />
  );
}

export default function StrategyPage() {
  return (
    <React.Suspense
      fallback={
        <main className="main" aria-label="Загрузка стратегии…">
          <StrategySkeleton />
        </main>
      }
    >
      <StrategyPageInner />
    </React.Suspense>
  );
}
