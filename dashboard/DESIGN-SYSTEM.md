# DCT Design System

The dashboard implements the **DCT Design System**, authored in Claude Design
(claude.ai/design project "DCT Design System") and ported into this codebase.
A verbatim copy of the source project lives in `design-reference/` (read-only;
excluded from ESLint) — treat it as the upstream spec when porting new pieces.

**Living style guide:** run the dashboard and open [`/design`](http://localhost:3000/design).

## Structure

| Layer | Location | What it is |
|---|---|---|
| Tokens | `src/styles/tokens/*.css` | Colors, typography, spacing, effects, base — copied from the design project |
| Component CSS | `src/styles/dct-components.css` | `.dct-*` classes; hover/focus in CSS so server components work |
| React components | `src/components/ui/` | Typed ports of the 16 design-system components |
| Icons | `src/components/icons/` | `Icon` + 40 embedded Lucide glyphs (`icon-data.ts`, generated from SVGs) |
| Domain mapping | `src/lib/status.ts` | CWOM status/verdict → badge status |
| Style guide | `src/app/design/` | Renders every token and component |

## Principles (from the design project's readme)

1. **Mission-control tone.** Calm, declarative, operator-grade copy. Sentence
   case everywhere; UPPERCASE only for the small tracked-label tier. No emoji,
   no exclamation marks. IDs/hashes/branches always in mono.
2. **Accents are strictly semantic, never decorative.** Blue = action/running,
   green = approved/passed, amber = pending/warning, red = rejected/failed.
   They appear three ways: 135° gradients on action buttons, 15% tints with
   40% borders on badges/callouts, raw color on icons/stats/live dots.
3. **Statuses render through `StatusBadge`.** The CWOM → badge mapping lives in
   `src/lib/status.ts`; don't hand-pick badge colors for a status.
4. **Motion is calm and opt-in.** Fade-in on load; −2px hover lift only on
   interactive cards; pulse only on genuinely live dots. Nothing bounces.
5. **Tokens are the source of truth.** No hard-coded hex/px in components —
   reference `--accent-*`, `--space-*`, `--radius-*`, `--shadow-*`.
6. **Dark mode only.**

## Key tokens

- Backgrounds: `--bg-0` (app), `--bg-inset` (wells/logs), `--surface-glass` /
  `--surface-glass-2` (frosted panels over `--blur-glass`)
- Text: `--text-1` / `--text-2` / `--text-3`
- Accents: `--accent-{blue,green,amber,red}` with `--tint-*` (15% fills),
  `--line-*` (40% borders), `--grad-{blue,green,red}` (button gradients)
- Semantic aliases: `--color-running`, `--color-approved`, `--color-pending`,
  `--color-rejected`, `--surface-card`
- Type scale: `--text-xs` (11px labels) → `--text-2xl` (40px stats); fonts via
  `--font-sans` (Inter) and `--font-mono` (JetBrains Mono), self-hosted with
  `next/font` in `layout.tsx`
- Radii: 8px inputs · 12px buttons · 16px cards (signature) · pill badges
- Shadows: `--shadow-card` → `--shadow-raised` → `--shadow-overlay`;
  glows `--glow-{blue,green,red}`

## Components

All exported from `@/components/ui`; `Icon` from `@/components/icons/Icon`.

- **`Button`** — `variant`: `primary | success | danger | secondary | ghost`;
  `size`: `sm | md | lg`; `icon` (Lucide name); `href` renders a Next `Link`; `block`.
- **`IconButton`** — square glass button; `icon`, required `label`,
  `variant`: `glass | ghost | danger`.
- **`Badge`** — `status`: `running | approved | pending | rejected | neutral`;
  `dot`, `pulse` (live states only).
- **`StatusBadge`** — pass any CWOM status/verdict/decision string.
- **`Card`** — glass panel; `title` / `subtitle` / `action` header slots;
  `interactive` for hover lift; `padding` (CSS value).
- **`Stat`** — big-number metric; `accent`: `blue | green | amber | red | neutral`.
- **`Tag`** — neutral metadata chip; `icon`, `mono`, `onRemove`. Use Badge when
  the value carries status.
- **`Input` / `Textarea` / `Select`** — inset dark wells, blue focus ring;
  `label`, `icon`, `error`, `mono`.
- **`Checkbox` / `Radio` / `Switch`** — controlled form controls (client components).
- **`Tabs`** — underline tabs with optional counts; controlled or uncontrolled.
- **`Dialog`** — modal on a heavy-blur scrim; `footer` action row.
- **`Toast`** — `kind`: `info | success | warning | error`; also works inline as a callout.
- **`Tooltip`** — CSS hover/focus tooltip; `side`: `top | bottom`.
- **`Icon`** — `name` (typed, 40 Lucide glyphs), `size`, `strokeWidth`.
- App helpers: **`PageHeader`** (gradient headline + crumb + actions),
  **`EmptyState`**, **`NavLink`** (sidebar item with icon + count badge).

## Syncing with the Claude Design project

The design project is upstream. To pull changes: fetch updated files with the
DesignSync tool into `design-reference/`, then port the diff into
`src/styles/` / `src/components/` following the existing conventions (inline
`useState` hover in the source becomes CSS `:hover` / `:focus-visible` here).
Regenerate icons with `node scratchpad/gen-icons.mjs` equivalent (see
`src/components/icons/icon-data.ts` header) if the glyph set changes.

## API base URL

Pages call the backend through `API_BASE` from `src/lib/api.ts`
(`NEXT_PUBLIC_JCT_API_URL`, default `http://127.0.0.1:8000`).
