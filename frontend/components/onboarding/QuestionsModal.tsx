'use client';

import * as React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { apiFetch } from '@/lib/api';
import { useSession } from '@/lib/session';
import { trackEvent } from '@/lib/telemetry';
import type { OnboardingQuestionOut } from '@/types/audit';

// ─── Sub-components ───────────────────────────────────────────────────────────

interface ChoiceInputProps {
  question: OnboardingQuestionOut;
  value: string;
  onChange: (v: string) => void;
}

function ChoiceInput({ question, value, onChange }: ChoiceInputProps) {
  const choices = question.choices ?? [];
  return (
    <fieldset className="border-0 p-0 m-0">
      <legend className="sr-only">{question.text}</legend>
      <div className="flex flex-wrap gap-2 mt-3">
        {choices.map((opt) => {
          const selected = value === opt;
          return (
            <button
              key={opt}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => onChange(opt)}
              className={cn(
                'px-4 py-2 rounded-[var(--radius-full)] border text-[length:var(--text-sm)] font-semibold',
                'transition-[border-color,background,color] duration-[var(--duration-fast)]',
                'focus-visible:outline-2 focus-visible:outline-[var(--color-focus-ring)] focus-visible:outline-offset-2',
                selected
                  ? 'bg-[var(--color-accent-subtle)] border-[var(--color-accent)] text-[color:var(--color-accent)]'
                  : 'bg-[var(--color-surface-muted)] border-[var(--color-border)] text-[color:var(--color-ink)] hover:border-[var(--color-border-strong)]'
              )}
            >
              {opt}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}

interface BooleanInputProps {
  value: string;
  onChange: (v: string) => void;
}

function BooleanInput({ value, onChange }: BooleanInputProps) {
  return (
    <div className="flex gap-3 mt-3">
      {(['да', 'нет'] as const).map((label) => {
        const boolVal = label === 'да' ? 'true' : 'false';
        const selected = value === boolVal;
        return (
          <button
            key={label}
            type="button"
            role="radio"
            aria-checked={selected}
            onClick={() => onChange(boolVal)}
            className={cn(
              'px-5 py-2 rounded-[var(--radius-full)] border text-[length:var(--text-sm)] font-semibold capitalize',
              'transition-[border-color,background,color] duration-[var(--duration-fast)]',
              'focus-visible:outline-2 focus-visible:outline-[var(--color-focus-ring)] focus-visible:outline-offset-2',
              selected
                ? 'bg-[var(--color-accent-subtle)] border-[var(--color-accent)] text-[color:var(--color-accent)]'
                : 'bg-[var(--color-surface-muted)] border-[var(--color-border)] text-[color:var(--color-ink)] hover:border-[var(--color-border-strong)]'
            )}
          >
            {label.charAt(0).toUpperCase() + label.slice(1)}
          </button>
        );
      })}
    </div>
  );
}

interface NumberRangeInputProps {
  question: OnboardingQuestionOut;
  value: string;
  onChange: (v: string) => void;
}

function NumberRangeInput({ question, value, onChange }: NumberRangeInputProps) {
  // Sensible defaults when min/max are not in the schema
  const numericValue = parseInt(value, 10) || 60000;
  const displayValue = numericValue.toLocaleString('ru-RU');

  return (
    <div className="mt-3 grid gap-2">
      <div className="flex items-center gap-3">
        <input
          type="number"
          id={`number-${question.id}`}
          placeholder="Введите значение"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="flex-1 border border-[var(--color-border)] rounded-[var(--radius-md)] px-3 py-2 text-[length:var(--text-base)] bg-[var(--color-surface)] text-[color:var(--color-ink)] focus:outline-2 focus:outline-[var(--color-focus-ring)]"
        />
        <span
          className="shrink-0 text-[length:var(--text-sm)] text-[color:var(--color-ink-muted)] w-24 text-right"
          aria-live="polite"
        >
          {value ? `${displayValue}` : ''}
        </span>
      </div>
    </div>
  );
}

interface TextInputProps {
  question: OnboardingQuestionOut;
  value: string;
  onChange: (v: string) => void;
}

function TextInput({ question, value, onChange }: TextInputProps) {
  return (
    <div className="mt-3">
      <textarea
        id={`text-${question.id}`}
        rows={3}
        placeholder="Введите ответ"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full border border-[var(--color-border)] rounded-[var(--radius-md)] px-3 py-2 text-[length:var(--text-base)] bg-[var(--color-surface)] text-[color:var(--color-ink)] resize-y focus:outline-2 focus:outline-[var(--color-focus-ring)]"
        aria-label={question.text}
      />
    </div>
  );
}

// ─── Progress stepper ─────────────────────────────────────────────────────────

function StepDots({ total, current }: { total: number; current: number }) {
  return (
    <div className="flex items-center gap-1.5" role="progressbar" aria-valuenow={current + 1} aria-valuemin={1} aria-valuemax={total}>
      {Array.from({ length: total }).map((_, i) => (
        <span
          key={i}
          className={cn(
            'block rounded-full transition-[width,background] duration-[var(--duration-normal)]',
            i === current
              ? 'w-4 h-2 bg-[var(--color-accent)]'
              : i < current
              ? 'w-2 h-2 bg-[var(--color-accent)]'
              : 'w-2 h-2 bg-[var(--color-surface-muted)] border border-[var(--color-border)]'
          )}
          aria-hidden="true"
        />
      ))}
      <span className="sr-only">{current + 1} из {total}</span>
    </div>
  );
}

// ─── Props ────────────────────────────────────────────────────────────────────

interface QuestionsModalProps {
  /** Resume ID — modal fetches its own questions from GET /api/resumes/{id}/onboarding/questions */
  resumeId: number;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called after last question answered (or user closes). Parent uses to refetch audit. */
  onAnswered?: () => void;
}

// ─── Main modal ───────────────────────────────────────────────────────────────

export function QuestionsModal({
  resumeId,
  open,
  onOpenChange,
  onAnswered,
}: QuestionsModalProps) {
  const { token } = useSession();

  const [questions, setQuestions] = React.useState<OnboardingQuestionOut[]>([]);
  const [loadingQuestions, setLoadingQuestions] = React.useState(false);
  const [step, setStep] = React.useState(0);
  const [answers, setAnswers] = React.useState<Record<string, string>>({});
  // Track answered question IDs so we know when all are done
  const [answeredIds, setAnsweredIds] = React.useState<Set<string>>(new Set());

  // Fetch questions when modal opens
  React.useEffect(() => {
    if (!open) return;

    setStep(0);
    setAnswers({});
    setAnsweredIds(new Set());
    setLoadingQuestions(true);

    apiFetch<OnboardingQuestionOut[]>(
      `/api/resumes/${resumeId}/onboarding/questions`,
      { token }
    )
      .then((data) => {
        if (data.length === 0) {
          // No questions — close and notify
          console.info('[QuestionsModal] Уточняющие вопросы закончились');
          onOpenChange(false);
          onAnswered?.();
        } else {
          setQuestions(data);
        }
      })
      .catch((err: unknown) => {
        console.debug('[QuestionsModal] Failed to load questions', err);
        onOpenChange(false);
      })
      .finally(() => setLoadingQuestions(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, resumeId, token]);

  const current = questions[step];

  const currentAnswer = current ? (answers[current.id] ?? '') : '';
  const isLast = step === questions.length - 1;

  // For choice and boolean — answer immediately on click, hide question (optimistic)
  function handleImmediateAnswer(questionId: string, value: string) {
    setAnswers((prev) => ({ ...prev, [questionId]: value }));
    postAnswer(questionId, value);
    advanceOrClose();
  }

  function handleSetAnswer(v: string) {
    if (!current) return;
    setAnswers((prev) => ({ ...prev, [current.id]: v }));
  }

  function postAnswer(questionId: string, value: string) {
    // Optimistic — fire and forget
    void apiFetch<null>(
      `/api/resumes/${resumeId}/onboarding/answer`,
      {
        token,
        method: 'POST',
        body: JSON.stringify({ question_id: questionId, answer_value: value }),
      }
    ).catch((err: unknown) => {
      console.debug('[QuestionsModal] answer POST failed', err);
    });
    trackEvent('onboarding_question_answered', { resume_id: resumeId, question_id: questionId });
    setAnsweredIds((prev) => new Set([...prev, questionId]));
  }

  function advanceOrClose() {
    if (isLast) {
      onOpenChange(false);
      onAnswered?.();
    } else {
      setStep((s) => s + 1);
    }
  }

  function handleSave() {
    if (!current || !currentAnswer.trim()) return;
    postAnswer(current.id, currentAnswer);
    advanceOrClose();
  }

  function handleBack() {
    setStep((s) => Math.max(0, s - 1));
  }

  function handleSkip() {
    advanceOrClose();
  }

  function handleDialogClose(nextOpen: boolean) {
    if (!nextOpen) {
      onAnswered?.();
    }
    onOpenChange(nextOpen);
  }

  // Don't render anything until we have questions
  if (!open) return null;

  if (loadingQuestions || !current) {
    return (
      <Dialog open={open} onOpenChange={handleDialogClose}>
        <DialogContent className="max-w-md w-full">
          <DialogHeader>
            <DialogTitle>Загрузка вопросов…</DialogTitle>
          </DialogHeader>
        </DialogContent>
      </Dialog>
    );
  }

  const isChoiceLike = current.answer_type === 'choice' || current.answer_type === 'boolean';
  const needsSaveButton = current.answer_type === 'number_range' || current.answer_type === 'text';
  const isAnswered = currentAnswer.trim().length > 0;

  return (
    <Dialog open={open} onOpenChange={handleDialogClose}>
      <DialogContent className="max-w-md w-full">
        <DialogHeader>
          <div className="flex items-center justify-between gap-4 mb-1">
            <StepDots total={questions.length} current={step} />
            <span className="text-[length:var(--text-xs)] text-[color:var(--color-ink-muted)] font-semibold tabular-nums">
              {step + 1} / {questions.length}
            </span>
          </div>
          <DialogTitle className="text-[length:var(--text-xl)] leading-[var(--leading-snug)]">
            {current.text}
          </DialogTitle>
          <DialogDescription className="mt-1">
            Ответ поможет точнее подобрать вакансии под ваши цели
          </DialogDescription>
        </DialogHeader>

        {/* Question input */}
        <div className="py-2">
          {current.answer_type === 'choice' && (
            <ChoiceInput
              question={current}
              value={currentAnswer}
              onChange={(v) => {
                handleSetAnswer(v);
                // For choice — one-click answers and advances (optimistic)
                handleImmediateAnswer(current.id, v);
              }}
            />
          )}
          {current.answer_type === 'boolean' && (
            <BooleanInput
              value={currentAnswer}
              onChange={(v) => handleImmediateAnswer(current.id, v)}
            />
          )}
          {current.answer_type === 'number_range' && (
            <NumberRangeInput
              question={current}
              value={currentAnswer}
              onChange={handleSetAnswer}
            />
          )}
          {current.answer_type === 'text' && (
            <TextInput
              question={current}
              value={currentAnswer}
              onChange={handleSetAnswer}
            />
          )}
        </div>

        {/* Footer — only shown for types that need explicit save */}
        {(needsSaveButton || !isChoiceLike) && (
          <DialogFooter className="flex-col sm:flex-row gap-2 items-stretch sm:items-center justify-between">
            <div className="flex gap-2">
              {step > 0 && (
                <Button variant="ghost" size="sm" onClick={handleBack}>
                  Назад
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={handleSkip} className="text-[color:var(--color-ink-muted)]">
                Пропустить
              </Button>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSave}
              disabled={!isAnswered}
            >
              {isLast ? 'Готово' : 'Сохранить'}
            </Button>
          </DialogFooter>
        )}

        {/* For choice/boolean — just a skip option */}
        {isChoiceLike && (
          <DialogFooter className="flex-col sm:flex-row gap-2 items-stretch sm:items-center justify-between">
            <div className="flex gap-2">
              {step > 0 && (
                <Button variant="ghost" size="sm" onClick={handleBack}>
                  Назад
                </Button>
              )}
              <Button variant="ghost" size="sm" onClick={handleSkip} className="text-[color:var(--color-ink-muted)]">
                Пропустить
              </Button>
            </div>
          </DialogFooter>
        )}
      </DialogContent>
    </Dialog>
  );
}
