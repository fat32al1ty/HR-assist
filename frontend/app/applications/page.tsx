'use client';

import { useEffect, useState } from 'react';
import { useSession } from '@/lib/session';
import { apiFetch } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible';
import { cn } from '@/lib/utils';

// ─────────────────────────────────────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────────────────────────────────────
type ApplicationStatus =
  | 'draft'
  | 'applied'
  | 'viewed'
  | 'replied'
  | 'rejected'
  | 'interview'
  | 'offer'
  | 'declined';

type Application = {
  id: number;
  vacancy_id: number | null;
  resume_id: number | null;
  resume_label: string | null;
  status: ApplicationStatus;
  source_url: string;
  vacancy_title: string;
  vacancy_company: string | null;
  notes: string | null;
  cover_letter_text: string | null;
  cover_letter_generated_at: string | null;
  applied_at: string | null;
  last_status_change_at: string;
  created_at: string;
  updated_at: string;
};

type CoverLetterResponse = {
  id: number;
  cover_letter_text: string;
  cover_letter_generated_at: string;
  cached: boolean;
};

// ─────────────────────────────────────────────────────────────────────────────
// Columns
// ─────────────────────────────────────────────────────────────────────────────
type ColumnId = 'applied' | 'replied' | 'interview' | 'rejected';

const COLUMNS: { id: ColumnId; label: string; emptyText: string }[] = [
  { id: 'applied',   label: 'Откликнулся', emptyText: 'Отклики появятся здесь.' },
  { id: 'replied',   label: 'Ответили',    emptyText: 'Сюда попадут ответы работодателя.' },
  { id: 'interview', label: 'Пригласили',  emptyText: 'Приглашения на интервью и офферы.' },
  { id: 'rejected',  label: 'Отказали',    emptyText: 'Здесь будут отказы.' },
];

const UI_STATUSES: { value: ApplicationStatus; label: string }[] = [
  { value: 'applied',   label: 'Откликнулся' },
  { value: 'replied',   label: 'Ответили'    },
  { value: 'interview', label: 'Пригласили'  },
  { value: 'rejected',  label: 'Отказали'    },
];

function columnForStatus(status: ApplicationStatus): ColumnId {
  switch (status) {
    case 'draft': case 'applied': case 'viewed': return 'applied';
    case 'replied':                               return 'replied';
    case 'interview': case 'offer':               return 'interview';
    case 'rejected': case 'declined':             return 'rejected';
  }
}

function uiStatus(status: ApplicationStatus): ApplicationStatus {
  switch (status) {
    case 'draft': case 'viewed': return 'applied';
    case 'offer':                return 'interview';
    case 'declined':             return 'rejected';
    default:                     return status;
  }
}

// ─────────────────────────────────────────────────────────────────────────────
// Date helper
// ─────────────────────────────────────────────────────────────────────────────
function formatFriendlyDate(value: string | null): string {
  if (!value) return '';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '';
  const now = new Date();
  const today     = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const d         = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  if (d.getTime() === today.getTime())     return 'сегодня';
  if (d.getTime() === yesterday.getTime()) return 'вчера';
  return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }).replace(/\.$/, '');
}

// ─────────────────────────────────────────────────────────────────────────────
// Application Card
// ─────────────────────────────────────────────────────────────────────────────
type CardProps = {
  row: Application;
  isBusy: boolean;
  coverLetterOpen: boolean;
  coverLetterDraft: string;
  coverLetterPrompt: string;
  pendingDelete: boolean;
  onStatusChange: (id: number, status: ApplicationStatus) => void;
  onOpenCoverLetter: (id: number) => void;
  onCloseCoverLetter: (id: number) => void;
  onGenerateCoverLetter: (id: number, force: boolean) => void;
  onSaveCoverLetter: (id: number) => void;
  onCopyCoverLetter: (id: number) => void;
  onCoverLetterChange: (id: number, text: string) => void;
  onCoverLetterPromptChange: (id: number, text: string) => void;
  onDeleteRequest: (id: number) => void;
  onDeleteConfirm: (id: number) => void;
  onDeleteCancel: (id: number) => void;
};

