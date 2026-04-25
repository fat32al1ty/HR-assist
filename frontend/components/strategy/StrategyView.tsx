'use client';

/**
 * StrategyView — Phase 5.2 anchor screen (wired, Phase 5.2.2)
 *
 * Design: refined editorial, warm-ground.
 * Three blocks flow as one continuous vertical read, not three separate pages.
 *
 * Props are typed against the real API shape (VacancyStrategyOut).
 * Loading / skeleton / error handling live in the page shell.
 */

import * as React from 'react';
import { Button } from '@/components/ui/button';
import type { VacancyStrategyOut, MatchHighlight, GapMitigation } from '@/types/strategy';

// ─── Sub-components ───────────────────────────────────────────────────────────

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
        Используется упрощённый режим — стратегия и письмо сформированы по шаблону. Полный режим вернётся завтра.
      </p>
    </div>
  );
}

// ─── Match highlight card ─────────────────────────────────────────────────────

interface HighlightCardProps {
  item: MatchHighlight;
  /** Ordinal position shown as a small numeric label */
  index: number;
  corrected: boolean;
  onCorrect: () => void;
}

function HighlightCard({ item, index, corrected, onCorrect }: HighlightCardProps) {
  return (
    <article
      className="relative flex flex-col gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-sm)]"
      style={{
        borderLeftWidth: '3px',
        borderLeftColor: 'var(--color-strategy-match-rule)',
        opacity: corrected ? 0.45 : 1,
        transition: 'opacity 0.2s ease',
      }}
    >
      {/* Ordinal chip */}
      <span
        aria-hidden="true"
        style={{
          position: 'absolute',
          top: '1.125rem',
          right: '1.125rem',
          fontFamily: 'var(--font-mono)',
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          color: 'var(--color-strategy-match-rule)',
          opacity: 0.7,
          letterSpacing: '0.04em',
        }}
      >
        {String(index + 1).padStart(2, '0')}
      </span>

      {/* Company */}
      <div style={{ display: 'grid', gap: 'var(--space-1)', paddingRight: 'var(--space-8)' }}>
        {item.company && (
          <span
            style={{
              fontFamily: 'var(--font-body)',
              fontSize: 'var(--text-xs)',
              fontWeight: 700,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              color: 'var(--color-ink-muted)',
            }}
          >
            {item.company}
          </span>
        )}
      </div>

      {/* Quote */}
      <blockquote
        style={{
          margin: 0,
          paddingLeft: 'var(--space-3)',
          borderLeft: '2px solid var(--color-strategy-match-rule)',
          fontFamily: 'var(--font-body)',
          fontSize: 'var(--text-base)',
          lineHeight: 'var(--leading-normal)',
          color: 'var(--color-ink-secondary)',
          fontStyle: 'normal',
        }}
      >
        {item.quote}
      </blockquote>

      {/* Correction affordance */}
      {!corrected && (
        <button
          type="button"
          onClick={onCorrect}
          style={{
            alignSelf: 'flex-start',
            background: 'none',
            border: 'none',
            padding: 0,
            fontFamily: 'var(--font-body)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-ink-muted)',
            textDecoration: 'underline',
            textUnderlineOffset: '3px',
            cursor: 'pointer',
            transition: 'color var(--duration-fast) var(--ease-out)',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-ink-secondary)';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-ink-muted)';
          }}
          aria-label="Отметить как неточное"
        >
          у меня этого нет на самом деле
        </button>
      )}
    </article>
  );
}

// ─── Gap mitigation card ──────────────────────────────────────────────────────

interface GapCardProps {
  item: GapMitigation;
  index: number;
  corrected: boolean;
  onCorrect: () => void;
}

