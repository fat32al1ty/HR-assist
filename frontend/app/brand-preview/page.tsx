'use client';

import type React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import LogoConcepts from '@/components/brand/LogoConcepts';

const BRAND_ASSETS = {
  icon32: '/brand-preview-assets/aijobmatch-variant2-icon-32.png',
  icon64: '/brand-preview-assets/aijobmatch-variant2-icon-64.png',
  icon128: '/brand-preview-assets/aijobmatch-variant2-icon-128.png',
  icon256: '/brand-preview-assets/aijobmatch-variant2-icon-256.png',
  icon512: '/brand-preview-assets/aijobmatch-variant2-icon-512.png',
  logo320: '/brand-preview-assets/aijobmatch-variant2-logo-320w.png',
  logo640: '/brand-preview-assets/aijobmatch-variant2-logo-640w.png',
  logo1280: '/brand-preview-assets/aijobmatch-variant2-logo-1280w.png',
  logoTransparent: '/brand-preview-assets/aijobmatch-variant2-logo-transparent.png',
  favicon: '/brand-preview-assets/aijobmatch-variant2-favicon.ico',
} as const;

const HERO_POINTS: ReadonlyArray<readonly [string, string]> = [
  [
    'Релевантный подбор вместо шума',
    'AI учитывает стек, опыт, домен и контекст резюме, чтобы не показывать нерелевантные роли.',
  ],
  [
    'Прозрачный fit/gap-анализ',
    'По каждой вакансии видно: что совпало, где пробелы и насколько реалистичен следующий шаг.',
  ],
  [
    'Сопровождение всей воронки',
    'Отклики, AI cover letter и статусы в одной рабочей панели без ручных таблиц.',
  ],
  [
    'Качество растет с каждым циклом',
    'Feedback loop учитывает отклики, отказы и действия кандидата для следующего ранжирования.',
  ],
];

const LOGO_RULES = [
  'Primary логотип: aijobmatch-variant2-logo-1280w.png.',
  'Иконка продукта: aijobmatch-variant2-icon-256.png.',
  'Favicon: aijobmatch-variant2-favicon.ico.',
  'Для более узких контейнеров можно использовать aijobmatch-variant2-logo-640w.png.',
] as const;

const LANDING_BLOCKS = [
  {
    title: 'Позиционирование',
    body: 'AI-powered карьерный ассистент для соискателя: от анализа профиля до результата в откликах.',
  },
  {
    title: 'Главное обещание',
    body: 'Не просто список вакансий, а подбор с оценкой шансов и объяснимой логикой.',
  },
  {
    title: 'Ключевая ценность',
    body: 'Соискатель понимает, куда стоит откликаться сейчас, а что лучше усилить в профиле.',
  },
] as const;

function LogoStrip() {
  return (
    <div className="flex items-center gap-3">
      <Image
        src={BRAND_ASSETS.icon64}
        alt="AIJobMatch icon"
        width={40}
        height={40}
        className="rounded-[10px] shadow-[var(--shadow-sm)]"
      />
      <div className="flex flex-col">
        <span className="text-[length:var(--text-xl)] font-bold leading-none text-[color:var(--color-ink)]">
          <span className="text-[color:var(--color-accent)]">AI</span> JobMatch
        </span>
        <span className="text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)]">aijobmatch.ru</span>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────
   Pills Demo — static reference for frontend-impl.
   All states rendered at once, no real state/API.
   ───────────────────────────────────────────────────────────────────────── */

/** Single chip in "auto" variant (system-detected value). */
function AutoPill({ label, removing = false }: { label: string; removing?: boolean }) {
  return (
    <span
      className={removing ? 'animate-pill-out' : 'animate-pill-in'}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        height: 28,
        padding: '0 10px 0 12px',
        borderRadius: 'var(--radius-full)',
        background: 'var(--color-pill-auto-bg)',
        color: 'var(--color-pill-auto-fg)',
        border: '1px solid var(--color-pill-auto-border)',
        fontSize: 'var(--text-sm)',
        fontWeight: 400,
        lineHeight: 1,
        whiteSpace: 'nowrap' as const,
        cursor: 'default',
        userSelect: 'none' as const,
      }}
    >
      {label}
      <button
        type="button"
        aria-label={`Удалить ${label}`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 16,
          height: 16,
          borderRadius: '50%',
          border: 'none',
          background: 'transparent',
          cursor: 'pointer',
          padding: 0,
          color: 'var(--color-pill-remove-icon)',
          fontSize: 14,
          lineHeight: 1,
          transition: 'color var(--duration-fast) var(--ease-out)',
          flexShrink: 0,
        }}
        onMouseEnter={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-pill-remove-icon-hover)'; }}
        onMouseLeave={(e) => { (e.currentTarget as HTMLButtonElement).style.color = 'var(--color-pill-remove-icon)'; }}
      >
        ×
      </button>
    </span>
  );
}

