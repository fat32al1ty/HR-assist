'use client';

/**
 * PillsEditor — editable role/domain pill group with inline combobox.
 *
 * Auto vs Pinned distinction is VISUAL ONLY:
 *   - "auto"   = value is in `autoDetected` prop (came from resume analysis)
 *   - "pinned" = value is NOT in `autoDetected` (user-added or outside analysis)
 * There is no "promote" action: the determination is purely based on set membership.
 * This keeps the component stateless w.r.t. provenance.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchSuggestions, type Suggestion } from '@/lib/preferences';

export type PillsEditorProps = {
  label: string;
  values: string[];
  autoDetected?: string[];
  type: 'role' | 'domain';
  maxItems: number;
  isDirty: boolean;
  isSaving: boolean;
  onChange: (next: string[]) => void;
  emptyHint?: string;
  token: string | null;
};

// ─── Pill sub-components ────────────────────────────────────────────────────

type AutoPillProps = {
  label: string;
  removing: boolean;
  onRemove: () => void;
};

function AutoPill({ label, removing, onRemove }: AutoPillProps) {
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
        whiteSpace: 'nowrap',
        cursor: 'default',
        userSelect: 'none',
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
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color =
            'var(--color-pill-remove-icon-hover)';
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLButtonElement).style.color =
            'var(--color-pill-remove-icon)';
        }}
        onClick={onRemove}
      >
        ×
      </button>
    </span>
  );
}

type PinnedPillProps = {
  label: string;
  removing: boolean;
  onRemove: () => void;
};

function PinnedPill({ label, removing, onRemove }: PinnedPillProps) {
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
        background: 'var(--color-pill-pinned-bg)',
        color: 'var(--color-pill-pinned-fg)',
        border: '1px solid var(--color-pill-pinned-border)',
        fontSize: 'var(--text-sm)',
        fontWeight: 600,
        lineHeight: 1,
        whiteSpace: 'nowrap',
        cursor: 'default',
        userSelect: 'none',
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
          transition:
            'background var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out)',
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
        onClick={onRemove}
      >
        ×
      </button>
    </span>
  );
}

// ─── Combobox ───────────────────────────────────────────────────────────────

type ComboboxProps = {
  type: 'role' | 'domain';
  token: string | null;
  existingValues: string[];
  onAdd: (value: string) => void;
  onClose: () => void;
};

const DEBOUNCE_MS = 200;

function Combobox({ type, token, existingValues, onAdd, onClose }: ComboboxProps) {
  const [query, setQuery] = useState('');
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [activeIndex, setActiveIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const fetchAndSet = useCallback(
    (q: string) => {
      if (abortRef.current) {
        abortRef.current.abort();
      }
      const controller = new AbortController();
      abortRef.current = controller;
      fetchSuggestions(type, q, token, controller.signal)
        .then((items) => {
          // filter already-added values (case-insensitive)
          const lower = existingValues.map((v) => v.toLowerCase());
          setSuggestions(items.filter((s) => !lower.includes(s.value.toLowerCase())));
          setActiveIndex(-1);
        })
        .catch(() => {
          // ignore abort errors
        });
    },
    [type, token, existingValues]
  );

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const q = e.target.value;
    setQuery(q);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    if (q.trim()) {
      debounceRef.current = setTimeout(() => {
        fetchAndSet(q.trim());
      }, DEBOUNCE_MS);
    } else {
      setSuggestions([]);
      setActiveIndex(-1);
    }
  }

  function commitValue(value: string) {
    const trimmed = value.trim();
    if (!trimmed) return;
    const lower = existingValues.map((v) => v.toLowerCase());
    if (!lower.includes(trimmed.toLowerCase())) {
      onAdd(trimmed);
    }
    onClose();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Escape') {
      onClose();
      return;
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1));
      return;
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, -1));
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      if (activeIndex >= 0 && activeIndex < suggestions.length) {
        commitValue(suggestions[activeIndex].value);
      } else {
        commitValue(query);
      }
    }
  }

  return (
    <div style={{ position: 'relative', width: 260, flexShrink: 0 }}>
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
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Введите и выберите…"
          aria-label="Введите значение"
          aria-autocomplete="list"
          aria-controls="pills-combobox-listbox"
          aria-activedescendant={
            activeIndex >= 0 ? `pills-combobox-option-${activeIndex}` : undefined
          }
          style={{
            flex: 1,
            border: 'none',
            background: 'transparent',
            outline: 'none',
            fontSize: 'var(--text-sm)',
            color: 'var(--color-ink)',
            minWidth: 0,
          }}
        />
        <button
          type="button"
          aria-label="Закрыть"
          onClick={onClose}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            color: 'var(--color-ink-muted)',
            fontSize: 16,
            lineHeight: 1,
            padding: 0,
            flexShrink: 0,
          }}
        >
          ×
        </button>
      </div>

      {/* Dropdown */}
      {suggestions.length > 0 && (
        <div
          id="pills-combobox-listbox"
          role="listbox"
          aria-label="Варианты"
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
            zIndex: 50,
          }}
        >
          {suggestions.map((s, i) => (
            <div
              key={s.value}
              id={`pills-combobox-option-${i}`}
              role="option"
              aria-selected={i === activeIndex}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                height: 32,
                padding: '0 12px',
                fontSize: 'var(--text-sm)',
                color: 'var(--color-ink)',
                background:
                  i === activeIndex
                    ? 'var(--color-combobox-suggestion-bg-hover)'
                    : 'transparent',
                cursor: 'pointer',
                gap: 8,
              }}
              onMouseEnter={() => setActiveIndex(i)}
              onMouseLeave={() => setActiveIndex(-1)}
              onMouseDown={(e) => {
                // prevent blur on input
                e.preventDefault();
                commitValue(s.value);
              }}
            >
              <span>{s.value}</span>
              {s.frequency > 1 && (
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
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── Main component ─────────────────────────────────────────────────────────

export default function PillsEditor({
  label,
  values,
  autoDetected = [],
  type,
  maxItems,
  isDirty,
  isSaving,
  onChange,
  emptyHint,
  token,
}: PillsEditorProps) {
  const [comboboxOpen, setComboboxOpen] = useState(false);
  const [removingIndex, setRemovingIndex] = useState<number | null>(null);

  const autoSet = new Set(autoDetected.map((v) => v.toLowerCase()));

  function isAuto(value: string): boolean {
    return autoSet.has(value.toLowerCase());
  }

  function handleRemove(index: number) {
    setRemovingIndex(index);
    // wait for animation to complete before actually removing
    setTimeout(() => {
      setRemovingIndex(null);
      onChange(values.filter((_, i) => i !== index));
    }, 150);
  }

  function handleAdd(value: string) {
    onChange([...values, value]);
  }

  const atLimit = values.length >= maxItems;

  return (
    <div
      style={{
        opacity: isSaving ? 0.6 : 1,
        pointerEvents: isSaving ? 'none' : 'auto',
        transition: 'opacity var(--duration-fast) var(--ease-out)',
      }}
    >
      {/* Group label */}
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
            textTransform: 'uppercase',
            color: 'var(--color-ink-muted)',
          }}
        >
          {label}
        </span>
        {isDirty && (
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
        )}
      </div>

      {/* Pills row */}
      {values.length === 0 && !comboboxOpen ? (
        emptyHint ? (
          <p
            style={{
              margin: 0,
              fontSize: 'var(--text-sm)',
              fontStyle: 'italic',
              color: 'var(--color-ink-muted)',
              lineHeight: 'var(--leading-normal)',
              marginBottom: 8,
            }}
          >
            {emptyHint}
          </p>
        ) : null
      ) : null}

      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 6,
          alignItems: 'center',
        }}
      >
        {values.map((value, i) =>
          isAuto(value) ? (
            <AutoPill
              key={value}
              label={value}
              removing={removingIndex === i}
              onRemove={() => handleRemove(i)}
            />
          ) : (
            <PinnedPill
              key={value}
              label={value}
              removing={removingIndex === i}
              onRemove={() => handleRemove(i)}
            />
          )
        )}

        {/* Add button or combobox */}
        {comboboxOpen ? (
          <Combobox
            type={type}
            token={token}
            existingValues={values}
            onAdd={handleAdd}
            onClose={() => setComboboxOpen(false)}
          />
        ) : atLimit ? (
          <span
            style={{
              fontSize: 'var(--text-xs)',
              color: 'var(--color-ink-muted)',
              fontStyle: 'italic',
            }}
          >
            Лимит: {maxItems}
          </span>
        ) : (
          <button
            type="button"
            aria-label={`Добавить в ${label}`}
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
              userSelect: 'none',
              whiteSpace: 'nowrap',
              transition:
                'border-color var(--duration-fast) var(--ease-out), color var(--duration-fast) var(--ease-out)',
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
            onClick={() => setComboboxOpen(true)}
          >
            + добавить
          </button>
        )}
      </div>
    </div>
  );
}
