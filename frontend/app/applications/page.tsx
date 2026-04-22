'use client';

import { useEffect, useState } from 'react';
import { useSession } from '@/lib/session';
import { apiFetch } from '@/lib/api';

// ──────────────────────────────────────────────────────────────────────────────
// Types (verbatim from page.tsx)
// ──────────────────────────────────────────────────────────────────────────────
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

type ApplicationFilter = 'all' | 'active' | 'archived' | ApplicationStatus;

const APPLICATION_STATUS_LABELS: Record<ApplicationStatus, string> = {
  draft: 'Черновик',
  applied: 'Откликнулся',
  viewed: 'Просмотрено',
  replied: 'Получен ответ',
  interview: 'Интервью',
  offer: 'Оффер',
  rejected: 'Отказ',
  declined: 'Отклонил сам',
};

const APPLICATION_ACTIVE_STATUSES: ApplicationStatus[] = [
  'draft',
  'applied',
  'viewed',
  'replied',
  'interview',
  'offer',
];

const APPLICATION_ARCHIVED_STATUSES: ApplicationStatus[] = ['rejected', 'declined'];

const APPLICATION_STATUS_ORDER: ApplicationStatus[] = [
  'draft',
  'applied',
  'viewed',
  'replied',
  'interview',
  'offer',
  'rejected',
  'declined',
];

const APPLICATION_FILTER_TABS: { value: ApplicationFilter; label: string }[] = [
  { value: 'all', label: 'Все' },
  { value: 'active', label: 'В работе' },
  { value: 'draft', label: 'Черновики' },
  { value: 'applied', label: 'Откликнулся' },
  { value: 'interview', label: 'Интервью' },
  { value: 'offer', label: 'Оффер' },
  { value: 'archived', label: 'Архив' },
];

