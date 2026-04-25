'use client';

import * as React from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { RoleReadCard } from '@/components/audit/RoleReadCard';
import { MarketSalaryCard } from '@/components/audit/MarketSalaryCard';
import { SkillGapsCard } from '@/components/audit/SkillGapsCard';
import { ResumeQualityCard } from '@/components/audit/ResumeQualityCard';
import { QuestionsModal } from '@/components/onboarding/QuestionsModal';
import { AuditSkeleton } from './AuditSkeleton';
import { apiFetch, ApiError } from '@/lib/api';
import { useSession } from '@/lib/session';
import { trackEvent } from '@/lib/telemetry';
import type { ResumeAuditOut } from '@/types/audit';

// ─── Banner components ────────────────────────────────────────────────────────

function TemplateModeNotice() {
  return (
    <div
      className="flex items-center gap-2.5 px-4 py-2.5 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-surface-muted)]"
      role="note"
      aria-label="Упрощённый режим"
    >
      <span
        className="shrink-0 w-1.5 h-1.5 rounded-full bg-[var(--color-ink-muted)]"
        aria-hidden="true"
      />
      <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)] m-0">
        Используется упрощённый режим — подбор и анализ работают на правилах. Полный режим вернётся завтра.
      </p>
    </div>
  );
}

interface QuestionsBannerProps {
  count: number;
  onOpen: () => void;
}

function QuestionsBanner({ count, onOpen }: QuestionsBannerProps) {
  function plural(n: number, one: string, few: string, many: string): string {
    const mod10  = n % 10;
    const mod100 = n % 100;
    if (mod10 === 1 && mod100 !== 11) return one;
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
    return many;
  }

  const noun = plural(count, 'момент', 'момента', 'моментов');

  return (
    <div
      className="flex items-center justify-between gap-4 flex-wrap px-4 py-3 rounded-[var(--radius-lg)] border border-[color-mix(in_srgb,var(--color-accent)_25%,transparent)] bg-[var(--color-accent-subtle)]"
      role="status"
    >
      <p className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)] m-0">
        Уточни{' '}
        <span className="font-bold text-[color:var(--color-accent)]">
          {count} {noun}
        </span>
        {' '}— подбор станет точнее
      </p>
      <Button variant="primary" size="sm" onClick={onOpen}>
        Уточнить
      </Button>
    </div>
  );
}

interface ErrorCardProps {
  message: string;
  analysing?: boolean;
  onRetry: () => void;
}

