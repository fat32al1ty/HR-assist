'use client';

import { useEffect, useState } from 'react';
import { useSession } from '@/lib/session';
import { apiFetch } from '@/lib/api';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Separator } from '@/components/ui/separator';
import { Collapsible, CollapsibleTrigger, CollapsibleContent } from '@/components/ui/collapsible';
import { Textarea } from '@/components/ui/textarea';
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
// Column definitions
// ─────────────────────────────────────────────────────────────────────────────
type ColumnId = 'draft' | 'applied' | 'viewed' | 'interview+offer';

const COLUMNS: { id: ColumnId; label: string; emptyText: string }[] = [
  {
    id: 'draft',
    label: 'Черновик',
    emptyText: "Пусто. Когда найдёшь что-то интересное, нажми «Откликнуться» на карточке вакансии.",
  },
  {
    id: 'applied',
    label: 'Откликнулся',
    emptyText: 'Отклики появятся здесь после отправки.',
  },
  {
    id: 'viewed',
    label: 'Прочитали',
    emptyText: 'Сюда попадают отклики, которые работодатель прочитал.',
  },
  {
    id: 'interview+offer',
    label: 'Собеседование / Оффер',
    emptyText: 'Когда тебя позовут на интервью или дадут оффер — появится здесь.',
  },
];

// Statuses that go into the archive
const ARCHIVED_STATUSES: ApplicationStatus[] = ['rejected', 'declined'];

const STATUS_LABELS: Record<ApplicationStatus, string> = {
  draft: 'Черновик',
  applied: 'Откликнулся',
  viewed: 'Просмотрено',
  replied: 'Получен ответ',
  interview: 'Интервью',
  offer: 'Оффер',
  rejected: 'Отказ',
  declined: 'Отклонил сам',
};

const ALL_STATUS_ORDER: ApplicationStatus[] = [
  'draft',
  'applied',
  'viewed',
  'replied',
  'interview',
  'offer',
  'rejected',
  'declined',
];

