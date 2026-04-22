# HR-Assist — Style Guide

## Aesthetic direction

Refined editorial meets data-confident tool. The product feels like a considered financial
planning interface published in a quality magazine — warm cream ground, deep charcoal ink,
a single cardinal-red accent that marks the one thing worth doing now. No purple gradients,
no pastel scatter, no startup bootstrap. Asymmetry and generous whitespace over symmetry.

---

## Typography

| Role        | Family              | Weight | Size token         | Letter-spacing |
|-------------|---------------------|--------|--------------------|----------------|
| Display/h1  | Fraunces (serif)    | 600    | `--text-display`   | −0.04em        |
| Heading h2  | Fraunces            | 600    | `--text-3xl`       | −0.03em        |
| Heading h3  | Fraunces            | 600    | `--text-2xl`       | −0.03em        |
| Subhead h4  | Fraunces            | 500    | `--text-xl`        | −0.02em        |
| Body        | Source Sans 3       | 400    | `--text-base`      | 0              |
| Small/meta  | Source Sans 3       | 400    | `--text-sm`        | 0              |
| Eyebrow     | Source Sans 3       | 700    | `--text-xs`        | +0.1em, ALLCAPS|
| Code/mono   | JetBrains Mono      | 400    | `--text-sm`        | 0              |

**Rules:**
- Headings always use `font-family: var(--font-display)`.
- Body copy and all UI text use `var(--font-body)`.
- Never mix heading font into button labels or chip text.
- Line-height: headings `--leading-tight` (1.1); body `--leading-normal` (1.55).

---

## Color

### Surfaces (light → raised)

| Token                    | Hex       | Use                                      |
|--------------------------|-----------|------------------------------------------|
| `--color-canvas`         | `#f5f2ec` | Page background — warm cream             |
| `--color-surface`        | `#fdfcf9` | Cards, panels                            |
| `--color-surface-raised` | `#ffffff`  | Inputs, dropdowns, popovers             |
| `--color-surface-muted`  | `#efece4` | Subtle fills, table alternates, tags     |

### Text

| Token                    | Hex       | WCAG on canvas | Use                    |
|--------------------------|-----------|----------------|------------------------|
| `--color-ink`            | `#1c1915` | 13.8:1 AAA     | Primary copy           |
| `--color-ink-secondary`  | `#5c5650` | 6.1:1 AA       | Supporting copy        |
| `--color-ink-muted`      | `#9b9590` | 3.5:1 (large)  | Placeholders, captions |

### Accent (one, sharp)

| Token                  | Hex       | Contrast on canvas | Use                                   |
|------------------------|-----------|--------------------|---------------------------------------|
| `--color-accent`       | `#c0392b` | 5.8:1 AA           | CTA buttons, links, active indicators |
| `--color-accent-hover` | `#a52d21` | 7.2:1 AAA          | Hover/pressed state                   |
| `--color-accent-subtle`| `#fdf0ee` | —                  | Chip backgrounds, selected states     |

**Rules:**
- The accent is used on **one primary action per screen**. Secondary actions use `variant="secondary"`.
- Never use accent as a decorative background fill for large areas.
- All text on `--color-accent` background must be `--color-on-accent` (#fff, 7.2:1 contrast).

### Semantic states

| State   | Ink token           | Subtle bg token          |
|---------|---------------------|--------------------------|
| Success | `--color-success`   | `--color-success-subtle` |
| Warning | `--color-warning`   | `--color-warning-subtle` |
| Danger  | `--color-danger`    | `--color-danger-subtle`  |
| Info    | `--color-info`      | `--color-info-subtle`    |

---

## Spacing

Base unit: 4px. Use multiples: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80.
Tokens: `--space-1` through `--space-20`.

**Rules:**
- Gap inside a component cluster (button+icon, label+input): 4–8px.
- Gap between component groups on a panel: 16–24px.
- Panel padding: 24px (`p-6` in Tailwind).
- Section separation: 32–48px vertical.

---

## Radii & Shadows

| Token             | Value  | Use                             |
|-------------------|--------|---------------------------------|
| `--radius-sm`     | 4px    | Tags, tiny chips, micro-buttons |
| `--radius-md`     | 8px    | Inputs, buttons, small cards    |
| `--radius-lg`     | 14px   | Application cards, modals       |
| `--radius-xl`     | 20px   | Main panels, large cards        |
| `--radius-full`   | 9999px | Pills, badges, filter chips     |

| Token           | Use                              |
|-----------------|----------------------------------|
| `--shadow-sm`   | Buttons, small chips             |
| `--shadow-md`   | Cards, panels                    |
| `--shadow-lg`   | Dialogs, popovers                |
| `--shadow-focus`| Focus ring (3px accent glow)     |

---

## Motion

| Token               | Value              | Use                         |
|---------------------|--------------------|-----------------------------|
| `--duration-fast`   | 120ms              | Hover colour, border change |
| `--duration-normal` | 220ms              | Appear/disappear            |
| `--duration-slow`   | 380ms              | Page transitions, reveals   |
| `--ease-out`        | cubic-bezier(0.22,1,0.36,1) | Enter |
| `--ease-in-out`     | cubic-bezier(0.4,0,0.2,1)   | Reorder|

**Rules:**
- One orchestrated entry animation per route (stagger-children). Not per-card.
- `prefers-reduced-motion`: ALL animation durations collapse to 0.01ms via the global guard in `globals.css @layer base`. Never override this.
- Use `animate-fade-in` on page-level sections, `animate-scale-in` on dialogs.
- Collapsible open/close uses Radix data-state + CSS keyframes (`animate-slide-down` / `animate-slide-up`).

---

## Component anatomy

### Button

DO:
- One primary button per major action area.
- `variant="secondary"` for cancel/back.
- `variant="danger"` for destructive confirmations (inside a dialog, not inline).

DON'T:
- Two `variant="primary"` side by side.
- Use accent color directly via className — use variant prop.
- Omit `disabled` state on loading.

### Card

DO:
- `CardHeader` → `CardTitle` + `CardDescription` (optional).
- `CardContent` for body. `CardFooter` for actions.
- Nest at most 1 level (card within card = design smell).

DON'T:
- Pad inner content manually — use `CardContent` and `CardHeader`.
- Use Card as a list item; use a plain `<div>` with border tokens instead.

### Input / Textarea

DO:
- Always pair with `<Label>` linked via `htmlFor`/`id`.
- Show validation state with `aria-invalid` and a helper text below.

DON'T:
- Inline `style` for border/focus colours — the tokens handle this.
- Use placeholder text as a label.

### Collapsible

DO:
- Keep trigger text brief (noun + count): "Навыки — 14".
- Animate with `data-[state=open]:animate-slide-down` on `CollapsibleContent`.

DON'T:
- Nest collapsibles more than 1 level.
- Auto-open on route entry — collapsed is the default resting state.

### Dialog

DO:
- Always include `DialogTitle` + `DialogDescription` (screen-reader requirement).
- Primary action in `DialogFooter`, right-aligned.
- Destructive action: `variant="danger"`, placed left of cancel.

DON'T:
- Open a dialog from inside another dialog.
- Use `DialogContent` for informational toasts — use a lightweight `Badge` or inline message.