/** Single chip in "pinned" variant (user-confirmed value, primary fill). */
function PinnedPill({ label }: { label: string }) {
  return (
    <span
      className="animate-pill-in"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: 4,
        height: 28,
        padding: '0 10px 0 12px',
        borderRadius: 'var(--radius-full)',
        background: 'var(--color-pill-pinned-bg)',
        color: 'var(--color-pill-pinned-fg)',
        border: '1px solid var(--color-pill-pinned-border)',
        fontSize: 'var(--text-sm)',
        fontWeight: 600,
        lineHeight: 1,
        whiteSpace: 'nowrap' as const,
        cursor: 'default',
        userSelect: 'none' as const,
      }}
    >
      {label}
      <button
        type="button"
        aria-label={`Удалить ${label}`}
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 16,
          height: 16,
          borderRadius: '50%',
          border: 'none',
          background: 'rgba(255,255,255,0.18)',
          cursor: 'pointer',
          padding: 0,
          color: 'rgba(255,255,255,0.70)',
          fontSize: 14,
          lineHeight: 1,
          transition: 'background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out)',
          flexShrink: 0,
        }}
        onMouseEnter={(e) => {
          const b = e.currentTarget as HTMLButtonElement;
          b.style.background = 'rgba(255,255,255,0.35)';
          b.style.color = '#fff';
        }}
        onMouseLeave={(e) => {
          const b = e.currentTarget as HTMLButtonElement;
          b.style.background = 'rgba(255,255,255,0.18)';
          b.style.color = 'rgba(255,255,255,0.70)';
        }}
      >
        ×
      </button>
    </span>
  );
}

/** "+ добавить" affordance — dashed border, click opens combobox. */
function AddPill({ label = '+ добавить' }: { label?: string }) {
  return (
    <button
      type="button"
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        height: 28,
        padding: '0 12px',
        borderRadius: 'var(--radius-full)',
        background: 'transparent',
        color: 'var(--color-pill-add-fg)',
        border: '1.5px dashed var(--color-pill-add-border)',
        fontSize: 'var(--text-sm)',
        fontWeight: 500,
        lineHeight: 1,
        cursor: 'pointer',
        userSelect: 'none' as const,
        whiteSpace: 'nowrap' as const,
        transition: 'border-color var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out)',
      }}
      onMouseEnter={(e) => {
        const b = e.currentTarget as HTMLButtonElement;
        b.style.borderColor = 'var(--color-accent)';
        b.style.color = 'var(--color-accent)';
      }}
      onMouseLeave={(e) => {
        const b = e.currentTarget as HTMLButtonElement;
        b.style.borderColor = 'var(--color-pill-add-border)';
        b.style.color = 'var(--color-pill-add-fg)';
      }}
    >
      {label}
    </button>
  );
}