function ApplicationCard({
  row,
  isBusy,
  coverLetterOpen,
  coverLetterDraft,
  coverLetterPrompt,
  pendingDelete,
  onStatusChange,
  onOpenCoverLetter,
  onCloseCoverLetter,
  onGenerateCoverLetter,
  onSaveCoverLetter,
  onCopyCoverLetter,
  onCoverLetterChange,
  onCoverLetterPromptChange,
  onDeleteRequest,
  onDeleteConfirm,
  onDeleteCancel,
}: CardProps) {
  const hasLetter = Boolean(row.cover_letter_text);
  const coverLetterChanged = coverLetterDraft.trim() !== (row.cover_letter_text ?? '').trim();

  return (
    <article
      className={cn(
        'rounded-[var(--radius-lg)] border border-[var(--color-border)]',
        'bg-white/70 shadow-[var(--shadow-sm)]',
        'p-4 flex flex-col gap-2.5',
        'transition-opacity duration-[var(--duration-normal)] animate-fade-in'
      )}
    >
      {/* Title row: name + date */}
      <div className="flex items-start justify-between gap-2 min-w-0">
        <div className="flex flex-col gap-0.5 min-w-0 flex-1">
          <span
            className="text-[length:var(--text-base)] font-semibold text-[color:var(--color-ink)] leading-[var(--leading-tight)] tracking-[-0.01em] truncate"
            title={row.vacancy_title || 'Без названия'}
          >
            {row.vacancy_title || 'Без названия'}
          </span>
          <span className="text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)] truncate">
            {row.vacancy_company ?? 'Компания не указана'}
          </span>
        </div>
        <span className="font-[var(--font-mono)] text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)] shrink-0 pt-0.5">
          {formatFriendlyDate(row.last_status_change_at)}
        </span>
      </div>

      {/* Resume badge */}
      {row.resume_label ? (
        <Badge variant="info" className="self-start max-w-full truncate" title={row.resume_label}>
          {row.resume_label}
        </Badge>
      ) : null}

      {/* Status select */}
      <select
        value={uiStatus(row.status)}
        disabled={isBusy}
        aria-label="Изменить статус"
        className={cn(
          'w-full text-[length:var(--text-sm)] font-semibold',
          'border border-[var(--color-border)] rounded-[var(--radius-md)]',
          'bg-[var(--color-surface-muted)] text-[color:var(--color-ink)]',
          'px-3 py-1.5 cursor-pointer',
          'transition-colors duration-[var(--duration-fast)]',
          isBusy && 'opacity-55 cursor-not-allowed'
        )}
        onChange={(e) => onStatusChange(row.id, e.target.value as ApplicationStatus)}
      >
        {UI_STATUSES.map((s) => (
          <option key={s.value} value={s.value}>{s.label}</option>
        ))}
      </select>

      {/* Cover letter — collapsed state: one text action */}
      {!coverLetterOpen ? (
        <div className="flex items-center gap-3 pt-1">
          {hasLetter ? (
            <button
              type="button"
              disabled={isBusy}
              onClick={() => onOpenCoverLetter(row.id)}
              className="text-[length:var(--text-xs)] font-semibold text-[color:var(--color-accent)] hover:opacity-75 transition-opacity disabled:opacity-40"
            >
              Письмо ↓
            </button>
          ) : (
            <button
              type="button"
              disabled={isBusy}
              onClick={() => onGenerateCoverLetter(row.id, false)}
              className="text-[length:var(--text-xs)] font-semibold text-[color:var(--color-accent)] hover:opacity-75 transition-opacity disabled:opacity-40"
            >
              Сгенерировать письмо
            </button>
          )}
          {row.cover_letter_generated_at ? (
            <span className="text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)]">
              {formatFriendlyDate(row.cover_letter_generated_at)}
            </span>
          ) : null}
        </div>
      ) : (
        /* Cover letter — open state */
        <div className="flex flex-col gap-2 pt-1">
          <textarea
            rows={6}
            maxLength={6000}
            value={coverLetterDraft}
            disabled={isBusy}
            className={cn(
              'w-full resize-vertical min-h-[120px]',
              'border border-[var(--color-border)] rounded-[var(--radius-md)]',
              'bg-[var(--color-surface-muted)] text-[color:var(--color-ink)]',
              'text-[length:var(--text-sm)] leading-[var(--leading-normal)]',
              'p-2.5 font-[var(--font-body)]'
            )}
            placeholder="Нажмите «Обновить», чтобы сгенерировать черновик, или введите свой текст."
            onChange={(e) => onCoverLetterChange(row.id, e.target.value)}
          />
          <details className="group">
            <summary className="cursor-pointer text-[length:var(--text-xs)] font-semibold text-[color:var(--color-ink-secondary)] hover:text-[color:var(--color-ink)] transition-colors select-none">
              Уточнение для AI <span className="text-[color:var(--color-ink-muted)] font-normal">(анкета, тон, акценты)</span>
            </summary>
            <textarea
              rows={3}
              maxLength={1500}
              value={coverLetterPrompt}
              disabled={isBusy}
              className={cn(
                'mt-1.5 w-full resize-vertical min-h-[60px]',
                'border border-[var(--color-border)] rounded-[var(--radius-md)]',
                'bg-[var(--color-surface-muted)] text-[color:var(--color-ink)]',
                'text-[length:var(--text-sm)] leading-[var(--leading-normal)]',
                'p-2.5 font-[var(--font-body)]'
              )}
              placeholder="Напр.: ответь на вопросы анкеты — а) откуда узнал о вакансии: LinkedIn, б) готов выйти через 2 недели; добавь, что готов к командировкам."
              onChange={(e) => onCoverLetterPromptChange(row.id, e.target.value)}
            />
            <p className="mt-1 text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)]">
              При нажатии «Обновить» уточнение учтётся в новой версии письма.
            </p>
          </details>
          <div className="flex flex-wrap gap-1.5">
            <Button variant="primary"   size="sm" disabled={isBusy} onClick={() => onGenerateCoverLetter(row.id, true)}>Обновить</Button>
            <Button variant="secondary" size="sm" disabled={isBusy || !coverLetterChanged} onClick={() => onSaveCoverLetter(row.id)}>Сохранить</Button>
            <Button variant="ghost"     size="sm" disabled={isBusy || !coverLetterDraft.trim()} onClick={() => onCopyCoverLetter(row.id)}>Копировать</Button>
            <Button variant="ghost"     size="sm" disabled={isBusy} onClick={() => onCloseCoverLetter(row.id)}>Скрыть</Button>
          </div>
        </div>
      )}

      {/* Footer: vacancy link + delete */}
      <div className="flex items-center justify-between gap-2 pt-1">
        {row.source_url ? (
          <a
            href={row.source_url}
            target="_blank"
            rel="noreferrer"
            className="text-[length:var(--text-xs)] font-semibold text-[color:var(--color-accent)] hover:opacity-75 transition-opacity"
          >
            Вакансия ↗
          </a>
        ) : (
          <span />
        )}

        {pendingDelete ? (
          <div className="flex items-center gap-2">
            <span className="text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)]">Удалить?</span>
            <button type="button" disabled={isBusy} onClick={() => onDeleteConfirm(row.id)}
              className="text-[length:var(--text-xs)] font-semibold text-[color:var(--color-danger)] hover:opacity-75 transition-opacity disabled:opacity-40">
              Да
            </button>
            <button type="button" onClick={() => onDeleteCancel(row.id)}
              className="text-[length:var(--text-xs)] text-[color:var(--color-ink-secondary)] hover:text-[color:var(--color-ink)] transition-colors">
              Нет
            </button>
          </div>
        ) : (
          <button type="button" disabled={isBusy} onClick={() => onDeleteRequest(row.id)}
            className="text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)] hover:text-[color:var(--color-danger)] transition-colors disabled:opacity-40">
            Удалить
          </button>
        )}
      </div>
    </article>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Column header
// ─────────────────────────────────────────────────────────────────────────────
function ColumnHeader({ label, count }: { label: string; count: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="font-[var(--font-display)] text-[length:var(--text-lg)] font-semibold text-[color:var(--color-ink)] tracking-[-0.02em]">
        {label}
      </span>
      <span className={cn(
        'inline-flex items-center justify-center min-w-[20px] h-[20px] px-1',
        'rounded-full text-[10px] font-bold',
        'bg-[var(--color-surface-muted)] text-[color:var(--color-ink-secondary)]',
        'border border-[var(--color-border)]'
      )}>
        {count}
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Page
// ─────────────────────────────────────────────────────────────────────────────
export default function ApplicationsPage() {
  const { token } = useSession();

  const [applications, setApplications] = useState<Application[]>([]);
  const [statusMessage, setStatusMessage] = useState('');
  const [busyIds, setBusyIds] = useState<Record<number, boolean>>({});
  const [coverLetterOpenIds, setCoverLetterOpenIds] = useState<Record<number, boolean>>({});
  const [coverLetterDrafts, setCoverLetterDrafts] = useState<Record<number, string>>({});
  const [coverLetterPrompts, setCoverLetterPrompts] = useState<Record<number, string>>({});
  const [pendingDeleteIds, setPendingDeleteIds] = useState<Record<number, boolean>>({});
  const [mobileOpenCol, setMobileOpenCol] = useState<ColumnId | null>('applied');

  useEffect(() => {
    if (!token) return;
    void loadApplications();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function loadApplications() {
    try {
      const data = await apiFetch<Application[]>('/api/applications', { token });
      setApplications(data);
    } catch (error) {
      setStatusMessage(error instanceof Error ? `Не удалось загрузить отклики: ${error.message}` : 'Не удалось загрузить отклики.');
    }
  }

  function setBusy(id: number, busy: boolean) {
    setBusyIds((prev) => { const next = { ...prev }; if (busy) next[id] = true; else delete next[id]; return next; });
  }

  async function changeApplicationStatus(applicationId: number, nextStatus: ApplicationStatus) {
    const existing = applications.find((r) => r.id === applicationId);
    if (!existing || existing.status === nextStatus) return;
    setBusy(applicationId, true);
    try {
      const updated = await apiFetch<Application>(`/api/applications/${applicationId}`, {
        token, method: 'PATCH', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: nextStatus }),
      });
      setApplications((prev) => prev.map((r) => (r.id === applicationId ? updated : r)));
      setStatusMessage('');
    } catch (error) {
      setStatusMessage(error instanceof Error ? `Не удалось обновить статус: ${error.message}` : 'Не удалось обновить статус.');
    } finally {
      setBusy(applicationId, false);
    }
  }

  function openCoverLetter(applicationId: number) {
    setCoverLetterOpenIds((prev) => ({ ...prev, [applicationId]: true }));
    const row = applications.find((a) => a.id === applicationId);
    if (row && coverLetterDrafts[applicationId] === undefined) {
      setCoverLetterDrafts((prev) => ({ ...prev, [applicationId]: row.cover_letter_text ?? '' }));
    }
  }

  function closeCoverLetter(applicationId: number) {
    setCoverLetterOpenIds((prev) => { const next = { ...prev }; delete next[applicationId]; return next; });
  }

  async function generateCoverLetter(applicationId: number, force: boolean) {
    setBusy(applicationId, true);
    try {
      const promptText = (coverLetterPrompts[applicationId] ?? '').trim();
      const body = promptText ? JSON.stringify({ extra_instructions: promptText }) : undefined;
      const response = await apiFetch<CoverLetterResponse>(
        `/api/applications/${applicationId}/cover-letter${force ? '?force=true' : ''}`,
        {
          token,
          method: 'POST',
          headers: body ? { 'Content-Type': 'application/json' } : undefined,
          body,
        }
      );
      setApplications((prev) => prev.map((r) =>
        r.id === applicationId
          ? { ...r, cover_letter_text: response.cover_letter_text, cover_letter_generated_at: response.cover_letter_generated_at }
          : r
      ));
      setCoverLetterDrafts((prev) => ({ ...prev, [applicationId]: response.cover_letter_text }));
      setCoverLetterOpenIds((prev) => ({ ...prev, [applicationId]: true }));
      setStatusMessage(response.cached
        ? 'Показываем сохранённое письмо (свежая генерация была менее суток назад).'
        : 'Сопроводительное сгенерировано. Проверьте и при необходимости отредактируйте.');
    } catch (error) {
      setStatusMessage(error instanceof Error ? `Не удалось сгенерировать письмо: ${error.message}` : 'Не удалось сгенерировать письмо.');
    } finally {
      setBusy(applicationId, false);
    }
  }

  async function saveCoverLetterEdits(applicationId: number) {
    const draft = coverLetterDrafts[applicationId] ?? '';
    const existing = applications.find((r) => r.id === applicationId);
    if (!existing) return;
    const trimmed = draft.trim();
    if (trimmed === (existing.cover_letter_text ?? '').trim()) return;
    setBusy(applicationId, true);
    try {
      const payload: Record<string, unknown> = trimmed ? { cover_letter_text: trimmed } : { clear_cover_letter: true };
      const updated = await apiFetch<Application>(`/api/applications/${applicationId}`, {
        token, method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
      });
      setApplications((prev) => prev.map((r) => (r.id === applicationId ? updated : r)));
      setCoverLetterDrafts((prev) => ({ ...prev, [applicationId]: updated.cover_letter_text ?? '' }));
      setStatusMessage('Правки сопроводительного сохранены.');
    } catch (error) {
      setStatusMessage(error instanceof Error ? `Не удалось сохранить письмо: ${error.message}` : 'Не удалось сохранить письмо.');
    } finally {
      setBusy(applicationId, false);
    }
  }

  async function copyCoverLetterToClipboard(applicationId: number) {
    const text = coverLetterDrafts[applicationId];
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setStatusMessage('Текст сопроводительного скопирован в буфер.');
    } catch {
      setStatusMessage('Не удалось скопировать. Выделите текст вручную.');
    }
  }

  function requestDelete(applicationId: number) {
    setPendingDeleteIds((prev) => ({ ...prev, [applicationId]: true }));
  }

  function cancelDelete(applicationId: number) {
    setPendingDeleteIds((prev) => { const next = { ...prev }; delete next[applicationId]; return next; });
  }

  async function confirmDelete(applicationId: number) {
    setBusy(applicationId, true);
    setPendingDeleteIds((prev) => { const next = { ...prev }; delete next[applicationId]; return next; });
    try {
      await apiFetch(`/api/applications/${applicationId}`, { token, method: 'DELETE' });
      setApplications((prev) => prev.filter((r) => r.id !== applicationId));
      setStatusMessage('Отклик удалён.');
    } catch (error) {
      setStatusMessage(error instanceof Error ? `Не удалось удалить отклик: ${error.message}` : 'Не удалось удалить отклик.');
      setBusy(applicationId, false);
    }
  }

  if (!token) return null;

  function cardsForColumn(colId: ColumnId): Application[] {
    return applications
      .filter((r) => columnForStatus(r.status) === colId)
      .sort((a, b) => new Date(b.last_status_change_at).getTime() - new Date(a.last_status_change_at).getTime());
  }

  function renderCard(row: Application) {
    return (
      <ApplicationCard
        key={row.id}
        row={row}
        isBusy={Boolean(busyIds[row.id])}
        coverLetterOpen={Boolean(coverLetterOpenIds[row.id])}
        coverLetterDraft={coverLetterDrafts[row.id] ?? row.cover_letter_text ?? ''}
        coverLetterPrompt={coverLetterPrompts[row.id] ?? ''}
        pendingDelete={Boolean(pendingDeleteIds[row.id])}
        onStatusChange={changeApplicationStatus}
        onOpenCoverLetter={openCoverLetter}
        onCloseCoverLetter={closeCoverLetter}
        onGenerateCoverLetter={generateCoverLetter}
        onSaveCoverLetter={saveCoverLetterEdits}
        onCopyCoverLetter={copyCoverLetterToClipboard}
        onCoverLetterChange={(id, text) => setCoverLetterDrafts((prev) => ({ ...prev, [id]: text }))}
        onCoverLetterPromptChange={(id, text) => setCoverLetterPrompts((prev) => ({ ...prev, [id]: text }))}
        onDeleteRequest={requestDelete}
        onDeleteConfirm={confirmDelete}
        onDeleteCancel={cancelDelete}
      />
    );
  }

  function renderColumnBody(colId: ColumnId) {
    const cards = cardsForColumn(colId);
    const col = COLUMNS.find((c) => c.id === colId)!;
    return (
      <div className="flex flex-col gap-2">
        {cards.length === 0 ? (
          <p className="text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)] italic px-1 py-2">{col.emptyText}</p>
        ) : null}
        {cards.map(renderCard)}
      </div>
    );
  }

  return (
    <div className="w-full max-w-[var(--content-width)] mx-auto px-4 py-10 flex flex-col gap-6">
      {/* Title */}
      <div className="flex flex-col gap-1">
        <h1 className="font-[var(--font-display)] text-[length:var(--text-3xl)] font-semibold text-[color:var(--color-ink)] tracking-[-0.03em] leading-[var(--leading-tight)]">
          Мои отклики
        </h1>
        <p className="text-[length:var(--text-sm)] text-[color:var(--color-ink-secondary)]">
          Трекер статусов. Меняй статус через выпадающий список на карточке.
        </p>
      </div>

      {/* Status message */}
      {statusMessage ? (
        <div className={cn(
          'rounded-[var(--radius-md)] px-4 py-3 text-[length:var(--text-sm)]',
          'bg-[var(--color-warning-subtle)] text-[color:var(--color-warning)]',
          'border border-[color-mix(in_srgb,var(--color-warning)_25%,transparent)]'
        )}>
          {statusMessage}
        </div>
      ) : null}

      {/* Desktop: 4 columns (≥1080px) or 2 columns (640–1079px) */}
      <div className="hidden min-[640px]:grid min-[640px]:grid-cols-2 min-[1080px]:grid-cols-4 gap-5 items-start stagger-children">
        {COLUMNS.map((col) => (
          <div key={col.id} className="flex flex-col gap-2 animate-fade-in">
            <div className="sticky top-0 z-10 pb-2 border-b border-[var(--color-border)]">
              <ColumnHeader label={col.label} count={cardsForColumn(col.id).length} />
            </div>
            <div className="flex flex-col gap-2 pt-1">
              {renderColumnBody(col.id)}
            </div>
          </div>
        ))}
      </div>

      {/* Mobile: accordions (<640px) */}
      <div className="flex flex-col gap-2 min-[640px]:hidden stagger-children">
        {COLUMNS.map((col) => {
          const isOpen = mobileOpenCol === col.id;
          return (
            <Collapsible
              key={col.id}
              open={isOpen}
              onOpenChange={(open) => setMobileOpenCol(open ? col.id : null)}
              className="animate-fade-in"
            >
              <CollapsibleTrigger className={cn(
                'w-full flex items-center justify-between',
                'border border-[var(--color-border)] rounded-[var(--radius-lg)] px-4 py-2.5',
                'cursor-pointer transition-colors duration-[var(--duration-fast)]',
                'hover:bg-[var(--color-surface-muted)]',
                isOpen && 'border-[var(--color-border-strong)]'
              )}>
                <ColumnHeader label={col.label} count={cardsForColumn(col.id).length} />
                <svg
                  className={cn('h-4 w-4 text-[color:var(--color-ink-muted)] transition-transform duration-[var(--duration-fast)]', isOpen && 'rotate-180')}
                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </CollapsibleTrigger>
              <CollapsibleContent className="data-[state=open]:animate-slide-down data-[state=closed]:animate-slide-up pt-2">
                {renderColumnBody(col.id)}
              </CollapsibleContent>
            </Collapsible>
          );
        })}
      </div>
    </div>
  );
}