function ErrorCard({ message, analysing, onRetry }: ErrorCardProps) {
  return (
    <div
      className="flex flex-col items-center gap-4 px-6 py-10 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface)] text-center"
      style={{ maxWidth: 'var(--content-width)', margin: '0 auto' }}
    >
      <p className="text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)] m-0">
        {analysing ? 'Резюме ещё анализируется…' : message}
      </p>
      {!analysing && (
        <Button variant="primary" size="sm" onClick={onRetry}>
          Попробовать снова
        </Button>
      )}
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

const AUTO_RETRY_INTERVAL_MS = 3000;
const AUTO_RETRY_TIMEOUT_MS  = 30000;

export default function AuditPage() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const { token }    = useSession();

  const resumeIdRaw = searchParams.get('resume_id');
  const resumeId    = resumeIdRaw ? parseInt(resumeIdRaw, 10) : null;

  const [audit,   setAudit]   = React.useState<ResumeAuditOut | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [error,   setError]   = React.useState<string | null>(null);
  // true while the backend is still computing (422 from /audit)
  const [analysing, setAnalysing] = React.useState(false);
  const [modalOpen, setModalOpen] = React.useState(false);
  // Track whether audit_view telemetry has already been fired this mount
  const auditViewFired = React.useRef(false);

  // Refs for auto-retry teardown
  const retryTimerRef   = React.useRef<ReturnType<typeof setInterval> | null>(null);
  const retryTimeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  function clearRetryTimers() {
    if (retryTimerRef.current !== null) {
      clearInterval(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    if (retryTimeoutRef.current !== null) {
      clearTimeout(retryTimeoutRef.current);
      retryTimeoutRef.current = null;
    }
  }

  // Redirect to / if no resume_id in query
  React.useEffect(() => {
    if (!resumeId || !Number.isFinite(resumeId)) {
      router.replace('/');
    }
  }, [resumeId, router]);

  async function fetchAudit(): Promise<void> {
    if (!resumeId || !Number.isFinite(resumeId)) return;
    try {
      const data = await apiFetch<ResumeAuditOut>(
        `/api/resumes/${resumeId}/audit`,
        { token }
      );
      setAudit(data);
      setAnalysing(false);
      setError(null);
      clearRetryTimers();

      if (!auditViewFired.current) {
        auditViewFired.current = true;
        trackEvent('audit_view', { resume_id: resumeId });
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Ошибка загрузки аудита';
      // 422 means backend hasn't computed the audit yet — auto-retry
      if (err instanceof ApiError && err.status === 422) {
        setAnalysing(true);
        setError(null);
      } else {
        setAnalysing(false);
        setError(message);
      }
    } finally {
      setLoading(false);
    }
  }

  // Initial fetch + auto-retry on 422
  React.useEffect(() => {
    if (!resumeId || !Number.isFinite(resumeId)) return;

    void fetchAudit();

    // auto-retry every 3s for up to 30s if still analysing
    retryTimerRef.current = setInterval(() => {
      // Only retry when still analysing and no data yet
      setAnalysing((cur) => {
        if (cur) void fetchAudit();
        return cur;
      });
    }, AUTO_RETRY_INTERVAL_MS);

    retryTimeoutRef.current = setTimeout(() => {
      clearRetryTimers();
      setAnalysing((cur) => {
        if (cur) {
          setError('Анализ занял слишком много времени. Попробуйте позже.');
        }
        return false;
      });
    }, AUTO_RETRY_TIMEOUT_MS);

    return () => clearRetryTimers();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resumeId, token]);

  function handleRetry() {
    setLoading(true);
    setError(null);
    void fetchAudit();
  }

  function handleModalAnswered() {
    // Refetch audit so triggered_question_ids updates (banner may disappear)
    void fetchAudit();
  }

  // ── Loading state
  if (loading) {
    return (
      <main className="main" aria-label="Аудит резюме">
        <AuditSkeleton />
      </main>
    );
  }

  // ── Error / still-analysing state
  if (error || analysing) {
    return (
      <main className="main" aria-label="Аудит резюме">
        <ErrorCard
          message={error ?? ''}
          analysing={analysing}
          onRetry={handleRetry}
        />
      </main>
    );
  }

  // ── No data (shouldn't normally reach here)
  if (!audit) return null;

  const hasQuestions = audit.triggered_question_ids.length > 0;

  return (
    <>
      <main className="main" aria-label="Аудит резюме">
        <div
          className="stagger-children"
          style={{
            display: 'grid',
            gap: 'var(--space-6)',
            maxWidth: 'var(--content-width)',
            margin: '0 auto',
          }}
        >
          {/* Template mode notice — above everything, neutral */}
          {audit.template_mode_active && (
            <div className="animate-fade-in">
              <TemplateModeNotice />
            </div>
          )}

          {/* Questions banner */}
          {hasQuestions && (
            <div className="animate-fade-in">
              <QuestionsBanner
                count={audit.triggered_question_ids.length}
                onOpen={() => setModalOpen(true)}
              />
            </div>
          )}

          {/* Page heading */}
          <div className="animate-fade-in">
            <span className="eyebrow block mb-2">Аудит резюме</span>
            <h1
              style={{
                fontSize: 'clamp(1.75rem, 3.5vw, 2.75rem)',
                fontWeight: 700,
                letterSpacing: '-0.035em',
                lineHeight: 'var(--leading-tight)',
                color: 'var(--color-ink)',
                margin: 0,
              }}
            >
              {audit.role_read.primary.role_family}
              {' '}
              <span style={{ color: 'var(--color-ink-secondary)', fontWeight: 500 }}>
                · {audit.role_read.primary.seniority}
              </span>
            </h1>
            <p
              style={{
                marginTop: 'var(--space-2)',
                color: 'var(--color-ink-secondary)',
                fontSize: 'var(--text-base)',
                lineHeight: 'var(--leading-normal)',
              }}
            >
              Так рынок читает ваше резюме прямо сейчас. Вот что найдено, что стоит добавить и чего ожидать по деньгам.
            </p>
          </div>

          {/* Top row: Role read + Market salary (side by side on lg) */}
          <div
            className="animate-fade-in"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))',
              gap: 'var(--space-5)',
              alignItems: 'start',
            }}
          >
            <RoleReadCard roleRead={audit.role_read} />
            <MarketSalaryCard salary={audit.market_salary} />
          </div>

          {/* Bottom row: Skill gaps + Resume quality */}
          <div
            className="animate-fade-in"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 340px), 1fr))',
              gap: 'var(--space-5)',
              alignItems: 'start',
            }}
          >
            <SkillGapsCard skillGaps={audit.skill_gaps} />
            <ResumeQualityCard qualityIssues={audit.quality_issues} />
          </div>

          {/* Bottom CTA */}
          <div
            className="animate-fade-in"
            style={{
              display: 'flex',
              justifyContent: 'center',
              paddingTop: 'var(--space-4)',
              paddingBottom: 'var(--space-16)',
            }}
          >
            <Button variant="primary" size="lg" onClick={() => router.push('/')}>
              Подобрать вакансии
            </Button>
          </div>
        </div>
      </main>

      {/* Onboarding modal — portal, non-blocking */}
      {resumeId !== null && (
        <QuestionsModal
          resumeId={resumeId}
          open={modalOpen}
          onOpenChange={setModalOpen}
          onAnswered={handleModalAnswered}
        />
      )}
    </>
  );
}