function columnForStatus(status: ApplicationStatus): ColumnId {
  switch (status) {
    case 'draft':
      return 'draft';
    case 'applied':
      return 'applied';
    case 'viewed':
    case 'replied':
      return 'viewed';
    case 'interview':
    case 'offer':
      return 'interview+offer';
    default:
      return 'draft';
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
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  if (d.getTime() === today.getTime()) return 'сегодня';
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
  notesDraft: string;
  onStatusChange: (id: number, status: ApplicationStatus) => void;
  onToggleCoverLetter: (id: number) => void;
  onGenerateCoverLetter: (id: number, force: boolean) => void;
  onSaveCoverLetter: (id: number) => void;
  onCopyCoverLetter: (id: number) => void;
  onCoverLetterChange: (id: number, text: string) => void;
  onNotesChange: (id: number, text: string) => void;
  onSaveNotes: (id: number) => void;
};

function ApplicationCard({
  row,
  isBusy,
  coverLetterOpen,
  coverLetterDraft,
  notesDraft,
  onStatusChange,
  onToggleCoverLetter,
  onGenerateCoverLetter,
  onSaveCoverLetter,
  onCopyCoverLetter,
  onCoverLetterChange,
  onNotesChange,
  onSaveNotes,
}: CardProps) {
  const hasLetter = Boolean(row.cover_letter_text);
  const coverLetterChanged = coverLetterDraft.trim() !== (row.cover_letter_text ?? '').trim();
  const hasNotes = Boolean(row.notes);
  const notesChanged = notesDraft.trim() !== (row.notes ?? '').trim();
  const titleTruncated =
    row.vacancy_title.length > 60 ? row.vacancy_title.slice(0, 57) + '…' : row.vacancy_title;

  return (
    <article
      className={cn(
        'bg-[var(--color-surface)] border border-[var(--color-border)]',
        'rounded-[var(--radius-lg)] shadow-[var(--shadow-sm)]',
        'p-4 flex flex-col gap-3',
        'transition-opacity duration-[var(--duration-normal)]',
        'animate-fade-in'
      )}
    >
      {/* Title + company */}
      <div className="flex flex-col gap-0.5 min-w-0">
        <span
          className="font-[var(--font-display)] text-[var(--text-base)] font-semibold text-[var(--color-ink)] leading-[var(--leading-tight)] truncate"
          title={row.vacancy_title || 'Без названия'}
        >
          {titleTruncated || 'Без названия'}
        </span>
        <span className="text-[var(--text-sm)] text-[var(--color-ink-secondary)] truncate">
          {row.vacancy_company ?? 'Компания не указана'}
        </span>
      </div>

      {/* Badges row */}
      <div className="flex flex-wrap items-center gap-2">
        {row.resume_label ? (
          <Badge variant="info" className="max-w-[140px] truncate" title={row.resume_label}>
            {row.resume_label}
          </Badge>
        ) : null}
        <span className="text-[var(--text-xs)] text-[var(--color-ink-muted)] ml-auto">
          {formatFriendlyDate(row.last_status_change_at)}
        </span>
      </div>

      {/* Status dropdown */}
      <div>
        <select
          value={row.status}
          disabled={isBusy}
          aria-label="Изменить статус"
          className={cn(
            'w-full text-[var(--text-sm)] font-semibold',
            'border border-[var(--color-border)] rounded-[var(--radius-md)]',
            'bg-[var(--color-surface-muted)] text-[var(--color-ink)]',
            'px-3 py-2 cursor-pointer',
            'transition-colors duration-[var(--duration-fast)]',
            isBusy && 'opacity-55 cursor-not-allowed'
          )}
          onChange={(e) => onStatusChange(row.id, e.target.value as ApplicationStatus)}
        >
          {ALL_STATUS_ORDER.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
      </div>

      {/* Cover letter section */}
      <div className="border-t border-dashed border-[var(--color-border)] pt-3 flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={isBusy}
            onClick={() => onToggleCoverLetter(row.id)}
          >
            {coverLetterOpen
              ? 'Скрыть сопроводительное'
              : hasLetter
              ? 'Открыть сопроводительное'
              : 'Сопроводительное'}
          </Button>
          {!coverLetterOpen && !hasLetter ? (
            <Button
              variant="primary"
              size="sm"
              disabled={isBusy}
              onClick={() => onGenerateCoverLetter(row.id, false)}
            >
              Сгенерировать
            </Button>
          ) : null}
          {row.cover_letter_generated_at ? (
            <span className="text-[var(--text-xs)] text-[var(--color-ink-muted)] italic">
              {formatFriendlyDate(row.cover_letter_generated_at)}
            </span>
          ) : null}
        </div>

        {coverLetterOpen ? (
          <div className="flex flex-col gap-2">
            <textarea
              rows={7}
              maxLength={6000}
              value={coverLetterDraft}
              disabled={isBusy}
              className={cn(
                'w-full resize-vertical min-h-[140px]',
                'border border-[var(--color-border)] rounded-[var(--radius-md)]',
                'bg-[var(--color-surface-muted)] text-[var(--color-ink)]',
                'text-[var(--text-sm)] leading-[var(--leading-normal)]',
                'p-3 font-[var(--font-body)]'
              )}
              placeholder={
                hasLetter
                  ? ''
                  : 'Нажмите «Сгенерировать», чтобы получить черновик от GPT, или введите свой текст.'
              }
              onChange={(e) => onCoverLetterChange(row.id, e.target.value)}
            />
            <div className="flex flex-wrap gap-2">
              <Button
                variant="primary"
                size="sm"
                disabled={isBusy}
                onClick={() => onGenerateCoverLetter(row.id, hasLetter)}
              >
                {hasLetter ? 'Сгенерировать заново' : 'Сгенерировать'}
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={isBusy || !coverLetterChanged}
                onClick={() => onSaveCoverLetter(row.id)}
              >
                Сохранить правки
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={isBusy || !coverLetterDraft.trim()}
                onClick={() => onCopyCoverLetter(row.id)}
              >
                Копировать
              </Button>
            </div>
          </div>
        ) : null}
      </div>

      {/* Notes section */}
      <Collapsible>
        <CollapsibleTrigger
          className={cn(
            'w-full flex items-center justify-between',
            'text-[var(--text-sm)] font-semibold text-[var(--color-ink-secondary)]',
            'hover:text-[var(--color-ink)] transition-colors duration-[var(--duration-fast)]',
            'cursor-pointer py-1'
          )}
        >
          <span>Заметки</span>
          {hasNotes ? (
            <span className="text-[var(--text-xs)] text-[var(--color-ink-muted)] font-normal">
              (есть)
            </span>
          ) : null}
        </CollapsibleTrigger>
        <CollapsibleContent className="flex flex-col gap-2 pt-2">
          <Textarea
            rows={4}
            maxLength={4000}
            value={notesDraft}
            disabled={isBusy}
            placeholder="Заметки к отклику…"
            onChange={(e) => onNotesChange(row.id, e.target.value)}
          />
          <div className="flex justify-end">
            <Button
              variant="secondary"
              size="sm"
              disabled={isBusy || !notesChanged}
              onClick={() => onSaveNotes(row.id)}
            >
              Сохранить
            </Button>
          </div>
        </CollapsibleContent>
      </Collapsible>

      {/* Source link */}
      {row.source_url ? (
        <a
          href={row.source_url}
          target="_blank"
          rel="noreferrer"
          className="text-[var(--text-sm)] font-semibold text-[var(--color-accent)] self-start"
        >
          Открыть вакансию ↗
        </a>
      ) : null}
    </article>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Column header badge
// ─────────────────────────────────────────────────────────────────────────────
function ColumnHeader({ label, count }: { label: string; count: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="font-[var(--font-display)] text-[var(--text-base)] font-semibold text-[var(--color-ink)] tracking-[-0.02em]">
        {label}
      </span>
      <span
        className={cn(
          'inline-flex items-center justify-center',
          'min-w-[22px] h-[22px] px-1.5',
          'rounded-[var(--radius-full)]',
          'text-[11px] font-bold',
          'bg-[var(--color-surface-muted)] text-[var(--color-ink-secondary)]',
          'border border-[var(--color-border)]'
        )}
      >
        {count}
      </span>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────────────────
// Page component
// ─────────────────────────────────────────────────────────────────────────────
export default function ApplicationsPage() {
  const { token } = useSession();

  const [applications, setApplications] = useState<Application[]>([]);
  const [statusMessage, setStatusMessage] = useState('');
  const [busyIds, setBusyIds] = useState<Record<number, boolean>>({});
  const [coverLetterOpenIds, setCoverLetterOpenIds] = useState<Record<number, boolean>>({});
  const [coverLetterDrafts, setCoverLetterDrafts] = useState<Record<number, string>>({});
  const [notesDrafts, setNotesDrafts] = useState<Record<number, string>>({});
  const [archiveOpen, setArchiveOpen] = useState(false);
  // Mobile: which column accordion is open (null = none)
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
      setStatusMessage(
        error instanceof Error
          ? `Не удалось загрузить отклики: ${error.message}`
          : 'Не удалось загрузить отклики.'
      );
    }
  }

  function setBusy(id: number, busy: boolean) {
    setBusyIds((prev) => {
      const next = { ...prev };
      if (busy) next[id] = true;
      else delete next[id];
      return next;
    });
  }

  async function changeApplicationStatus(applicationId: number, nextStatus: ApplicationStatus) {
    const existing = applications.find((r) => r.id === applicationId);
    if (!existing || existing.status === nextStatus) return;
    setBusy(applicationId, true);
    try {
      const updated = await apiFetch<Application>(`/api/applications/${applicationId}`, {
        token,
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: nextStatus }),
      });
      setApplications((prev) => prev.map((r) => (r.id === applicationId ? updated : r)));
      setStatusMessage('');
    } catch (error) {
      setStatusMessage(
        error instanceof Error
          ? `Не удалось обновить статус: ${error.message}`
          : 'Не удалось обновить статус.'
      );
    } finally {
      setBusy(applicationId, false);
    }
  }

  function toggleCoverLetter(applicationId: number) {
    setCoverLetterOpenIds((prev) => {
      const next = { ...prev };
      if (next[applicationId]) delete next[applicationId];
      else next[applicationId] = true;
      return next;
    });
    const row = applications.find((a) => a.id === applicationId);
    if (row && coverLetterDrafts[applicationId] === undefined) {
      setCoverLetterDrafts((prev) => ({ ...prev, [applicationId]: row.cover_letter_text ?? '' }));
    }
  }

  async function generateCoverLetter(applicationId: number, force: boolean) {
    setBusy(applicationId, true);
    try {
      const response = await apiFetch<CoverLetterResponse>(
        `/api/applications/${applicationId}/cover-letter${force ? '?force=true' : ''}`,
        { token, method: 'POST' }
      );
      setApplications((prev) =>
        prev.map((r) =>
          r.id === applicationId
            ? {
                ...r,
                cover_letter_text: response.cover_letter_text,
                cover_letter_generated_at: response.cover_letter_generated_at,
              }
            : r
        )
      );
      setCoverLetterDrafts((prev) => ({ ...prev, [applicationId]: response.cover_letter_text }));
      setCoverLetterOpenIds((prev) => ({ ...prev, [applicationId]: true }));
      setStatusMessage(
        response.cached
          ? 'Показываем сохранённое письмо (свежая генерация была менее суток назад).'
          : 'Сопроводительное сгенерировано. Проверьте и при необходимости отредактируйте.'
      );
    } catch (error) {
      setStatusMessage(
        error instanceof Error
          ? `Не удалось сгенерировать письмо: ${error.message}`
          : 'Не удалось сгенерировать письмо.'
      );
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
      const payload: Record<string, unknown> = trimmed
        ? { cover_letter_text: trimmed }
        : { clear_cover_letter: true };
      const updated = await apiFetch<Application>(`/api/applications/${applicationId}`, {
        token,
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setApplications((prev) => prev.map((r) => (r.id === applicationId ? updated : r)));
      setCoverLetterDrafts((prev) => ({ ...prev, [applicationId]: updated.cover_letter_text ?? '' }));
      setStatusMessage('Правки сопроводительного сохранены.');
    } catch (error) {
      setStatusMessage(
        error instanceof Error
          ? `Не удалось сохранить письмо: ${error.message}`
          : 'Не удалось сохранить письмо.'
      );
    } finally {
      setBusy(applicationId, false);
    }
  }

  async function saveApplicationNotes(applicationId: number) {
    const draft = notesDrafts[applicationId] ?? '';
    const existing = applications.find((r) => r.id === applicationId);
    if (!existing) return;
    const trimmed = draft.trim();
    if (trimmed === (existing.notes ?? '').trim()) return;
    setBusy(applicationId, true);
    try {
      const payload: Record<string, unknown> = trimmed
        ? { notes: trimmed }
        : { clear_notes: true };
      const updated = await apiFetch<Application>(`/api/applications/${applicationId}`, {
        token,
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setApplications((prev) => prev.map((r) => (r.id === applicationId ? updated : r)));
      setNotesDrafts((prev) => ({ ...prev, [applicationId]: updated.notes ?? '' }));
      setStatusMessage('Заметка сохранена.');
    } catch (error) {
      setStatusMessage(
        error instanceof Error
          ? `Не удалось сохранить заметку: ${error.message}`
          : 'Не удалось сохранить заметку.'
      );
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

  if (!token) return null;

  const activeApps = applications.filter((r) => !ARCHIVED_STATUSES.includes(r.status));
  const archivedApps = applications.filter((r) => ARCHIVED_STATUSES.includes(r.status));
  const archiveCount = archivedApps.length;

  function cardsForColumn(colId: ColumnId): Application[] {
    return activeApps
      .filter((r) => columnForStatus(r.status) === colId)
      .sort(
        (a, b) =>
          new Date(b.last_status_change_at).getTime() - new Date(a.last_status_change_at).getTime()
      );
  }

  function renderCard(row: Application) {
    return (
      <ApplicationCard
        key={row.id}
        row={row}
        isBusy={Boolean(busyIds[row.id])}
        coverLetterOpen={Boolean(coverLetterOpenIds[row.id])}
        coverLetterDraft={coverLetterDrafts[row.id] ?? row.cover_letter_text ?? ''}
        notesDraft={notesDrafts[row.id] ?? row.notes ?? ''}
        onStatusChange={changeApplicationStatus}
        onToggleCoverLetter={toggleCoverLetter}
        onGenerateCoverLetter={generateCoverLetter}
        onSaveCoverLetter={saveCoverLetterEdits}
        onCopyCoverLetter={copyCoverLetterToClipboard}
        onCoverLetterChange={(id, text) =>
          setCoverLetterDrafts((prev) => ({ ...prev, [id]: text }))
        }
        onNotesChange={(id, text) =>
          setNotesDrafts((prev) => ({ ...prev, [id]: text }))
        }
        onSaveNotes={saveApplicationNotes}
      />
    );
  }

  function renderColumnBody(colId: ColumnId) {
    const cards = cardsForColumn(colId);
    if (colId === 'interview+offer') {
      const interviewCards = cards.filter((r) => r.status === 'interview');
      const offerCards = cards.filter((r) => r.status === 'offer');
      const empty = cards.length === 0;
      const col = COLUMNS.find((c) => c.id === colId)!;
      return (
        <div className="flex flex-col gap-3">
          {empty ? (
            <p className="text-[var(--text-sm)] text-[var(--color-ink-muted)] italic">
              {col.emptyText}
            </p>
          ) : null}
          {interviewCards.map(renderCard)}
          {interviewCards.length > 0 && offerCards.length > 0 ? (
            <Separator className="my-1" />
          ) : null}
          {offerCards.map(renderCard)}
        </div>
      );
    }
    const cards2 = cardsForColumn(colId);
    const col = COLUMNS.find((c) => c.id === colId)!;
    return (
      <div className="flex flex-col gap-3">
        {cards2.length === 0 ? (
          <p className="text-[var(--text-sm)] text-[var(--color-ink-muted)] italic">
            {col.emptyText}
          </p>
        ) : null}
        {cards2.map(renderCard)}
      </div>
    );
  }

  return (
    <div className="w-full max-w-[var(--content-width)] mx-auto px-4 py-10 flex flex-col gap-6">
      {/* Page title */}
      <div className="flex flex-col gap-1">
        <h1
          className="font-[var(--font-display)] text-[var(--text-3xl)] font-semibold text-[var(--color-ink)] tracking-[-0.03em] leading-[var(--leading-tight)]"
        >
          Мои отклики
        </h1>
        <p className="text-[var(--text-sm)] text-[var(--color-ink-secondary)]">
          Статусный трекер откликов. Смени статус через выпадающий список на карточке.
        </p>
      </div>

      {/* Status message */}
      {statusMessage ? (
        <div
          className={cn(
            'rounded-[var(--radius-md)] px-4 py-3 text-[var(--text-sm)]',
            'bg-[var(--color-warning-subtle)] text-[var(--color-warning)]',
            'border border-[color-mix(in_srgb,var(--color-warning)_25%,transparent)]'
          )}
        >
          {statusMessage}
        </div>
      ) : null}

      {/* ── Desktop board (≥900px): 4 equal columns ─────────────────────────── */}
      <div className="hidden min-[900px]:grid grid-cols-4 gap-6">
        {COLUMNS.map((col) => (
          <div key={col.id} className="flex flex-col gap-3">
            {/* Sticky column header */}
            <div
              className={cn(
                'sticky top-0 z-10 py-3 px-1',
                'bg-[var(--color-canvas)]',
                'border-b border-[var(--color-border)]'
              )}
            >
              <ColumnHeader label={col.label} count={cardsForColumn(col.id).length} />
            </div>
            {renderColumnBody(col.id)}
          </div>
        ))}
      </div>

      {/* ── Mobile board (<900px): 4 accordions ─────────────────────────────── */}
      <div className="flex flex-col gap-3 min-[900px]:hidden">
        {COLUMNS.map((col) => {
          const isOpen = mobileOpenCol === col.id;
          const count = cardsForColumn(col.id).length;
          return (
            <Collapsible
              key={col.id}
              open={isOpen}
              onOpenChange={(open) => setMobileOpenCol(open ? col.id : null)}
            >
              <CollapsibleTrigger
                className={cn(
                  'w-full flex items-center justify-between',
                  'bg-[var(--color-surface)] border border-[var(--color-border)]',
                  'rounded-[var(--radius-md)] px-4 py-3',
                  'shadow-[var(--shadow-sm)]',
                  'cursor-pointer',
                  'transition-colors duration-[var(--duration-fast)]',
                  'hover:bg-[var(--color-surface-muted)]',
                  isOpen && 'border-[var(--color-border-strong)]'
                )}
              >
                <ColumnHeader label={col.label} count={count} />
                <svg
                  className={cn(
                    'h-4 w-4 text-[var(--color-ink-muted)] transition-transform duration-[var(--duration-fast)]',
                    isOpen && 'rotate-180'
                  )}
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </CollapsibleTrigger>
              <CollapsibleContent className="data-[state=open]:animate-slide-down data-[state=closed]:animate-slide-up pt-3">
                {renderColumnBody(col.id)}
              </CollapsibleContent>
            </Collapsible>
          );
        })}
      </div>

      {/* ── Archive toggle ────────────────────────────────────────────────────── */}
      {archiveCount > 0 ? (
        <div className="flex flex-col gap-4 mt-2">
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => setArchiveOpen((v) => !v)}
              className={cn(
                'inline-flex items-center gap-2',
                'text-[var(--text-sm)] font-semibold text-[var(--color-ink-secondary)]',
                'hover:text-[var(--color-ink)]',
                'transition-colors duration-[var(--duration-fast)]',
                'cursor-pointer'
              )}
            >
              <svg
                className={cn(
                  'h-4 w-4 transition-transform duration-[var(--duration-fast)]',
                  archiveOpen && 'rotate-180'
                )}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
              </svg>
              Архив ({archiveCount})
            </button>
          </div>

          {archiveOpen ? (
            <div className="flex flex-col gap-3 animate-fade-in">
              <Separator />
              <p className="text-[var(--text-xs)] text-[var(--color-ink-muted)] uppercase font-bold tracking-[0.08em]">
                Архив
              </p>
              {archivedApps
                .sort(
                  (a, b) =>
                    new Date(b.last_status_change_at).getTime() -
                    new Date(a.last_status_change_at).getTime()
                )
                .map((row) => (
                  <div
                    key={row.id}
                    className={cn(
                      'flex flex-col gap-1 px-4 py-3',
                      'bg-[var(--color-surface-muted)] border border-[var(--color-border)]',
                      'rounded-[var(--radius-md)]',
                      'opacity-70'
                    )}
                  >
                    <span
                      className="text-[var(--text-sm)] font-semibold text-[var(--color-ink)] truncate"
                      title={row.vacancy_title}
                    >
                      {row.vacancy_title || 'Без названия'}
                    </span>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-[var(--text-xs)] text-[var(--color-ink-muted)]">
                        {row.vacancy_company ?? ''}
                      </span>
                      <Badge variant="danger">{STATUS_LABELS[row.status]}</Badge>
                      <span className="text-[var(--text-xs)] text-[var(--color-ink-muted)] ml-auto">
                        {formatFriendlyDate(row.last_status_change_at)}
                      </span>
                    </div>
                  </div>
                ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
