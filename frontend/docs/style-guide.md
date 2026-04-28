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

---

## Strategy view (Phase 5.2) — `/strategy`

### Direction

Three blocks — match highlights, gap mitigations, cover letter editor — form **one continuous vertical flow**, not three sections in a tab or accordion. Visual separation is a hairline gradient rule (`BlockSeparator`), not a heading color change or a full-width divider. The eye travels straight down.

### Entry button on vacancy card (`/`)

The "Стратегия" button belongs in the **card action row** (`flex items-center gap-2 flex-wrap`) that already holds "Откликнуться", "Интересно", and "Не подходит". Place it **between "Откликнуться" and "Интересно"** as a `variant="secondary" size="sm"` button. It renders as a `<Link href={/strategy?resume_id=X&vacancy_id=Y}>` wrapped button, not a `<button onClick>`. This keeps it indexable and avoids a router.push cost. Do not add it as a primary button — "Откликнуться" stays primary.

```
[Откликнуться]  [Стратегия]  [Интересно +]  [Не подходит ✗]
```

### Token table

| Token                             | Value (oklch)         | Use                                              |
|-----------------------------------|-----------------------|--------------------------------------------------|
| `--color-strategy-match-rule`     | oklch(0.52 0.12 200)  | Left 3px border on highlight cards + ordinal chip |
| `--color-strategy-gap-rule`       | oklch(0.62 0.12 68)   | Left 3px border on gap cards + dot               |
| `--color-strategy-gap-surface`    | oklch(0.982 0.018 68) | Card background wash — amber, barely perceptible |
| `--color-strategy-gap-label`      | oklch(0.46 0.11 68)   | Gap eyebrow + requirement label text             |
| `--color-strategy-editor-surface` | oklch(0.995 0.008 80) | Cover letter textarea background — warm near-white |

Token scope rule: never use `--color-strategy-*` outside `StrategyView.tsx` and its sub-components.

### Block anatomy

#### Block 1 — Match highlights

```
[eyebrow: "Ваши аргументы"]
[h2: "Что совпадает"]
[sub-line: xs / ink-secondary]
Grid (auto-fit, minmax 300px, 1fr)
  ┌─ 3px teal rule ──────────────────────────────────────┐
  │  COMPANY · xs / mono / uppercase                01   │
  │  Role title · lg / display / ink                     │
  │  ╎ Quote line · base / body / ink-secondary          │
  │  у меня этого нет на самом деле · xs / underline     │
  └──────────────────────────────────────────────────────┘
```

- Grid uses `repeat(auto-fit, minmax(min(100%, 300px), 1fr))`. At 360px all three cards stack.
- On `lg` (≥ 960px) two cards share the first row and the third is alone — this is the auto-fit collapse behavior, not a forced layout. The calm single-column read at medium widths is preferred over forcing a 3-up at all times.
- Ordinal chip (`01`, `02`, `03`) is `font-mono font-bold text-xs` in `--color-strategy-match-rule` at 70% opacity. Positioned absolute, top-right of card. Screen readers skip it (`aria-hidden`).
- Quote uses a `<blockquote>` with a 2px left border in `--color-strategy-match-rule` and normal (not italic) font style. Keeps reading character without being typographically fussy.
- "у меня этого нет на самом деле" is a `<button type="button">` styled as a text link. `xs`, `--color-ink-muted`, underline. Hover lifts to `--color-ink-secondary`. No icon. Fires `onCorrectionEvent('highlight', index)`.

DO:
- Left rule width: exactly 3px (via `style={{ borderLeftWidth: '3px', borderLeftColor: 'var(--color-strategy-match-rule)' }}`).
- Use `text-[length:var(--text-lg)]` for role title inside a card — one step smaller than h2.

DON'T:
- Add a success badge or a checkmark decoration. Calm confidence, not celebration.
- Use accent red here — the teal rule is intentionally different from the page's primary accent.

#### Block 2 — Gap mitigations

```
[eyebrow: "Пробелы"]  (color: --color-strategy-gap-label)
[h2: "Как письмо это обходит"]
Grid (auto-fit, minmax 280px, 1fr)
  ┌─ 3px amber rule ─ amber wash bg ────────────────────┐
  │  ● Requirement text · sm / bold / gap-label          │
  │  Mitigation paragraph · base / body / ink-secondary  │
  │  у меня этого нет на самом деле · xs / underline     │
  └──────────────────────────────────────────────────────┘
```

