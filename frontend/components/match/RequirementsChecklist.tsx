'use client';

import { useState } from 'react';
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

const COLLAPSE_THRESHOLD = 5;

type StatusIconProps = {
  status: RequirementCheckStatus;
};

function StatusIcon({ status }: StatusIconProps) {
  return (
    <span
      aria-hidden="true"
      style={{ color: STATUS_COLOR_VAR[status] }}
      className="shrink-0 font-bold text-[length:var(--text-sm)] w-4 text-center"
    >
      {STATUS_ICON[status]}
    </span>
  );
}

type CheckItemProps = {
  text: string;
  status: RequirementCheckStatus;
  evidence?: string | null;
  userOverridden?: boolean;
  onClick?: () => void;
};

function CheckItem({ text, status, evidence, userOverridden, onClick }: CheckItemProps) {
  const interactive = typeof onClick === 'function';
  const Inner = (
    <>
      <div className="flex items-start gap-2">
        <StatusIcon status={status} />
        <span className="sr-only">{STATUS_SR[status]}</span>
        <span className="text-[color:var(--color-ink-secondary)] text-[length:var(--text-sm)] leading-[var(--leading-snug)]">
          {text}
          {userOverridden ? (
            <span
              aria-label="ручная отметка"
              title="ручная отметка"
              className="ml-1 text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)]"
            >
              ●
            </span>
          ) : null}
        </span>
      </div>
      {evidence ? (
        <p className="ml-6 text-xs text-[color:var(--color-ink-muted)] leading-snug m-0">
          {evidence}
        </p>
      ) : null}
    </>
  );
  if (interactive) {
    return (
      <li className="flex flex-col gap-0.5">
        <button
          type="button"
          onClick={onClick}
          className="text-left cursor-pointer rounded-[var(--radius-md)] -mx-2 px-2 py-1 border border-transparent hover:border-[var(--color-border)] hover:bg-[var(--color-surface-muted)] hover:shadow-[var(--shadow-xs)] focus-visible:border-[var(--color-accent)] focus-visible:bg-[var(--color-surface-muted)] focus-visible:outline-none transition-all duration-[var(--duration-fast)] flex flex-col gap-0.5"
          aria-label={`Переключить статус: ${text}`}
          title="Кликните, чтобы переключить ✓ ↔ ✗"
        >
          {Inner}
        </button>
      </li>
    );
  }
  return <li className="flex flex-col gap-0.5">{Inner}</li>;
}

type SectionProps = {
  title: string;
  items: CheckItemProps[];
};

function Section({ title, items }: SectionProps) {
  const [expanded, setExpanded] = useState(false);

  if (items.length === 0) return null;

  const visible = !expanded && items.length > COLLAPSE_THRESHOLD
    ? items.slice(0, COLLAPSE_THRESHOLD)
    : items;
  const hiddenCount = items.length - COLLAPSE_THRESHOLD;

  return (
    <div className="flex flex-col gap-2">
      <p className="m-0 text-[length:var(--text-xs)] font-medium text-[color:var(--color-ink-muted)] uppercase tracking-wide">
        {title}
      </p>
      <ul className="list-none m-0 p-0 flex flex-col gap-2">
        {visible.map((item, i) => (
          <CheckItem key={i} {...item} />
        ))}
      </ul>
      {!expanded && hiddenCount > 0 ? (
        <button
          type="button"
          onClick={() => setExpanded(true)}
          className="self-start text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)] hover:text-[color:var(--color-ink-secondary)] underline underline-offset-2 transition-colors"
        >
          Показать ещё {hiddenCount}
        </button>
      ) : null}
    </div>
  );
}

type Props = {
  data: RequirementsCheck;
  onToggle?: ToggleHandler;
};

export default function RequirementsChecklist({ data, onToggle }: Props) {
  const handleClick = (section: Section, text: string, status: RequirementCheckStatus) =>
    onToggle ? () => onToggle(section, text, status) : undefined;

  const experienceItem: CheckItemProps | null = data.experience
    ? {
        text: `Опыт работы — нужно ${data.experience.required_years} лет${
          data.experience.candidate_years != null
            ? `, у вас ${data.experience.candidate_years}`
            : ''
        }`,
        status: data.experience.status,
      }
    : null;

  const mustHaveItems: CheckItemProps[] = [
    ...(experienceItem ? [experienceItem] : []),
    ...data.must_have.map((item: RequirementItem) => ({
      text: item.text,
      status: item.status,
      evidence: item.evidence,
      userOverridden: item.user_overridden ?? false,
      onClick: handleClick('must_have', item.text, item.status),
    })),
  ];

  const niceToHaveItems: CheckItemProps[] = data.nice_to_have.map((item: RequirementItem) => ({
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