/** Combobox dropdown — open state with 5 suggestions (static mock). */
function ComboboxOpen() {
  const suggestions = [
    { value: 'Product Manager', popular: true },
    { value: 'Project Manager', popular: false },
    { value: 'Product Owner', popular: true },
    { value: 'Scrum Master', popular: false },
    { value: 'Product Analyst', popular: false },
  ] as const;

  return (
    <div style={{ position: 'relative', width: 260 }}>
      {/* Input */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          height: 36,
          padding: '0 12px',
          borderRadius: 'var(--radius-md)',
          border: '1.5px solid var(--color-accent)',
          background: 'var(--color-combobox-suggestion-bg)',
          boxShadow: 'var(--shadow-focus)',
          gap: 8,
        }}
      >
        <span style={{ fontSize: 'var(--text-sm)', color: 'var(--color-ink)', flex: 1 }}>
          Product Ma<span style={{ opacity: 0.45 }}>|</span>
        </span>
        <button
          type="button"
          aria-label="Закрыть"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--color-ink-muted)',
            fontSize: 16,
            lineHeight: 1,
            padding: 0,
          }}
        >
          ×
        </button>
      </div>

      {/* Dropdown */}
      <div
        role="listbox"
        aria-label="Варианты ролей"
        style={{
          position: 'absolute',
          top: 40,
          left: 0,
          right: 0,
          background: 'var(--color-combobox-suggestion-bg)',
          border: '1px solid var(--color-combobox-border)',
          borderRadius: 'var(--radius-md)',
          boxShadow: 'var(--color-combobox-shadow)',
          overflow: 'hidden',
          zIndex: 'var(--z-overlay)',
        }}
      >
        {suggestions.map((s, i) => (
          <div
            key={s.value}
            role="option"
            aria-selected={i === 0}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              height: 32,
              padding: '0 12px',
              fontSize: 'var(--text-sm)',
              color: 'var(--color-ink)',
              background: i === 0 ? 'var(--color-combobox-suggestion-bg-hover)' : 'transparent',
              cursor: 'pointer',
              gap: 8,
            }}
          >
            <span>{s.value}</span>
            {s.popular ? (
              <span
                style={{
                  fontSize: 11,
                  fontWeight: 600,
                  color: 'var(--color-pill-popular-fg)',
                  background: 'var(--color-pill-popular-bg)',
                  padding: '1px 6px',
                  borderRadius: 'var(--radius-full)',
                  letterSpacing: '0.02em',
                  flexShrink: 0,
                }}
              >
                · часто
              </span>
            ) : null}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Unsaved indicator dot — appears when pills were changed but not saved. */
function UnsavedDot() {
  return (
    <span
      aria-label="Несохранённые изменения"
      title="Несохранённые изменения"
      style={{
        display: 'inline-block',
        width: 7,
        height: 7,
        borderRadius: '50%',
        background: 'var(--color-unsaved-indicator-fg)',
        flexShrink: 0,
        marginLeft: 4,
      }}
    />
  );
}

/** Group label row with optional unsaved dot. */
function GroupLabel({ children, unsaved = false }: { children: React.ReactNode; unsaved?: boolean }) {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        marginBottom: 8,
      }}
    >
      <span
        style={{
          fontSize: 'var(--text-xs)',
          fontWeight: 700,
          letterSpacing: '0.08em',
          textTransform: 'uppercase' as const,
          color: 'var(--color-ink-muted)',
        }}
      >
        {children}
      </span>
      {unsaved && <UnsavedDot />}
    </div>
  );
}

/** State label used to annotate each pill in the reference grid. */
function StateTag({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        fontSize: 10,
        fontWeight: 700,
        letterSpacing: '0.07em',
        textTransform: 'uppercase' as const,
        color: 'var(--color-ink-muted)',
        padding: '2px 6px',
        background: 'var(--color-surface-muted)',
        borderRadius: 'var(--radius-sm)',
        border: '1px solid var(--color-border)',
        userSelect: 'none' as const,
      }}
    >
      {children}
    </span>
  );
}