- The amber wash (`--color-strategy-gap-surface`) is the key visual distinction from highlight cards. The rule color differs (amber vs teal). No red, no warning icon — this must read as "recovery plan", not "problem report".
- Requirement text is `sm / bold / --color-strategy-gap-label`. The dot bullet (6px circle) shares the same color at 70% opacity.
- Mitigation paragraph uses `--leading-relaxed` (1.7) — slightly more open than normal body. It's the longest prose on the page after the cover letter.

DON'T:
- Use `--color-danger` or `--color-warning` for any gap element. The amber is pre-softened (`oklch(0.62 0.12 68)` vs `--color-warning` at `oklch(0.60 0.14 70)`).
- Display more than 2 gap cards. The constraint is aesthetic — more would tip the block from "recovery" to "rejection".

#### Block 3 — Cover letter editor

```
[eyebrow: "Сопроводительное письмо"]
[h2: "Черновик письма"]
[description: sm / ink-secondary]

┌── editor surface (--color-strategy-editor-surface) ────┐
│  <textarea>                                            │
│   font: body / lg / leading-relaxed                    │
│   padding: space-6                                     │
│   min-height: 280px                                    │
├── ruler (surface-muted bg, border-top) ────────────────┤
│  [N символов осталось · mono xs]  [N / 1200 · mono xs] │
└────────────────────────────────────────────────────────┘

[Button variant="primary" size="lg" : "Скопировать"]
[Link : "Открыть вакансию на источнике ↗"]
```

Typography rules for the editor:
- `font-size: var(--text-lg)` — one step above body. Makes the text feel like something being written, not filled in.
- `line-height: var(--leading-relaxed)` (1.7) — matches long-form writing tools.
- No padding inside the card header — the textarea IS the surface. The editor surface token gives the faintest warm tint to distinguish from page canvas.
- The ruler bar (char counter) sits flush at the bottom inside the card. Background `--color-surface-muted`, 1px border-top.
- Counter turns `--color-danger` + `font-bold` when over 1200 chars. `aria-live="polite"` on the counter span.

CTA row:
- "Скопировать" is the single primary button on the page. `size="lg"` for weight. Disabled when over limit.
- "Открыть вакансию на источнике ↗" is a secondary `<a>` link, `sm / font-semibold / ink-secondary / underline`. Never a Button — it's navigation, not action.
- The two sit in a `flex items-center gap-4 flex-wrap` row. On 360px the link wraps below.

### Block separator

`BlockSeparator` is a 1px `<div>` with a `linear-gradient` from transparent → `--color-border` → transparent. It creates breathing room between the three blocks without adding visual weight. Never use `<hr>` (default browser styling varies). No top/bottom margin on the separator — the parent grid gap (`--space-10`) provides all spacing.

### Motion

All three blocks carry `animate-fade-in` inside the `stagger-children` grid. The parent `stagger-children` stagger gives the template-mode notice → heading → highlights → gaps → editor a sequential reveal at 60ms intervals. This is the one orchestrated motion on the page — no per-card hover animations.

### Mobile (360px)

- All three card grids collapse to single column via `auto-fit + minmax(min(100%, NNNpx), 1fr)`.
- Ordinal chips remain visible.
- Editor textarea's `min-height: 280px` holds — do not reduce below 200px even on tiny screens.
- CTA link wraps below "Скопировать" in the flex row.
- `--space-10` gap between blocks stays; do not tighten to `--space-6` on mobile — the editorial rhythm depends on it.

---

## Editable pills — roles & domains sidebar widget

### Aesthetic direction

The pill groups live inside the sidebar (`<aside>`) on the main `/` page. The visual language is deliberately calm: auto-detected values are near-invisible gray chips that occupy almost no visual weight, while user-pinned values snap to the brand accent (cardinal red) — making the user's intentional choices read as the dominant signal. The widget never fights with the vacancy feed.

### Token table