function GapCard({ item, index, corrected, onCorrect }: GapCardProps) {
  return (
    <article
      className="flex flex-col gap-3 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-surface)] p-5 shadow-[var(--shadow-sm)]"
      style={{
        borderLeftWidth: '3px',
        borderLeftColor: 'var(--color-strategy-gap-rule)',
        background: 'var(--color-strategy-gap-surface)',
        opacity: corrected ? 0.45 : 1,
        transition: 'opacity 0.2s ease',
      }}
    >
      {/* Requirement label */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 'var(--space-2)' }}>
        <span
          aria-hidden="true"
          style={{
            flexShrink: 0,
            marginTop: '3px',
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            background: 'var(--color-strategy-gap-rule)',
            opacity: 0.7,
          }}
        />
        <span
          style={{
            fontFamily: 'var(--font-body)',
            fontSize: 'var(--text-sm)',
            fontWeight: 700,
            color: 'var(--color-strategy-gap-label)',
            lineHeight: 'var(--leading-snug)',
          }}
        >
          {item.requirement}
        </span>
      </div>

      {/* Mitigation copy */}
      <p
        style={{
          margin: 0,
          fontFamily: 'var(--font-body)',
          fontSize: 'var(--text-base)',
          lineHeight: 'var(--leading-relaxed)',
          color: 'var(--color-ink-secondary)',
        }}
      >
        {item.mitigation_text}
      </p>

      {/* Correction affordance — identical micro-pattern to HighlightCard */}
      {!corrected && (
        <button
          type="button"
          onClick={onCorrect}
          style={{
            alignSelf: 'flex-start',
            background: 'none',
            border: 'none',
            padding: 0,
            fontFamily: 'var(--font-body)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-ink-muted)',
            textDecoration: 'underline',
            textUnderlineOffset: '3px',
            cursor: 'pointer',
            transition: 'color var(--duration-fast) var(--ease-out)',
          }}
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-ink-secondary)';
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-ink-muted)';
          }}
          aria-label="Отметить как неточное"
        >
          у меня этого нет на самом деле
        </button>
      )}

      {/* Corrected state indicator */}
      {corrected && (
        <span
          style={{
            fontFamily: 'var(--font-body)',
            fontSize: 'var(--text-xs)',
            color: 'var(--color-ink-muted)',
          }}
        >
          Отмечено — спасибо за поправку
        </span>
      )}
    </article>
  );
}

// ─── Cover letter editor ──────────────────────────────────────────────────────

const COVER_LETTER_MAX = 1200;

interface CoverLetterEditorProps {
  initialDraft: string;
  onCopy: (text: string) => void;
  onEdit: (text: string) => void;
}

function CoverLetterEditor({ initialDraft, onCopy, onEdit }: CoverLetterEditorProps) {
  const [text, setText] = React.useState(initialDraft);
  const [copied, setCopied] = React.useState(false);
  const remaining = COVER_LETTER_MAX - text.length;
  const isOverLimit = remaining < 0;

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    setText(e.target.value);
    onEdit(e.target.value);
  }

  function handleCopy() {
    onCopy(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <section
      style={{
        display: 'grid',
        gap: 'var(--space-5)',
      }}
      aria-labelledby="cover-letter-heading"
    >
      {/* Section eyebrow + heading */}
      <div style={{ display: 'grid', gap: 'var(--space-2)' }}>
        <span
          className="eyebrow"
          aria-hidden="true"
        >
          Сопроводительное письмо
        </span>
        <h2
          id="cover-letter-heading"
          style={{
            fontFamily: 'var(--font-display)',
            fontSize: 'var(--text-2xl)',
            fontWeight: 600,
            letterSpacing: '-0.03em',
            lineHeight: 'var(--leading-tight)',
            color: 'var(--color-ink)',
            margin: 0,
          }}
        >
          Черновик письма
        </h2>
        <p
          style={{
            margin: 0,
            color: 'var(--color-ink-secondary)',
            fontSize: 'var(--text-sm)',
            lineHeight: 'var(--leading-normal)',
          }}
        >
          Отредактируйте под себя и скопируйте.
          Письмо учитывает пробелы сверху — мягко, не как извинение.
        </p>
      </div>

      {/* Editor surface */}
      <div
        style={{
          position: 'relative',
          borderRadius: 'var(--radius-lg)',
          border: '1px solid var(--color-border)',
          background: 'var(--color-strategy-editor-surface)',
          overflow: 'hidden',
          boxShadow: 'var(--shadow-sm)',
        }}
      >
        <textarea
          id="cover-letter-text"
          value={text}
          onChange={handleChange}
          maxLength={COVER_LETTER_MAX + 50} /* let them type, counter warns */
          rows={12}
          aria-label="Текст сопроводительного письма"
          aria-describedby="cover-letter-counter"
          style={{
            display: 'block',
            width: '100%',
            border: 'none',
            outline: 'none',
            padding: 'var(--space-6)',
            fontFamily: 'var(--font-body)',
            fontSize: 'var(--text-lg)',
            lineHeight: 'var(--leading-relaxed)',
            color: 'var(--color-ink)',
            background: 'transparent',
            resize: 'vertical',
            minHeight: '280px',
          }}
        />

        {/* Ruler at bottom of textarea */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: 'var(--space-3) var(--space-6)',
            borderTop: '1px solid var(--color-border)',
            background: 'var(--color-surface-muted)',
          }}
        >
          <span
            id="cover-letter-counter"
            role="status"
            aria-live="polite"
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-xs)',
              color: isOverLimit ? 'var(--color-danger)' : 'var(--color-ink-muted)',
              fontWeight: isOverLimit ? 700 : 400,
              transition: 'color var(--duration-fast) var(--ease-out)',
            }}
          >
            {isOverLimit
              ? `+${Math.abs(remaining)} символов сверх лимита`
              : `${remaining} символов осталось`}
          </span>
          <span
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 'var(--text-xs)',
              color: 'var(--color-ink-muted)',
            }}
          >
            {text.length} / {COVER_LETTER_MAX}
          </span>
        </div>
      </div>

      {/* CTA row */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 'var(--space-4)',
          flexWrap: 'wrap',
        }}
      >
        <Button
          variant="primary"
          size="lg"
          onClick={handleCopy}
          disabled={isOverLimit}
          aria-label="Скопировать письмо в буфер обмена"
        >
          {copied ? 'Скопировано ✓' : 'Скопировать'}
        </Button>
      </div>
    </section>
  );
}

