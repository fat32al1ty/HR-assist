/**
 * TrackSegmentView — Phase 5.1 anchor screen component
 *
 * Visual reference for the 3-track vacancy segmentation layout.
 * This file is the DESIGN REFERENCE — frontend-impl wires real state,
 * API data, and interaction handlers against this anatomy.
 *
 * DO NOT add business logic, API calls, or state management here.
 * All data is passed as props; all interaction callbacks are no-ops
 * in this reference version.
 */

'use client';

import * as React from 'react';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';

/* ── Prop types ──────────────────────────────────────────────────────────── */

/** Mirror of the API VacancyMatch shape. Extend when wiring real data. */
export interface VacancyMatchStub {
  vacancy_id: number;
  title: string;
  company: string | null;
  location: string | null;
  similarity_score: number;
  salary_text?: string | null;
}

export type TrackKind = 'match' | 'grow' | 'stretch';

export interface TrackSection {
  kind: TrackKind;
  /** Russian label shown in the section heading */
  label: string;
  /** One-line gap summary from track_gap_analysis */
  gap_summary: string | null;
  vacancies: VacancyMatchStub[];
  /** Only populated for 'stretch' track */
  softer_subset_count?: number;
}

export interface TrackSegmentViewProps {
  tracks: TrackSection[];
  /** Render-prop — renders the full vacancy card for a given stub. When provided,
   *  VacancyCardStub is bypassed and this is used instead. */
  renderCard?: (match: VacancyMatchStub) => React.ReactNode;
  /** Called when the stretch soft-requirements CTA is clicked */
  onShowSofterStretch?: (count: number) => void;
  /** Called when a vacancy card "Откликнуться" is clicked (fallback stub only) */
  onApply?: (vacancyId: number) => void;
  /** Called when a track section is expanded */
  onSectionExpand?: (kind: TrackKind) => void;
  /** Called when a gap pill/summary is clicked */
  onGapClick?: (kind: TrackKind, skill: string) => void;
  /** Called when the stretch softer-subset CTA is clicked */
  onSofterCtaClick?: (count: number) => void;
}

/* ── Track visual config ─────────────────────────────────────────────────── */

const TRACK_CONFIG: Record<
  TrackKind,
  {
    eyebrow: string;
    ruleColor: string;
    surfaceColor: string;
    labelColor: string;
    pillBg: string;
    pillText: string;
  }
> = {
  match: {
    eyebrow: 'Точка',
    ruleColor: 'var(--color-track-match-rule)',
    surfaceColor: 'transparent',
    labelColor: 'var(--color-track-match-label)',
    pillBg: 'var(--color-surface-muted)',
    pillText: 'var(--color-ink-secondary)',
  },
  grow: {
    eyebrow: 'Вырост',
    ruleColor: 'var(--color-track-grow-rule)',
    surfaceColor: 'var(--color-track-grow-surface)',
    labelColor: 'var(--color-track-grow-label)',
    pillBg: 'var(--color-track-grow-surface)',
    pillText: 'var(--color-track-grow-label)',
  },
  stretch: {
    eyebrow: 'Стрейч',
    ruleColor: 'var(--color-track-stretch-rule)',
    surfaceColor: 'var(--color-track-stretch-surface)',
    labelColor: 'var(--color-track-stretch-label)',
    pillBg: 'var(--color-track-stretch-surface)',
    pillText: 'var(--color-track-stretch-label)',
  },
};

/* ── Sub-components ──────────────────────────────────────────────────────── */

function CountPill({
  count,
  bg,
  color,
}: {
  count: number;
  bg: string;
  color: string;
}) {
  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-[var(--radius-full)] font-[var(--font-mono)] text-[length:var(--text-xs)] font-semibold border"
      style={{
        background: bg,
        color,
        borderColor: color,
        borderWidth: '1px',
        opacity: 0.85,
      }}
    >
      {count}
    </span>
  );
}

function GapSummary({ text }: { text: string }) {
  return (
    <p
      className="mt-1.5 text-[length:var(--text-sm)] leading-[var(--leading-snug)] line-clamp-2"
      style={{ color: 'var(--color-ink-muted)', fontStyle: 'italic' }}
      title={text}
    >
      {text}
    </p>
  );
}

function EmptyTrack({ kind }: { kind: TrackKind }) {
  const msgs: Record<TrackKind, string> = {
    match: 'Нет вакансий точного уровня. Попробуйте запустить подбор заново.',
    grow: 'Нет вакансий уровнем выше. Это нормально — приходите после следующего поиска.',
    stretch: 'Пока нет вакансий для амбициозного роста.',
  };
  return (
    <p
      className="text-[length:var(--text-sm)] italic"
      style={{ color: 'var(--color-ink-muted)', padding: '0.75rem 0' }}
    >
      {msgs[kind]}
    </p>
  );
}