/** The full static pills demo section. */
function PillsDemo() {
  return (
    <div
      style={{
        marginTop: 32,
        borderRadius: 'var(--radius-lg)',
        border: '1px solid var(--color-border)',
        background: 'white',
        overflow: 'hidden',
      }}
    >
      {/* Section header */}
      <div
        style={{
          padding: '20px 24px',
          borderBottom: '1px solid var(--color-border)',
          background: 'linear-gradient(135deg,#f0f7ff 0%,#f8fafc 100%)',
          display: 'flex',
          alignItems: 'baseline',
          gap: 12,
          flexWrap: 'wrap' as const,
        }}
      >
        <h2
          style={{
            fontSize: 'var(--text-2xl)',
            fontWeight: 700,
            letterSpacing: '-0.02em',
            color: 'var(--color-ink)',
            margin: 0,
          }}
        >
          Pills demo — все состояния
        </h2>
        <span
          style={{
            fontSize: 'var(--text-xs)',
            fontWeight: 700,
            letterSpacing: '0.08em',
            textTransform: 'uppercase' as const,
            color: 'var(--color-accent)',
            border: '1px solid var(--color-accent)',
            borderRadius: 'var(--radius-full)',
            padding: '2px 10px',
            opacity: 0.75,
          }}
        >
          reference
        </span>
      </div>

      <div style={{ padding: '28px 24px', display: 'grid', gap: 36 }}>

        {/* ── Row 1: Individual state catalogue ──────────────────────────── */}
        <div>
          <h3
            style={{
              fontSize: 'var(--text-base)',
              fontWeight: 700,
              color: 'var(--color-ink)',
              margin: '0 0 16px',
              letterSpacing: '-0.01em',
            }}
          >
            Все состояния — шпаргалка
          </h3>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap' as const,
              gap: 12,
              alignItems: 'center',
            }}
          >
            {/* auto pill — resting */}
            <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 6, alignItems: 'flex-start' }}>
              <StateTag>auto · rest</StateTag>
              <AutoPill label="Data Engineer" />
            </div>

            {/* auto pill — hover (simulated via outline) */}
            <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 6, alignItems: 'flex-start' }}>
              <StateTag>auto · hover</StateTag>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  height: 28,
                  padding: '0 10px 0 12px',
                  borderRadius: 'var(--radius-full)',
                  background: 'var(--color-pill-auto-bg)',
                  color: 'var(--color-pill-auto-fg)',
                  border: '1px solid var(--color-pill-auto-border)',
                  fontSize: 'var(--text-sm)',
                  boxShadow: 'var(--shadow-sm)',
                }}
              >
                Data Engineer
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 16,
                    height: 16,
                    borderRadius: '50%',
                    fontSize: 14,
                    color: 'var(--color-pill-remove-icon-hover)',
                  }}
                >
                  ×
                </span>
              </span>
            </div>

            {/* pinned pill — resting */}
            <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 6, alignItems: 'flex-start' }}>
              <StateTag>pinned · rest</StateTag>
              <PinnedPill label="Backend Developer" />
            </div>

            {/* pinned pill — hover (simulated) */}
            <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 6, alignItems: 'flex-start' }}>
              <StateTag>pinned · hover</StateTag>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  height: 28,
                  padding: '0 10px 0 12px',
                  borderRadius: 'var(--radius-full)',
                  background: 'var(--color-pill-pinned-bg)',
                  color: 'var(--color-pill-pinned-fg)',
                  border: '1px solid var(--color-pill-pinned-border)',
                  fontSize: 'var(--text-sm)',
                  fontWeight: 600,
                  boxShadow: 'var(--shadow-sm)',
                }}
              >
                Backend Developer
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: 16,
                    height: 16,
                    borderRadius: '50%',
                    fontSize: 14,
                    background: 'rgba(255,255,255,0.35)',
                    color: '#fff',
                  }}
                >
                  ×
                </span>
              </span>
            </div>

            {/* focus-visible (simulated via outline) */}
            <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 6, alignItems: 'flex-start' }}>
              <StateTag>focus-visible</StateTag>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  height: 28,
                  padding: '0 10px 0 12px',
                  borderRadius: 'var(--radius-full)',
                  background: 'var(--color-pill-pinned-bg)',
                  color: 'var(--color-pill-pinned-fg)',
                  border: '1px solid var(--color-pill-pinned-border)',
                  fontSize: 'var(--text-sm)',
                  fontWeight: 600,
                  outline: '2px solid var(--color-focus-ring)',
                  outlineOffset: 3,
                }}
              >
                Tech Lead
              </span>
            </div>

            {/* add pill */}
            <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 6, alignItems: 'flex-start' }}>
              <StateTag>add pill</StateTag>
              <AddPill />
            </div>

            {/* removing animation */}
            <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 6, alignItems: 'flex-start' }}>
              <StateTag>removing</StateTag>
              <AutoPill label="DevOps" removing />
            </div>

            {/* disabled / loading */}
            <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 6, alignItems: 'flex-start' }}>
              <StateTag>disabled</StateTag>
              <span
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                  height: 28,
                  padding: '0 10px 0 12px',
                  borderRadius: 'var(--radius-full)',
                  background: 'var(--color-pill-pinned-bg)',
                  color: 'var(--color-pill-pinned-fg)',
                  border: '1px solid var(--color-pill-pinned-border)',
                  fontSize: 'var(--text-sm)',
                  fontWeight: 600,
                  opacity: 0.42,
                  pointerEvents: 'none' as const,
                  userSelect: 'none' as const,
                }}
              >
                Backend Developer
                <span style={{ display: 'inline-flex', width: 16, height: 16, alignItems: 'center', justifyContent: 'center', fontSize: 14 }}>×</span>
              </span>
            </div>
          </div>
        </div>

        {/* ── Row 2: Filled group (Роли) ──────────────────────────────────── */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 260px), 1fr))',
            gap: 24,
          }}
        >
          {/* Filled group */}
          <div
            style={{
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border)',
              padding: '16px 18px',
              background: 'var(--color-surface-muted)',
              display: 'flex',
              flexDirection: 'column' as const,
              gap: 0,
            }}
          >
            <GroupLabel unsaved>Роли</GroupLabel>
            <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6, alignItems: 'center' }}>
              <PinnedPill label="Backend Developer" />
              <PinnedPill label="Tech Lead" />
              <AutoPill label="Software Architect" />
              <AutoPill label="Platform Engineer" />
              <AddPill />
            </div>
          </div>

          {/* Filled group — Домены */}
          <div
            style={{
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border)',
              padding: '16px 18px',
              background: 'var(--color-surface-muted)',
              display: 'flex',
              flexDirection: 'column' as const,
              gap: 0,
            }}
          >
            <GroupLabel>Домены</GroupLabel>
            <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6, alignItems: 'center' }}>
              <PinnedPill label="FinTech" />
              <AutoPill label="E-Commerce" />
              <AddPill />
            </div>
          </div>

          {/* Empty group */}
          <div
            style={{
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--color-border)',
              padding: '16px 18px',
              background: 'var(--color-surface-muted)',
              display: 'flex',
              flexDirection: 'column' as const,
              gap: 0,
            }}
          >
            <GroupLabel>Роли — без резюме</GroupLabel>
            <p
              style={{
                margin: 0,
                fontSize: 'var(--text-sm)',
                fontStyle: 'italic',
                color: 'var(--color-ink-muted)',
                lineHeight: 'var(--leading-normal)',
              }}
            >
              Загрузите резюме, чтобы система предложила роли
            </p>
          </div>
        </div>

        {/* ── Row 3: Combobox open ─────────────────────────────────────────── */}
        <div>
          <h3
            style={{
              fontSize: 'var(--text-base)',
              fontWeight: 700,
              color: 'var(--color-ink)',
              margin: '0 0 16px',
              letterSpacing: '-0.01em',
            }}
          >
            Combobox — открытый (со списком подсказок)
          </h3>
          <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 12, alignItems: 'flex-start' }}>
            {/* Mock context: the add pill was clicked, input appeared in-place */}
            <div
              style={{
                borderRadius: 'var(--radius-lg)',
                border: '1px solid var(--color-border)',
                padding: '16px 18px',
                background: 'var(--color-surface-muted)',
                minWidth: 280,
              }}
            >
              <GroupLabel>Роли</GroupLabel>
              <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6, alignItems: 'center' }}>
                <PinnedPill label="Backend Developer" />
                <AutoPill label="Software Architect" />
                {/* Combobox takes the place of the add pill */}
                <ComboboxOpen />
              </div>
            </div>
          </div>
          <p
            style={{
              marginTop: 10,
              fontSize: 'var(--text-xs)',
              color: 'var(--color-ink-muted)',
              fontStyle: 'italic',
            }}
          >
            Keyboard: ↑/↓ навигация, Enter — выбор, Esc — закрыть. Выбранный вариант становится pinned-пиллом.
          </p>
        </div>

        {/* ── Row 4: Unsaved indicator annotation ─────────────────────────── */}
        <div>
          <h3
            style={{
              fontSize: 'var(--text-base)',
              fontWeight: 700,
              color: 'var(--color-ink)',
              margin: '0 0 12px',
              letterSpacing: '-0.01em',
            }}
          >
            Unsaved indicator
          </h3>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 'var(--text-xs)', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase' as const, color: 'var(--color-ink-muted)' }}>
              Роли
            </span>
            <UnsavedDot />
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-ink-muted)', fontStyle: 'italic' }}>
              ← точка исчезает после сохранения
            </span>
          </div>
          <p
            style={{
              marginTop: 6,
              fontSize: 'var(--text-xs)',
              color: 'var(--color-ink-muted)',
              fontStyle: 'italic',
            }}
          >
            Token: <code>--color-unsaved-indicator-fg</code> (= accent red). Рендерится как 7px круг рядом с лейблом группы.
          </p>
        </div>

        {/* ── Row 5: Token reference table ────────────────────────────────── */}
        <div>
          <h3
            style={{
              fontSize: 'var(--text-base)',
              fontWeight: 700,
              color: 'var(--color-ink)',
              margin: '0 0 12px',
              letterSpacing: '-0.01em',
            }}
          >
            Токены — справка
          </h3>
          <div
            style={{
              overflowX: 'auto' as const,
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--color-border)',
            }}
          >
            <table
              style={{
                width: '100%',
                borderCollapse: 'collapse' as const,
                fontSize: 'var(--text-xs)',
                fontFamily: 'var(--font-mono)',
              }}
            >
              <thead>
                <tr style={{ background: 'var(--color-surface-muted)', borderBottom: '1px solid var(--color-border)' }}>
                  <th style={{ textAlign: 'left' as const, padding: '8px 12px', fontWeight: 700, color: 'var(--color-ink)' }}>Токен</th>
                  <th style={{ textAlign: 'left' as const, padding: '8px 12px', fontWeight: 700, color: 'var(--color-ink)' }}>Значение</th>
                  <th style={{ textAlign: 'left' as const, padding: '8px 12px', fontWeight: 700, color: 'var(--color-ink)', minWidth: 200 }}>Роль</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ['--color-pill-auto-bg',              'oklch(0.94 0.008 240)',  'Фон auto-пилла'],
                  ['--color-pill-auto-fg',              'oklch(0.30 0.02 240)',   'Текст auto-пилла (9:1 контраст)'],
                  ['--color-pill-auto-border',          'oklch(0.80 0.018 240)',  '1px обводка auto-пилла'],
                  ['--color-pill-pinned-bg',            'var(--color-accent)',    'Фон pinned-пилла (cardinal red)'],
                  ['--color-pill-pinned-fg',            'var(--color-on-accent)', 'Текст pinned-пилла (white)'],
                  ['--color-pill-pinned-border',        'var(--color-accent)',    'Обводка pinned-пилла'],
                  ['--color-pill-add-border',           'oklch(0.72 0.018 240)',  'Dashed обводка кнопки + добавить'],
                  ['--color-pill-add-fg',               'var(--color-ink-secondary)', 'Текст кнопки + добавить'],
                  ['--color-pill-remove-icon',          'oklch(0.60 0.02 240)',   '× в покое (приглушён)'],
                  ['--color-pill-remove-icon-hover',    'oklch(0.20 0.02 240)',   '× при наведении (контрастный)'],
                  ['--color-combobox-suggestion-bg',    'var(--color-surface-raised)', 'Фон dropdown'],
                  ['--color-combobox-suggestion-bg-hover', 'oklch(0.96 0.012 240)', 'Строка при наведении'],
                  ['--color-combobox-border',           'var(--color-border)',    'Рамка dropdown'],
                  ['--color-pill-popular-bg',           'oklch(0.97 0.025 145)', 'Фон бейджа "· часто"'],
                  ['--color-pill-popular-fg',           'oklch(0.42 0.10 145)',  'Текст бейджа "· часто"'],
                  ['--color-unsaved-indicator-fg',      'var(--color-accent)',   'Точка "несохранено" (accent red)'],
                ].map(([token, value, role]) => (
                  <tr
                    key={token}
                    style={{ borderBottom: '1px solid var(--color-border)' }}
                  >
                    <td style={{ padding: '7px 12px', color: 'var(--color-accent)', fontFamily: 'var(--font-mono)' }}>{token}</td>
                    <td style={{ padding: '7px 12px', color: 'var(--color-ink-secondary)', fontFamily: 'var(--font-mono)' }}>{value}</td>
                    <td style={{ padding: '7px 12px', color: 'var(--color-ink)', fontFamily: 'var(--font-body)', fontWeight: 400 }}>{role}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

      </div>
    </div>
  );
}

