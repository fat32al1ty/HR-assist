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

---

## Phase 5.0 token additions (audit screen)

### Status severity tokens — `ResumeQualityCard`

Three dedicated status tokens map to `QualityIssueSeverity` values. These are **intentionally separate** from the global `--color-{success,warning,danger}` aliases so the audit quality panel can be restyled independently.

| Token                        | Value (oklch)          | Use                                     |
|------------------------------|------------------------|-----------------------------------------|
| `--color-status-info`        | oklch(0.50 0.14 250)   | `info` severity — calm blue dot + label |
| `--color-status-info-subtle` | oklch(0.96 0.03 250)   | `info` row background                   |
| `--color-status-warn`        | oklch(0.58 0.14 68)    | `warn` severity — amber                 |
| `--color-status-warn-subtle` | oklch(0.97 0.04 68)    | `warn` row background                   |
| `--color-status-error`       | var(--destructive)     | `error` severity — shares accent red    |
| `--color-status-error-subtle`| 10% destructive tint   | `error` row background                  |

**Rule:** Never use `--color-status-*` as button colours or backgrounds on large areas. Severity dot + label only.

### Salary band gradient tokens — `MarketSalaryCard`

| Token                      | Value (oklch)        | Use                                      |
|----------------------------|----------------------|------------------------------------------|
| `--color-salary-band-low`  | oklch(0.80 0.10 145) | p25 end of track gradient (muted green)  |
| `--color-salary-band-mid`  | oklch(0.72 0.13 85)  | midpoint transition (warm amber)         |
| `--color-salary-band-high` | oklch(0.65 0.16 50)  | p75 end of track gradient (deeper amber) |
| `--color-salary-band-peak` | oklch(0.55 0.18 50)  | Median marker + label text               |

**Rule:** The gradient goes left→right on a horizontal track. Do not reverse it. The p50 marker floats above the track at the calculated midpoint percentage.

### Skill gap bar token — `SkillGapsCard`

| Token                   | Value (oklch)        | Use                                                |
|-------------------------|----------------------|----------------------------------------------------|
| `--color-skill-gap-bar` | oklch(0.60 0.13 250) | Frequency bar fill for skills the user doesn't own |

Owned skills use `--color-success` for their bar (green = already have it). Missing skills use `--color-skill-gap-bar` (blue = market demand).

### Audit page layout rules

- **Top row** (Role + Salary): `grid-template-columns: repeat(auto-fit, minmax(340px, 1fr))`. Stacks to 1-col below ~720px.
- **Bottom row** (Skill gaps + Quality): same pattern, same breakpoint.
- **Hero salary figure**: `clamp(2.25rem, 5vw, 3.5rem)`, weight 700, tracking −0.04em. This is the editorial number that sells the product.
- **Questions banner**: appears above the page heading when `triggered_question_ids.length > 0`. Uses `--color-accent-subtle` background. Never blocks the main grid.
- **Template mode notice**: appears above the banner (if both are present), neutral `--color-surface-muted` background. Not alarming.
- **CTA**: single `Button variant="primary" size="lg"` at page bottom. One per page, as per the button rule.

### Onboarding modal (`QuestionsModal`)

- Uses standard `Dialog` + `DialogContent` — inherits `--shadow-lg`, `--radius-xl`.
- Step progress uses pill-shaped dots: active dot is wider (`w-4`) + accent colour; past dots are accent; future dots are muted surface.
- Choice options are pill buttons (`--radius-full`), selected state reuses `--color-accent-subtle` + `--color-accent` border.
- `number_range` uses native `<input type="range">` with `accent-[var(--color-accent)]` + a live `aria-live` readout.

---

## Anchor screen — `/` (slice 2.8.7)

Applied conventions (reference for 2.8.8):

### Workspace layout
`div.workspace` / `div.workspace-main` — grid retained via legacy CSS; `.stagger-children` class added for orchestrated entry.  All sections use `<Card>` with `CardHeader` + `CardContent`.

### Page-load reveal
Parent `div.workspace` has `stagger-children` applied. Each major section (sidebar, resume card, "Что ищу" card, matches card, archive cards) carries `animate-fade-in`. Stagger offsets: 0 / 60 / 120 / 180 / 240 / 300 ms. `prefers-reduced-motion` guard in `@layer base` collapses all durations to `0.01ms`.

### Drop-zone file input
File input is hidden (`sr-only`); wrapped in a `<label>` that acts as the full drop zone. Three visual states: default (`border-dashed border-border bg-surface-muted`), hover (`border-border-strong bg-surface-raised`), drag-over (`border-accent bg-accent-subtle`). `dragOver` React state drives the class switch.

### Collapsible chevron
All `CollapsibleTrigger` elements use `group` + `group-data-[state=open]:rotate-180` on the `▼` glyph. Duration is `duration-[var(--duration-fast)]`.

### Message / alert inline
Error and status messages use: `bg-warning-subtle text-warning border border-warning/25 rounded-md px-3 py-2 text-sm`. No `.message` legacy class.