/** Minimal vacancy card — anatomy reference. Frontend-impl fills in full card body. */
function VacancyCardStub({
  match,
  onApply,
}: {
  match: VacancyMatchStub;
  onApply?: (id: number) => void;
}) {
  const pct = Math.round(match.similarity_score * 100);

  return (
    <article
      className="bg-[var(--color-surface)] border border-[var(--color-border)] rounded-[var(--radius-lg)] p-4 flex flex-col gap-3 shadow-[var(--shadow-sm)] hover:shadow-[var(--shadow-md)] transition-shadow duration-[var(--duration-fast)]"
      data-vacancy-id={match.vacancy_id}
    >
      {/* Header row */}
      <div className="flex items-start justify-between gap-3 min-w-0">
        <h3 className="min-w-0 flex-1 text-[length:var(--text-xl)] font-[var(--font-display)] font-semibold leading-[var(--leading-tight)] tracking-[-0.025em] text-[color:var(--color-ink)]">
          {match.title}
        </h3>
        {/* Relevance column */}
        <div className="flex flex-col items-end gap-0.5 shrink-0 font-[var(--font-mono)] text-[length:var(--text-sm)]">
          <span className="font-semibold text-[color:var(--color-ink)]">{pct}%</span>
          <span className="text-[length:var(--text-xs)] font-sans font-normal text-[color:var(--color-ink-muted)]">
            релевантность
          </span>
          {match.salary_text ? (
            <span className="text-[color:var(--color-ink-secondary)]">{match.salary_text}</span>
          ) : null}
        </div>
      </div>

      {/* Meta */}
      <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-muted)] m-0">
        {match.company ?? 'Компания не указана'}
        {' · '}
        {match.location ?? 'Локация не указана'}
      </p>

      {/* Actions row */}
      <div className="flex items-center gap-2 mt-auto pt-1">
        <button
          type="button"
          className="primary text-[length:var(--text-sm)] min-h-[36px] px-4 py-1.5 font-semibold"
          onClick={() => onApply?.(match.vacancy_id)}
        >
          Откликнуться
        </button>
      </div>
    </article>
  );
}

/** Stretch soft-requirements CTA */
function StretchSofterCTA({
  count,
  onClick,
}: {
  count: number;
  onClick?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="w-full mt-1 rounded-[var(--radius-lg)] px-5 py-3 text-[length:var(--text-sm)] font-semibold text-left leading-[var(--leading-snug)] transition-colors duration-[var(--duration-fast)]"
      style={{
        background: 'var(--color-track-stretch-cta-bg)',
        border: '1px solid var(--color-track-stretch-cta-border)',
        color: 'var(--color-track-stretch-cta-ink)',
      }}
    >
      Показать {count} {pluralizeVacancy(count)} с мягкими требованиями
      <span
        className="block text-[length:var(--text-xs)] font-normal mt-0.5"
        style={{ opacity: 0.75 }}
      >
        Где работодатель пишет «будет плюсом» вместо «обязательно»
      </span>
    </button>
  );
}

function pluralizeVacancy(n: number): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return 'вакансию';
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return 'вакансии';
  return 'вакансий';
}

/* ── Section header ──────────────────────────────────────────────────────── */

function TrackHeader({
  cfg,
  label,
  count,
  isOpen,
  onToggle,
}: {
  cfg: (typeof TRACK_CONFIG)[TrackKind];
  label: string;
  count: number;
  isOpen: boolean;
  onToggle: () => void;
}) {
  return (
    <CollapsibleTrigger asChild>
      <button
        type="button"
        onClick={onToggle}
        className="group w-full flex items-center justify-between gap-4 py-4 transition-colors duration-[var(--duration-fast)] focus-visible:outline-2"
        style={{ background: 'none', border: 'none', cursor: 'pointer' }}
        aria-expanded={isOpen}
      >
        <span className="flex flex-col items-start gap-1 min-w-0">
          {/* Eyebrow */}
          <span
            className="text-[length:var(--text-xs)] font-bold tracking-[0.1em] uppercase"
            style={{ color: cfg.labelColor }}
          >
            {cfg.eyebrow}
          </span>
          {/* Section name */}
          <span
            className="text-[length:var(--text-2xl)] font-[var(--font-display)] font-semibold tracking-[-0.03em] leading-[var(--leading-tight)] text-[color:var(--color-ink)]"
          >
            {label}
          </span>
        </span>

        {/* Right side: count + chevron */}
        <span className="flex items-center gap-3 shrink-0">
          <CountPill count={count} bg={cfg.pillBg} color={cfg.pillText} />
          <span
            className="text-[color:var(--color-ink-muted)] transition-transform duration-[var(--duration-fast)] group-data-[state=open]:rotate-180"
            aria-hidden="true"
          >
            ▼
          </span>
        </span>
      </button>
    </CollapsibleTrigger>
  );
}