export default function BrandPreviewPage() {
  return (
    <main className="page">
      <section className="main">
        <div className="max-w-[1220px] mx-auto px-6 pt-12 pb-16">
          <LogoConcepts />

          <div className="rounded-[28px] border border-[var(--color-border)] bg-[radial-gradient(1200px_520px_at_20%_-5%,rgba(59,130,246,0.14),transparent)] shadow-[var(--shadow-sm)] mt-10">
            <div className="p-8 md:p-10 lg:p-12">
              <span className="inline-flex items-center rounded-full border border-[var(--color-border)] bg-white px-3 py-1 text-[length:var(--text-xs)] font-bold uppercase tracking-[0.08em] text-[color:var(--color-ink-secondary)]">
                Brand preview · draft
              </span>

              <div className="mt-6 grid grid-cols-1 lg:grid-cols-[1.2fr_0.8fr] gap-8 lg:gap-10">
                <div>
                  <LogoStrip />
                  <span className="mt-6 inline-flex rounded-full border border-[var(--color-border)] bg-white px-3 py-1 text-[length:var(--text-xs)] font-bold uppercase tracking-[0.08em] text-[color:var(--color-ink-secondary)]">
                    AI career assistant for job seekers
                  </span>
                  <h1 className="mt-4 max-w-[720px] text-[length:var(--text-display)] leading-[var(--leading-tight)] tracking-[-0.035em] font-bold text-[color:var(--color-ink)]">
                    AI подбирает релевантные вакансии и честно показывает,{' '}
                    <span className="text-[color:var(--color-accent)]">куда реально стоит откликаться</span>
                  </h1>
                  <p className="mt-4 max-w-[700px] text-[length:var(--text-lg)] leading-[var(--leading-relaxed)] text-[color:var(--color-ink-secondary)]">
                    От анализа резюме и рыночного профиля до explainable fit/gap, AI cover letter и управляемой
                    воронки откликов.
                  </p>

                  <ul className="mt-7 grid gap-3 max-w-[760px]">
                    {HERO_POINTS.map(([title, body]) => (
                      <li key={title} className="flex gap-3">
                        <span className="mt-[3px] inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[var(--color-accent-subtle)] text-[color:var(--color-accent)] text-[length:var(--text-xs)] font-bold">
                          ✓
                        </span>
                        <div>
                          <p className="font-semibold text-[length:var(--text-sm)] text-[color:var(--color-ink)]">{title}</p>
                          <p className="text-[length:var(--text-sm)] leading-[var(--leading-snug)] text-[color:var(--color-ink-secondary)]">
                            {body}
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>

                  <div className="mt-7 flex flex-wrap gap-3">
                    <button
                      type="button"
                      disabled
                      className="rounded-[var(--radius-md)] bg-[var(--color-accent)] px-4 py-2.5 text-[color:var(--color-on-accent)] font-semibold opacity-90 cursor-not-allowed"
                    >
                      Загрузить резюме
                    </button>
                    <button
                      type="button"
                      disabled
                      className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-4 py-2.5 text-[color:var(--color-ink-secondary)] font-semibold cursor-not-allowed"
                    >
                      Посмотреть demo flow
                    </button>
                  </div>
                </div>

                <div className="rounded-[24px] border border-[var(--color-border)] bg-white/80 p-6 md:p-7 shadow-[var(--shadow-sm)] self-start">
                  <h2 className="text-[length:var(--text-3xl)] tracking-[-0.02em] font-bold text-[color:var(--color-ink)]">
                    Вход в кабинет
                  </h2>
                  <p className="mt-1 text-[length:var(--text-base)] text-[color:var(--color-ink-secondary)]">
                    Войдите, чтобы получить подбор вакансий под ваш профиль
                  </p>
                  <div className="mt-5 flex flex-col gap-3">
                    <input placeholder="Email" disabled />
                    <input type="password" placeholder="Пароль" disabled />
                    <button
                      type="button"
                      disabled
                      className="rounded-[var(--radius-md)] bg-[var(--color-accent)] px-4 py-2.5 text-[color:var(--color-on-accent)] font-semibold opacity-90 cursor-not-allowed"
                    >
                      Войти
                    </button>
                    <button
                      type="button"
                      disabled
                      className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white px-4 py-2.5 text-[color:var(--color-ink-secondary)] font-semibold cursor-not-allowed"
                    >
                      Нет аккаунта? Зарегистрироваться
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-8 grid grid-cols-1 lg:grid-cols-[1fr_1fr] gap-5">
            <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 p-6 shadow-[var(--shadow-sm)]">
              <h2 className="text-[length:var(--text-2xl)] tracking-[-0.02em] font-bold text-[color:var(--color-ink)]">
                Логотип из вашего site pack
              </h2>
              <p className="mt-2 text-[length:var(--text-sm)] leading-[var(--leading-snug)] text-[color:var(--color-ink-secondary)]">
                Подключен реальный logo pack `variant2` из папки, которую вы прислали.
              </p>

              <div className="mt-5 rounded-[18px] border border-[var(--color-border)] bg-[linear-gradient(135deg,#dbeafe_0%,#eff6ff_40%,#ffffff_100%)] p-6">
                <Image
                  src={BRAND_ASSETS.logo1280}
                  alt="AIJobMatch logo variant2"
                  width={1280}
                  height={384}
                  className="h-auto w-full max-w-[560px]"
                  priority
                />
                <div className="mt-5 flex items-center gap-3">
                  <Image src={BRAND_ASSETS.icon128} alt="AIJobMatch icon 128" width={34} height={34} className="rounded-[8px]" />
                  <Image src={BRAND_ASSETS.icon64} alt="AIJobMatch icon 64" width={22} height={22} className="rounded-[6px]" />
                  <Image src={BRAND_ASSETS.icon32} alt="AIJobMatch icon 32" width={16} height={16} className="rounded-[4px]" />
                </div>
              </div>
            </div>

            <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 p-6 shadow-[var(--shadow-sm)]">
              <h2 className="text-[length:var(--text-2xl)] tracking-[-0.02em] font-bold text-[color:var(--color-ink)]">
                Правила применения
              </h2>
              <ul className="mt-4 space-y-3 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
                {LOGO_RULES.map((item) => (
                  <li key={item} className="flex gap-2">
                    <span className="text-[color:var(--color-accent)]">•</span>
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-5 rounded-[14px] border border-[var(--color-accent)]/35 bg-[var(--color-accent-subtle)] p-4">
                <p className="text-[length:var(--text-sm)] font-semibold text-[color:var(--color-ink)]">
                  Рекомендуем зафиксировать:
                </p>
                <p className="mt-1 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
                  логотип `variant2` + доменный wordmark как единый бренд для `aijobmatch.ru`.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-8 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 p-6 shadow-[var(--shadow-sm)]">
            <h2 className="text-[length:var(--text-2xl)] tracking-[-0.02em] font-bold text-[color:var(--color-ink)]">
              Лендинг: финальная подача
            </h2>
            <div className="mt-5 grid grid-cols-1 md:grid-cols-3 gap-4">
              {LANDING_BLOCKS.map(({ title, body }) => (
                <div
                  key={title}
                  className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white p-5"
                >
                  <h3 className="font-semibold text-[length:var(--text-base)] text-[color:var(--color-ink)]">{title}</h3>
                  <p className="mt-2 text-[length:var(--text-sm)] leading-[var(--leading-snug)] text-[color:var(--color-ink-secondary)]">
                    {body}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="mt-8 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 p-6 shadow-[var(--shadow-sm)]">
            <h2 className="text-[length:var(--text-2xl)] tracking-[-0.02em] font-bold text-[color:var(--color-ink)]">
              Что изменили относительно текущей боевой
            </h2>
            <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="rounded-[var(--radius-md)] border border-[var(--color-border)] bg-white p-5">
                <p className="text-[length:var(--text-xs)] font-bold uppercase tracking-[0.08em] text-[color:var(--color-ink-muted)]">
                  Было
                </p>
                <ul className="mt-3 space-y-2 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
                  <li>HR-консультант как общее позиционирование.</li>
                  <li>Слабая связка бренда с доменом aijobmatch.</li>
                  <li>Меньше акцента на explainability и feedback loop.</li>
                </ul>
              </div>
              <div className="rounded-[var(--radius-md)] border border-[var(--color-accent)]/35 bg-[var(--color-accent-subtle)] p-5">
                <p className="text-[length:var(--text-xs)] font-bold uppercase tracking-[0.08em] text-[color:var(--color-accent)]">
                  Стало
                </p>
                <ul className="mt-3 space-y-2 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
                  <li>AIJobMatch как единый продуктовый бренд.</li>
                  <li>Реальный вариант2-логотип из вашего пака на hero/бренд-блоке.</li>
                  <li>Четкая формула ценности: match + шансы + объяснение + цикл обучения.</li>
                </ul>
              </div>
            </div>
          </div>

          <div className="mt-8">
            <PillsDemo />
          </div>

          <div className="mt-8 mb-2 rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-white/70 p-6 shadow-[var(--shadow-sm)]">
            <h2 className="text-[length:var(--text-xl)] tracking-[-0.02em] font-bold text-[color:var(--color-ink)]">
              Что дальше перед переносом в боевую
            </h2>
            <ol className="mt-4 list-decimal list-inside space-y-2 text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
              <li>Утвердить variant2 как основной логотип бренда.</li>
              <li>Уточнить подпись `HR ASSIST` в wordmark (оставляем или убираем в следующем экспорте).</li>
              <li>Перенести изменения в боевую страницу отдельным шагом.</li>
            </ol>
            <Link
              href="/"
              className="mt-5 inline-flex items-center gap-1 text-[length:var(--text-sm)] font-semibold text-[color:var(--color-accent)] hover:underline"
            >
              ← Вернуться на основной сайт
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