### Match card
- Title: `font-display font-semibold text-xl tracking-tight`.
- Score + salary: right-aligned column, `font-mono text-sm`.
- "Почему показали": right-aligned trigger, `text-xs text-ink-muted`, chevron rotates on open.
- "Откликнуться": `Button variant="primary" size="sm"`. Like/dislike: `variant="ghost" size="sm"`.
- Source link: `ml-auto text-sm text-ink-muted hover:text-accent no-underline`.
- Card shadow: `shadow-sm` default, `shadow-md` on hover via `hover:shadow-md transition-shadow`.

### Inline messages removed
`.message`, `.panel-note`, `.empty-state` class references eliminated from `/`. Replaced with token-based inline styles or italic `text-ink-secondary text-sm` paragraphs.

### Legacy classes retained in globals.css (still used by other routes)
`.workspace`, `.workspace-main`, `.panel`, `.vacancy-tier-divider`, `.fit-grid`, `.fit-box`, `.resume-active-tag`, `.status`, `.match-reason`, `.match-salary`, `.salary-range-row`, `.progress-box`, `.progress-*`, `.curated-*`, `.fit-micro-btn`, `.radio-chip`, `.sources-box`. These will be purged in 2.8.8 when the last consumer is migrated.

---

## Track segmentation view (Phase 5.1)

### Direction

Three tracks form **one continuous vertical list**, not three pages. Visual rhythm flows downward. Differentiation is done by a 3px left border rule + a whisper-thin surface wash — not by large colored headers or icons. The user's eye reads track kind instantly from the left edge; it then moves right to the heading. No clutter in the middle.

### Track hierarchy

| Track     | Eyebrow (ru) | Left rule token               | Surface wash token                | Label color token              |
|-----------|--------------|-------------------------------|-----------------------------------|-------------------------------|
| `match`   | Точка        | `--color-track-match-rule`    | none (page canvas)                | `--color-track-match-label`   |
| `grow`    | Вырост       | `--color-track-grow-rule`     | `--color-track-grow-surface`      | `--color-track-grow-label`    |
| `stretch` | Стрейч       | `--color-track-stretch-rule`  | `--color-track-stretch-surface`   | `--color-track-stretch-label` |

- `match` is **calm**: no background, neutral rule, neutral label. The default state that needs no explanation.
- `grow` has a **blue left rule** + barely-perceptible blue surface tint. Signals "reach" without alarm. Blue is already used for status-info across the system, making it a familiar directional signal.
- `stretch` has a **warm amber rule** + amber surface wash. Reads as aspirational — the same hue as `--color-warning` but at much lower chroma, so it never reads as an error. Paired with the amber CTA button it gives stretch its own identity within the single list.

### Section header anatomy

```
[3px rule]  [eyebrow — xs / bold / tracking / uppercase / labelColor]
            [section title — 2xl / display font / ink]       [count pill] [▼]
            [gap summary — sm / italic / ink-muted]   (always visible, not collapsible)
```

- Eyebrow text is short Russian noun: "Точка", "Вырост", "Стрейч". Never spell out the English track name.
- Section title uses `--font-display` (Fraunces), `text-2xl`, tracking `-0.03em`. Same as h3 in the type scale.
- Counter pill: `font-mono text-xs font-semibold rounded-full border`. Background + text = the track's own label color at low opacity (not the global accent).
- Chevron `▼` rotates 180° via `group-data-[state=open]:rotate-180 transition-transform`. Duration `--duration-fast`.
- The gap summary line sits **below the header, above the collapsible content**. Always visible (not hidden when collapsed) so the user gets the key fact without opening the section.

### Collapsible behavior

- `match` opens by default on page load. `grow` and `stretch` start collapsed.
- Open/close uses Radix `<Collapsible>` with `data-[state=open]:animate-slide-down` on `CollapsibleContent`. Matches the existing pattern from 2.8.7.
- No nesting — one collapsible level per track.

### Vacancy cards inside a track

The card anatomy is **unchanged** from 2.8.7. The track wrapper does not alter card styling. Cards inherit `bg-surface border-border rounded-lg shadow-sm hover:shadow-md`.

### Stretch CTA button

```
[amber bg] [amber border]  "Показать N вакансий с мягкими требованиями"
                            sub-line: "Где работодатель пишет «будет плюсом»…"
```

- Uses `--color-track-stretch-cta-bg`, `--color-track-stretch-cta-border`, `--color-track-stretch-cta-ink`.
- Full-width, `rounded-lg`, left-aligned text (reads as a link-row, not a submit button).
- Rendered inside the collapsible body, after the vacancy list.
- Only shown when `softer_subset_count > 0`. Absent if 0 or null.

### Empty state

One italic sentence per track in `text-sm text-ink-muted`. No illustration. No button (the search trigger lives elsewhere on the page).

### Mobile (≤ 360px)

- Left rule stays. Surface tint stays.
- Section heading wraps normally — Fraunces at `text-2xl` handles long Russian words cleanly.
- Count pill and chevron wrap to the same flex row as the heading; they shrink but never disappear.
- Gap summary truncates at 2 lines (`line-clamp-2`). Full text available via `title` attribute.

### Token rule

Never use `--color-track-*` tokens outside the track section header and CTA. Do not apply them to vacancy cards, status badges, or global navigation.