/* ── Track section ───────────────────────────────────────────────────────── */

function TrackSection({
  section,
  defaultOpen,
  renderCard,
  onApply,
  onShowSofterStretch,
  onSectionExpand,
  onSofterCtaClick,
}: {
  section: TrackSection;
  defaultOpen: boolean;
  renderCard?: (match: VacancyMatchStub) => React.ReactNode;
  onApply?: (id: number) => void;
  onShowSofterStretch?: (count: number) => void;
  onSectionExpand?: (kind: TrackKind) => void;
  onSofterCtaClick?: (count: number) => void;
}) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);
  const cfg = TRACK_CONFIG[section.kind];

  function handleToggle() {
    const nextOpen = !isOpen;
    setIsOpen(nextOpen);
    if (nextOpen) {
      onSectionExpand?.(section.kind);
    }
  }

  return (
    <section
      style={{
        borderLeft: `3px solid ${cfg.ruleColor}`,
        paddingLeft: '1.25rem',
        /*
         * Surface tint: applied as a subtle background only when non-transparent.
         * match stays on the page canvas; grow/stretch get a whisper-thin wash.
         */
        background: cfg.surfaceColor !== 'transparent' ? cfg.surfaceColor : undefined,
        borderRadius: cfg.surfaceColor !== 'transparent' ? 'var(--radius-xl)' : undefined,
      }}
    >
      <Collapsible open={isOpen} onOpenChange={setIsOpen}>
        <TrackHeader
          cfg={cfg}
          label={section.label}
          count={section.vacancies.length}
          isOpen={isOpen}
          onToggle={handleToggle}
        />

        {/* Gap summary — always visible, not inside collapsible */}
        {section.gap_summary ? (
          <GapSummary text={section.gap_summary} />
        ) : null}

        <CollapsibleContent className="data-[state=open]:animate-slide-down">
          <div className="flex flex-col gap-3 pt-4 pb-5">
            {section.vacancies.length === 0 ? (
              <EmptyTrack kind={section.kind} />
            ) : (
              section.vacancies.map((v) =>
                renderCard ? (
                  <React.Fragment key={v.vacancy_id}>{renderCard(v)}</React.Fragment>
                ) : (
                  <VacancyCardStub key={v.vacancy_id} match={v} onApply={onApply} />
                )
              )
            )}

            {/* Stretch CTA */}
            {section.kind === 'stretch' &&
              section.softer_subset_count != null &&
              section.softer_subset_count > 0 ? (
              <StretchSofterCTA
                count={section.softer_subset_count}
                onClick={() => {
                  onShowSofterStretch?.(section.softer_subset_count!);
                  onSofterCtaClick?.(section.softer_subset_count!);
                }}
              />
            ) : null}
          </div>
        </CollapsibleContent>
      </Collapsible>
    </section>
  );
}

/* ── Root component ──────────────────────────────────────────────────────── */

/**
 * TrackSegmentView
 *
 * Renders 3 track sections in a single continuous vertical list.
 * `match` section is open by default; `grow` and `stretch` are collapsed.
 *
 * Usage (in page.tsx once wired):
 *   <TrackSegmentView
 *     tracks={[matchTrack, growTrack, stretchTrack]}
 *     onApply={(id) => handleApply(id)}
 *     onShowSofterStretch={(n) => handleSofterStretch(n)}
 *   />
 */
export function TrackSegmentView({
  tracks,
  renderCard,
  onApply,
  onShowSofterStretch,
  onSectionExpand,
  onSofterCtaClick,
}: TrackSegmentViewProps) {
  if (tracks.length === 0) {
    return (
      <p
        className="text-[length:var(--text-sm)] italic"
        style={{ color: 'var(--color-ink-muted)' }}
      >
        После запуска здесь появятся подходящие вакансии.
      </p>
    );
  }

  return (
    /*
     * stagger-children: orchestrated reveal — each section gets a 60ms delay
     * offset from globals.css @layer utilities.
     */
    <div className="flex flex-col gap-6 stagger-children animate-fade-in">
      {tracks.map((section) => (
        <TrackSection
          key={section.kind}
          section={section}
          /* match is the calm default — open. grow and stretch start collapsed. */
          defaultOpen={section.kind === 'match'}
          renderCard={renderCard}
          onApply={onApply}
          onShowSofterStretch={onShowSofterStretch}
          onSectionExpand={onSectionExpand}
          onSofterCtaClick={onSofterCtaClick}
        />
      ))}
    </div>
  );
}