| Token | Value | Semantic role |
|---|---|---|
| `--color-pill-auto-bg` | oklch(0.94 0.008 240) | Auto-pill background — faint cool-gray tint |
| `--color-pill-auto-fg` | oklch(0.30 0.02 240) | Auto-pill text — deep, 9:1 contrast on bg |
| `--color-pill-auto-border` | oklch(0.80 0.018 240) | Auto-pill 1px solid border |
| `--color-pill-pinned-bg` | `var(--color-accent)` | Pinned-pill fill — cardinal red |
| `--color-pill-pinned-fg` | `var(--color-on-accent)` | Pinned-pill text — white, 7.2:1 contrast |
| `--color-pill-pinned-border` | `var(--color-accent)` | Pinned-pill border (matches fill) |
| `--color-pill-add-border` | oklch(0.72 0.018 240) | Dashed border for "+ добавить" button |
| `--color-pill-add-fg` | `var(--color-ink-secondary)` | Text inside "+ добавить" |
| `--color-pill-remove-icon` | oklch(0.60 0.02 240) | × in resting state — visually quiet |
| `--color-pill-remove-icon-hover` | oklch(0.20 0.02 240) | × on hover — sharp, high contrast |
| `--color-combobox-suggestion-bg` | `var(--color-surface-raised)` | Dropdown surface |
| `--color-combobox-suggestion-bg-hover` | oklch(0.96 0.012 240) | Hovered suggestion row |
| `--color-combobox-border` | `var(--color-border)` | Dropdown border |
| `--color-pill-popular-bg` | oklch(0.97 0.025 145) | "· часто" badge background |
| `--color-pill-popular-fg` | oklch(0.42 0.10 145) | "· часто" badge text |
| `--color-unsaved-indicator-fg` | `var(--color-accent)` | Unsaved dot (7px circle) next to group label |

### Anatomy

```
[Group label: РОЛИ ●]          ← ● = unsaved indicator (only when dirty)

[Backend Developer ×]  [Tech Lead ×]       ← pinned pills (accent fill)
[Software Architect ×]  [Data Engineer ×]  ← auto pills (gray)
[+ добавить]                               ← add-pill (dashed border)

[Group label: ДОМЕНЫ]

[FinTech ×]  [E-Commerce ×]   ← mix of pinned / auto
[+ добавить]
```

On click of "+ добавить", the pill is replaced by an inline combobox:

```
┌─[text input: "Prod Ma|"]──────[×]─┐
└──────────────────────────────────────┘
┌── dropdown (z-overlay) ──────────────┐
│  Product Manager          · часто    │  ← highlighted row
│  Project Manager                     │
│  Product Owner            · часто    │
│  Scrum Master                        │
│  Product Analyst                     │
└──────────────────────────────────────┘
```

### Pill sizing

| Property | Value |
|---|---|
| Height | 28px |
| Padding | 0 10px 0 12px (extra left for text breathing room, right for × button) |
| Border-radius | `--radius-full` (9999px) |
| Font size | `--text-sm` |
| Font weight | 400 (auto) / 600 (pinned) |
| Remove icon size | 16×16px circle button, font-size 14px |

### Combobox sizing

| Property | Value |
|---|---|
| Input height | 36px |
| Dropdown max-height | 240px (overflow-y: auto) |
| Suggestion row height | 32px |
| Dropdown z-index | `var(--z-overlay)` |
| Shadow | 0 4px 16px 8% ink tint |

### Motion

| Animation | Class | Duration | Trigger |
|---|---|---|---|
| Pill enter | `animate-pill-in` | `--duration-fast` (120ms) | Pill added to DOM |
| Pill exit | `animate-pill-out` | `--duration-fast` (120ms) | Removal button clicked |

Both keyframes are in `globals.css @layer utilities`. `prefers-reduced-motion` guard collapses all durations to `0.01ms` automatically — no extra work needed.

The exit animation collapses `max-width` from 200px → 0 simultaneously with `opacity` and `scale` so the surrounding pills close the gap smoothly. Use `overflow: hidden; white-space: nowrap` on the exiting element.

### Disabled / loading state

When a save is in flight, set `opacity: 0.42; pointer-events: none` on the entire group container (both pill rows and add-button). Do NOT disable individual pills — the whole group becomes non-interactive as a unit.

### Empty state

When the user has no resume yet, render an italic `text-sm text-ink-muted` sentence in place of the pill row:

> Загрузите резюме, чтобы система предложила роли

No illustration, no button. The upload affordance is already above this widget in the sidebar.

### DO / DON'T

DO:
- Render auto pills with `font-weight: 400` and a gray surface — they are suggestions, not decisions.
- Render pinned pills with `font-weight: 600` and the full accent fill — these are the user's choices.
- Announce pill removal to screen readers via `aria-label="Удалить {value}"` on the × button.
- Keep the combobox input focused (`autoFocus`) when it opens; close on Esc.

DON'T:
- Use `--color-accent` directly on the auto-pill — only pinned pills use accent fill.
- Add hover background on the pill chip itself (only the × changes on hover).
- Animate the group label or the "+добавить" button — only the pill chips animate.
- Show the unsaved dot on initial page load — only show after the user makes a change.