// ─── Block separator ──────────────────────────────────────────────────────────

function BlockSeparator() {
  return (
    <div
      aria-hidden="true"
      style={{
        height: '1px',
        background: 'linear-gradient(to right, transparent, var(--color-border) 20%, var(--color-border) 80%, transparent)',
        margin: '0',
      }}
    />
  );
}

// ─── Main view ────────────────────────────────────────────────────────────────

export interface StrategyViewProps {
  data: VacancyStrategyOut;
  /**
   * Called when the user clicks "у меня этого нет на самом деле" on any card.
   * Wired to POST /api/recommendation-corrections and telemetry.
   */
  onCorrectionEvent: (kind: 'highlight' | 'gap', index: number) => void;
  /**
   * Called when "Скопировать" is pressed with the final edited text.
   * Wired to clipboard write and telemetry.
   */
  onCopyDraft: (text: string) => void;
  /**
   * Called on first cover-letter textarea edit (debounced by page shell).
   */
  onEditDraft: (text: string) => void;
}

export function StrategyView({
  data,
  onCorrectionEvent,
  onCopyDraft,
  onEditDraft,
}: StrategyViewProps) {
  // Optimistic greyed-out state for corrected cards
  const [correctedHighlights, setCorrectedHighlights] = React.useState<Set<number>>(new Set());
  const [correctedGaps, setCorrectedGaps] = React.useState<Set<number>>(new Set());

  function handleHighlightCorrect(index: number) {
    setCorrectedHighlights((prev) => new Set([...prev, index]));
    onCorrectionEvent('highlight', index);
  }

  function handleGapCorrect(index: number) {
    setCorrectedGaps((prev) => new Set([...prev, index]));
    onCorrectionEvent('gap', index);
  }

  return (
    <main className="main" aria-label="Стратегия отклика">
      <div
        className="stagger-children"
        style={{
          display: 'grid',
          gap: 'var(--space-10)',
          maxWidth: 'var(--content-width)',
          margin: '0 auto',
        }}
      >
        {/* ── Template mode notice ───────────────────────────────────────── */}
        {data.template_mode && (
          <div className="animate-fade-in">
            <TemplateModeNotice />
          </div>
        )}

        {/* ── Page heading ───────────────────────────────────────────────── */}
        <div className="animate-fade-in" style={{ display: 'grid', gap: 'var(--space-2)' }}>
          <span className="eyebrow block">Стратегия отклика</span>
          <h1
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 'clamp(1.75rem, 3.5vw, 2.75rem)',
              fontWeight: 700,
              letterSpacing: '-0.035em',
              lineHeight: 'var(--leading-tight)',
              color: 'var(--color-ink)',
              margin: 0,
            }}
          >
            Стратегия
          </h1>
          <p
            style={{
              marginTop: 'var(--space-2)',
              color: 'var(--color-ink-secondary)',
              fontSize: 'var(--text-base)',
              lineHeight: 'var(--leading-normal)',
            }}
          >
            Три аргумента из вашего опыта, два пробела с формулировкой для письма и готовый черновик.
          </p>
        </div>

        {/* ── Block 1: Match highlights ──────────────────────────────────── */}
        <section className="animate-fade-in" aria-labelledby="highlights-heading">
          <div style={{ display: 'grid', gap: 'var(--space-5)' }}>
            {/* Section label */}
            <div style={{ display: 'grid', gap: 'var(--space-1)' }}>
              <span
                className="eyebrow"
                aria-hidden="true"
                style={{ color: 'var(--color-strategy-match-rule)' }}
              >
                Ваши аргументы
              </span>
              <h2
                id="highlights-heading"
                style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: 'var(--text-2xl)',
                  fontWeight: 600,
                  letterSpacing: '-0.03em',
                  lineHeight: 'var(--leading-tight)',
                  color: 'var(--color-ink)',
                  margin: 0,
                }}
              >
                Что совпадает
              </h2>
              <p
                style={{
                  margin: 0,
                  color: 'var(--color-ink-secondary)',
                  fontSize: 'var(--text-sm)',
                  lineHeight: 'var(--leading-normal)',
                }}
              >
                Топ-3 момента из вашего резюме, которые прямо отвечают требованиям вакансии.
              </p>
            </div>

            {/* Cards */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 300px), 1fr))',
                gap: 'var(--space-4)',
                alignItems: 'start',
              }}
            >
              {data.match_highlights.map((item, i) => (
                <HighlightCard
                  key={`highlight-${i}`}
                  item={item}
                  index={i}
                  corrected={correctedHighlights.has(i)}
                  onCorrect={() => handleHighlightCorrect(i)}
                />
              ))}
            </div>
          </div>
        </section>

        <BlockSeparator />

        {/* ── Block 2: Gap mitigations ───────────────────────────────────── */}
        <section className="animate-fade-in" aria-labelledby="gaps-heading">
          <div style={{ display: 'grid', gap: 'var(--space-5)' }}>
            {/* Section label */}
            <div style={{ display: 'grid', gap: 'var(--space-1)' }}>
              <span
                className="eyebrow"
                aria-hidden="true"
                style={{ color: 'var(--color-strategy-gap-label)' }}
              >
                Пробелы
              </span>
              <h2
                id="gaps-heading"
                style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: 'var(--text-2xl)',
                  fontWeight: 600,
                  letterSpacing: '-0.03em',
                  lineHeight: 'var(--leading-tight)',
                  color: 'var(--color-ink)',
                  margin: 0,
                }}
              >
                Как письмо это обходит
              </h2>
              <p
                style={{
                  margin: 0,
                  color: 'var(--color-ink-secondary)',
                  fontSize: 'var(--text-sm)',
                  lineHeight: 'var(--leading-normal)',
                }}
              >
                Два требования, которых нет в резюме, — и точная фраза, с которой письмо их снимает.
              </p>
            </div>

            {/* Cards */}
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 280px), 1fr))',
                gap: 'var(--space-4)',
                alignItems: 'start',
              }}
            >
              {data.gap_mitigations.map((item, i) => (
                <GapCard
                  key={`gap-${i}`}
                  item={item}
                  index={i}
                  corrected={correctedGaps.has(i)}
                  onCorrect={() => handleGapCorrect(i)}
                />
              ))}
            </div>
          </div>
        </section>

        <BlockSeparator />

        {/* ── Block 3: Cover letter editor ───────────────────────────────── */}
        <div className="animate-fade-in">
          <CoverLetterEditor
            initialDraft={data.cover_letter_draft}
            onCopy={onCopyDraft}
            onEdit={onEditDraft}
          />
        </div>

        {/* Bottom breathing room */}
        <div style={{ height: 'var(--space-16)' }} aria-hidden="true" />
      </div>
    </main>
  );
}

export default StrategyView;
