'use client';

import type { RequirementsCheck, RequirementItem, RequirementCheckStatus } from '@/types/requirementsCheck';

type Section = 'must_have' | 'nice_to_have';

export type ToggleHandler = (
  section: Section,
  text: string,
  currentStatus: RequirementCheckStatus
) => void | Promise<void>;

const STATUS_ICON: Record<RequirementCheckStatus, string> = {
  ok: '✓',
  partial: '⚠',
  missing: '✗',
  unknown: '?',
};

const STATUS_SR: Record<RequirementCheckStatus, string> = {
  ok: 'соответствует',
  partial: 'частично',
  missing: 'нет',
  unknown: 'неоднозначно',
};

const STATUS_COLOR_VAR: Record<RequirementCheckStatus, string> = {
  ok: 'var(--color-success)',
  partial: 'var(--color-warning)',
  missing: 'var(--color-danger)',
  unknown: 'var(--color-ink-muted)',
};


type ChipItemProps = {
  text: string;
  status: RequirementCheckStatus;
  userOverridden?: boolean;
  onClick?: () => void;
  tooltip?: string;
};

function ChipItem({ text, status, userOverridden, onClick, tooltip }: ChipItemProps) {
  const interactive = typeof onClick === 'function';
  const chipContent = (
    <>
      <span
        aria-hidden="true"
        style={{ color: STATUS_COLOR_VAR[status] }}
        className="shrink-0 font-bold leading-none"
      >
        {STATUS_ICON[status]}
      </span>
      <span className="sr-only">{STATUS_SR[status]}</span>
      <span className="truncate">{text}</span>
      {userOverridden ? (
        <span
          aria-label="ручная отметка"
          title="ручная отметка"
          className="shrink-0 text-[color:var(--color-ink-muted)]"
        >
          ●
        </span>
      ) : null}
    </>
  );

  const baseClass =
    'inline-flex items-center gap-1 py-1 px-2.5 rounded-full text-[length:var(--text-sm)] font-medium ' +
    'text-[color:var(--color-ink-secondary)] border border-[var(--color-border)] ' +
    'bg-[var(--color-surface)] ' +
    'transition-all duration-[var(--duration-fast)] max-w-full';

  const hoverClass =
    'hover:bg-[var(--color-surface-muted)] hover:border-[color-mix(in_srgb,var(--color-ink)_30%,transparent)] ' +
    'hover:shadow-[var(--shadow-xs)] focus-visible:border-[var(--color-accent)] ' +
    'focus-visible:bg-[var(--color-surface-muted)] focus-visible:outline-none';

  if (interactive) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`${baseClass} ${hoverClass} cursor-pointer`}
        aria-label={`Переключить статус: ${text}`}
        title={tooltip ?? 'Кликните, чтобы переключить ✓ ↔ ✗'}
      >
        {chipContent}
      </button>
    );
  }

  return (
    <span
      className={baseClass}
      title={tooltip ?? undefined}
    >
      {chipContent}
    </span>
  );
}

// ── Section ───────────────────────────────────────────────────────────────────

type SectionItemProps = {
  text: string;
  status: RequirementCheckStatus;
  evidence?: string | null;
  userOverridden?: boolean;
  onClick?: () => void;
};

type SectionProps = {
  title: string;
  items: SectionItemProps[];
};

function Section({ title, items }: SectionProps) {
  if (items.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <p className="m-0 text-[length:var(--text-xs)] font-medium text-[color:var(--color-ink-muted)] uppercase tracking-wide">
        {title}
      </p>

      {/* Chip row — flex-wrap, all items always visible */}
      <div className="flex flex-wrap gap-1.5">
        {items.map((item, i) => (
          <ChipItem
            key={i}
            text={item.text}
            status={item.status}
            userOverridden={item.userOverridden}
            onClick={item.onClick}
          />
        ))}
      </div>
    </div>
  );
}

// ── Root component ─────────────────────────────────────────────────────────────

type Props = {
  data: RequirementsCheck;
  onToggle?: ToggleHandler;
};

export default function RequirementsChecklist({ data, onToggle }: Props) {
  const handleClick = (section: Section, text: string, status: RequirementCheckStatus) =>
    onToggle ? () => onToggle(section, text, status) : undefined;

  const experienceItem: SectionItemProps | null = data.experience
    ? {
        text: `Опыт работы — нужно ${data.experience.required_years} лет${
          data.experience.candidate_years != null
            ? `, у вас ${data.experience.candidate_years}`
            : ''
        }`,
        status: data.experience.status,
      }
    : null;

  const mustHaveItems: SectionItemProps[] = [
    ...(experienceItem ? [experienceItem] : []),
    ...data.must_have.map((item: RequirementItem) => ({
      text: item.text,
      status: item.status,
      evidence: item.evidence,
      userOverridden: item.user_overridden ?? false,
      onClick: handleClick('must_have', item.text, item.status),
    })),
  ];

  const niceToHaveItems: SectionItemProps[] = data.nice_to_have.map((item: RequirementItem) => ({
    text: item.text,
    status: item.status,
    evidence: item.evidence,
    userOverridden: item.user_overridden ?? false,
    onClick: handleClick('nice_to_have', item.text, item.status),
  }));

  if (mustHaveItems.length === 0 && niceToHaveItems.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-3">
      <Section title="Обязательные требования" items={mustHaveItems} />
      <Section title="Желательные" items={niceToHaveItems} />
    </div>
  );
}