// ──────────────────────────────────────────────────────────────────────────────
// Helper
// ──────────────────────────────────────────────────────────────────────────────
function formatApplicationDate(value: string | null): string {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleDateString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

// ──────────────────────────────────────────────────────────────────────────────
// Page component
// ──────────────────────────────────────────────────────────────────────────────
export default function ApplicationsPage() {
  const { token } = useSession();

  const [applications, setApplications] = useState<Application[]>([]);
  const [applicationsMessage, setApplicationsMessage] = useState('');
  const [applicationFilter, setApplicationFilter] = useState<ApplicationFilter>('active');
  const [applicationNotesDraft, setApplicationNotesDraft] = useState<Record<number, string>>({});
  const [applicationBusyIds, setApplicationBusyIds] = useState<Record<number, boolean>>({});
  const [expandedCoverLetterIds, setExpandedCoverLetterIds] = useState<Record<number, boolean>>({});
  const [coverLetterDrafts, setCoverLetterDrafts] = useState<Record<number, string>>({});

  useEffect(() => {
    if (!token) return;
    void loadApplications();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function loadApplications() {
    try {
      const data = await apiFetch<Application[]>('/api/applications', { token });
      setApplications(data);
      setApplicationNotesDraft((current) => {
        const next: Record<number, string> = { ...current };
        for (const row of data) {
          if (next[row.id] === undefined) {
            next[row.id] = row.notes ?? '';
          }
        }
        return next;
      });
    } catch (error) {
      setApplications([]);
      setApplicationsMessage(
        error instanceof Error ? `Не удалось загрузить отклики: ${error.message}` : 'Не удалось загрузить отклики.'
      );
    }
  }

  function setApplicationBusy(id: number, busyFlag: boolean) {
    setApplicationBusyIds((current) => {
      const next = { ...current };
      if (busyFlag) {
        next[id] = true;
      } else {
        delete next[id];
      }
      return next;
    });
  }

  async function changeApplicationStatus(applicationId: number, nextStatus: ApplicationStatus) {
    const existing = applications.find((row) => row.id === applicationId);
    if (!existing || existing.status === nextStatus) {
      return;
    }
    setApplicationBusy(applicationId, true);
    try {
      const updated = await apiFetch<Application>(`/api/applications/${applicationId}`, {
        token,
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: nextStatus }),
      });
      setApplications((current) => current.map((row) => (row.id === applicationId ? updated : row)));
      setApplicationsMessage('');
    } catch (error) {
      setApplicationsMessage(
        error instanceof Error ? `Не удалось обновить статус: ${error.message}` : 'Не удалось обновить статус.'
      );
    } finally {
      setApplicationBusy(applicationId, false);
    }
  }

  async function saveApplicationNotes(applicationId: number) {
    const draft = applicationNotesDraft[applicationId] ?? '';
    const existing = applications.find((row) => row.id === applicationId);
    if (!existing) {
      return;
    }
    const trimmed = draft.trim();
    const currentValue = existing.notes ?? '';
    if (trimmed === currentValue.trim()) {
      return;
    }
    setApplicationBusy(applicationId, true);
    try {
      const payload: Record<string, unknown> = trimmed ? { notes: trimmed } : { clear_notes: true };
      const updated = await apiFetch<Application>(`/api/applications/${applicationId}`, {
        token,
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setApplications((current) => current.map((row) => (row.id === applicationId ? updated : row)));
      setApplicationNotesDraft((current) => ({ ...current, [applicationId]: updated.notes ?? '' }));
      setApplicationsMessage('');
    } catch (error) {
      setApplicationsMessage(
        error instanceof Error ? `Не удалось сохранить заметку: ${error.message}` : 'Не удалось сохранить заметку.'
      );
    } finally {
      setApplicationBusy(applicationId, false);
    }
  }

  async function deleteApplicationRow(applicationId: number) {
    if (!window.confirm('Удалить отклик? Действие нельзя отменить.')) {
      return;
    }
    setApplicationBusy(applicationId, true);
    try {
      await apiFetch<void>(`/api/applications/${applicationId}`, { token, method: 'DELETE' });
      setApplications((current) => current.filter((row) => row.id !== applicationId));
      setApplicationNotesDraft((current) => {
        const next = { ...current };
        delete next[applicationId];
        return next;
      });
    } catch (error) {
      setApplicationsMessage(
        error instanceof Error ? `Не удалось удалить отклик: ${error.message}` : 'Не удалось удалить отклик.'
      );
    } finally {
      setApplicationBusy(applicationId, false);
    }
  }

  function toggleCoverLetter(applicationId: number) {
    setExpandedCoverLetterIds((current) => {
      const next = { ...current };
      if (next[applicationId]) {
        delete next[applicationId];
      } else {
        next[applicationId] = true;
      }
      return next;
    });
    const row = applications.find((app) => app.id === applicationId);
    if (row && coverLetterDrafts[applicationId] === undefined) {
      setCoverLetterDrafts((current) => ({ ...current, [applicationId]: row.cover_letter_text ?? '' }));
    }
  }

  async function generateCoverLetter(applicationId: number, force: boolean) {
    setApplicationBusy(applicationId, true);
    try {
      const response = await apiFetch<CoverLetterResponse>(
        `/api/applications/${applicationId}/cover-letter${force ? '?force=true' : ''}`,
        { token, method: 'POST' }
      );
      setApplications((current) =>
        current.map((row) =>
          row.id === applicationId
            ? {
                ...row,
                cover_letter_text: response.cover_letter_text,
                cover_letter_generated_at: response.cover_letter_generated_at,
              }
            : row
        )
      );
      setCoverLetterDrafts((current) => ({ ...current, [applicationId]: response.cover_letter_text }));
      setExpandedCoverLetterIds((current) => ({ ...current, [applicationId]: true }));
      setApplicationsMessage(
        response.cached
          ? 'Показываем сохранённое письмо (свежая генерация была менее суток назад).'
          : 'Сопроводительное сгенерировано. Проверьте и при необходимости отредактируйте.'
      );
    } catch (error) {
      setApplicationsMessage(
        error instanceof Error
          ? `Не удалось сгенерировать письмо: ${error.message}`
          : 'Не удалось сгенерировать письмо.'
      );
    } finally {
      setApplicationBusy(applicationId, false);
    }
  }

  async function saveCoverLetterEdits(applicationId: number) {
    const draft = coverLetterDrafts[applicationId] ?? '';
    const existing = applications.find((row) => row.id === applicationId);
    if (!existing) {
      return;
    }
    const trimmed = draft.trim();
    const currentValue = (existing.cover_letter_text ?? '').trim();
    if (trimmed === currentValue) {
      return;
    }
    setApplicationBusy(applicationId, true);
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
      setApplications((current) => current.map((row) => (row.id === applicationId ? updated : row)));
      setCoverLetterDrafts((current) => ({ ...current, [applicationId]: updated.cover_letter_text ?? '' }));
      setApplicationsMessage('Правки сопроводительного сохранены.');
    } catch (error) {
      setApplicationsMessage(
        error instanceof Error
          ? `Не удалось сохранить письмо: ${error.message}`
          : 'Не удалось сохранить письмо.'
      );
    } finally {
      setApplicationBusy(applicationId, false);
    }
  }

  async function copyCoverLetterToClipboard(applicationId: number) {
    const text = coverLetterDrafts[applicationId];
    if (!text) {
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      setApplicationsMessage('Текст сопроводительного скопирован в буфер.');
    } catch {
      setApplicationsMessage('Не удалось скопировать. Выделите текст вручную.');
    }
  }

  function filteredApplications(): Application[] {
    const sorted = [...applications].sort((a, b) => {
      const aIdx = APPLICATION_STATUS_ORDER.indexOf(a.status);
      const bIdx = APPLICATION_STATUS_ORDER.indexOf(b.status);
      if (aIdx !== bIdx) {
        return aIdx - bIdx;
      }
      return new Date(b.last_status_change_at).getTime() - new Date(a.last_status_change_at).getTime();
    });
    if (applicationFilter === 'all') {
      return sorted;
    }
    if (applicationFilter === 'active') {
      return sorted.filter((row) => APPLICATION_ACTIVE_STATUSES.includes(row.status));
    }
    if (applicationFilter === 'archived') {
      return sorted.filter((row) => APPLICATION_ARCHIVED_STATUSES.includes(row.status));
    }
    return sorted.filter((row) => row.status === applicationFilter);
  }

  if (!token) {
    return null;
  }

  return (
    <section className="panel applications-panel">
      <div className="applications-header">
        <h2>Мои отклики</h2>
        <p className="panel-note">
          Статусный трекер откликов: черновики, отклик отправлен, интервью, оффер. Отражает только ваши записи.
        </p>
      </div>
      <div className="applications-filters" role="tablist">
        {APPLICATION_FILTER_TABS.map((tab) => (
          <button
            key={tab.value}
            role="tab"
            className={`filter-chip${applicationFilter === tab.value ? ' active' : ''}`}
            onClick={() => setApplicationFilter(tab.value)}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {applicationsMessage ? <p className="panel-note">{applicationsMessage}</p> : null}
      <div className="applications-list">
        {applications.length === 0 ? (
          <p className="empty-state">
            Пока нет откликов. Нажмите «Откликнуться» в подборке или создайте отклик вручную.
          </p>
        ) : null}
        {applications.length > 0 && filteredApplications().length === 0 ? (
          <p className="empty-state">В этой категории пока пусто.</p>
        ) : null}
        {filteredApplications().map((row) => {
          const isBusy = Boolean(applicationBusyIds[row.id]);
          const draft = applicationNotesDraft[row.id] ?? row.notes ?? '';
          const notesChanged = draft.trim() !== (row.notes ?? '').trim();
          const coverLetterOpen = Boolean(expandedCoverLetterIds[row.id]);
          const coverLetterDraft = coverLetterDrafts[row.id] ?? row.cover_letter_text ?? '';
          const coverLetterChanged =
            coverLetterDraft.trim() !== (row.cover_letter_text ?? '').trim();
          const hasLetter = Boolean(row.cover_letter_text);
          return (
            <article className="application-card" key={`application-${row.id}`}>
              <header className="application-card-head">
                <div>
                  <h3>{row.vacancy_title || 'Без названия'}</h3>
                  <p className="meta">
                    {row.vacancy_company || 'Компания не указана'}
                    {row.applied_at ? ` • отклик от ${formatApplicationDate(row.applied_at)}` : ''}
                  </p>
                </div>
                <div className="application-card-tags">
                  {row.resume_id ? (
                    <span className="resume-badge" title="Профиль, из которого создан отклик">
                      {row.resume_label ?? 'Профиль'}
                    </span>
                  ) : null}
                  <span className={`status-pill status-${row.status}`}>
                    {APPLICATION_STATUS_LABELS[row.status]}
                  </span>
                </div>
              </header>
              <div className="application-card-controls">
                <label className="field">
                  <span>Статус</span>
                  <select
                    value={row.status}
                    disabled={isBusy}
                    onChange={(event) =>
                      void changeApplicationStatus(row.id, event.target.value as ApplicationStatus)
                    }
                  >
                    {APPLICATION_STATUS_ORDER.map((status) => (
                      <option key={status} value={status}>
                        {APPLICATION_STATUS_LABELS[status]}
                      </option>
                    ))}
                  </select>
                </label>
                {row.source_url ? (
                  <a href={row.source_url} target="_blank" rel="noreferrer" className="application-link">
                    Открыть вакансию
                  </a>
                ) : null}
              </div>
              <label className="field application-notes">
                <span>Заметки</span>
                <textarea
                  rows={2}
                  maxLength={2000}
                  value={draft}
                  disabled={isBusy}
                  onChange={(event) =>
                    setApplicationNotesDraft((current) => ({ ...current, [row.id]: event.target.value }))
                  }
                  placeholder="Напомните себе контекст: когда писать рекрутеру, что ответить на тест, к какому дню готовиться."
                />
              </label>
              <div className="cover-letter-block">
                <div className="cover-letter-head">
                  <button
                    className="secondary cover-letter-toggle"
                    disabled={isBusy}
                    onClick={() => toggleCoverLetter(row.id)}
                  >
                    {coverLetterOpen
                      ? 'Скрыть сопроводительное'
                      : hasLetter
                      ? 'Открыть сопроводительное'
                      : 'Сгенерировать сопроводительное'}
                  </button>
                  {!coverLetterOpen && !hasLetter ? (
                    <button
                      className="primary cover-letter-generate"
                      disabled={isBusy}
                      onClick={() => void generateCoverLetter(row.id, false)}
                    >
                      Сгенерировать
                    </button>
                  ) : null}
                  {row.cover_letter_generated_at ? (
                    <span className="cover-letter-stamp">
                      Последняя генерация: {formatApplicationDate(row.cover_letter_generated_at)}
                    </span>
                  ) : null}
                </div>
                {coverLetterOpen ? (
                  <>
                    <textarea
                      className="cover-letter-textarea"
                      rows={8}
                      maxLength={6000}
                      value={coverLetterDraft}
                      disabled={isBusy}
                      onChange={(event) =>
                        setCoverLetterDrafts((current) => ({
                          ...current,
                          [row.id]: event.target.value,
                        }))
                      }
                      placeholder={
                        hasLetter
                          ? ''
                          : 'Нажмите «Сгенерировать», чтобы получить черновик от GPT, или введите свой текст.'
                      }
                    />
                    <div className="cover-letter-actions">
                      <button
                        className="primary"
                        disabled={isBusy}
                        onClick={() => void generateCoverLetter(row.id, hasLetter)}
                      >
                        {hasLetter ? 'Сгенерировать заново' : 'Сгенерировать'}
                      </button>
                      <button
                        className="secondary"
                        disabled={isBusy || !coverLetterChanged}
                        onClick={() => void saveCoverLetterEdits(row.id)}
                      >
                        Сохранить правки
                      </button>
                      <button
                        className="secondary"
                        disabled={isBusy || !coverLetterDraft.trim()}
                        onClick={() => void copyCoverLetterToClipboard(row.id)}
                      >
                        Копировать
                      </button>
                    </div>
                  </>
                ) : null}
              </div>
              <div className="application-card-footer">
                <button
                  className="secondary"
                  disabled={isBusy || !notesChanged}
                  onClick={() => void saveApplicationNotes(row.id)}
                >
                  Сохранить заметку
                </button>
                <button
                  className="danger"
                  disabled={isBusy}
                  onClick={() => void deleteApplicationRow(row.id)}
                >
                  Удалить
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
