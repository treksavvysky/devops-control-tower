# DCT Design System

**DevOps Control Tower (DCT)** is a command center for AI-assisted software delivery. Fuzzy intent becomes audited, deterministic work: tasks are submitted, validated against policy, executed by agents, proven with evidence, and gated by human review before anything lands. The dashboard is the human window into that pipeline — an operator console for monitoring agents, watching runs stream in, inspecting evidence packs, and making the final approve/reject call. Every screen answers one question: **is this work safe to ship?**

**Sources:** built from a written brand brief only (company description + style/mood/palette notes supplied in-project). No codebase, Figma file, or logo assets were provided. Icons are Lucide (see Iconography); fonts load from Google Fonts.

## Brand image

Mission control, flight-deck, operator-grade. Calm authority; precision without coldness. Trustworthy automation with a human hand on the final lever. High signal, zero noise. Dark-mode only.

**Avoid:** playful, pastel, skeuomorphic, corporate-beige, cluttered dashboards, neon cyberpunk excess. Nothing bounces, nothing shouts.

## Content fundamentals

- **Tone:** calm, declarative, operator-grade. Short sentences that state facts: "All 12 checks passed." "Awaiting human review." Never hype, never exclamation marks.
- **Voice:** the system reports; the human decides. UI copy is imperative for actions ("Approve & merge", "Reject run", "Request changes") and descriptive for state ("3 of 12 checks did not pass").
- **Casing:** sentence case for body, titles, and buttons ("Review queue", "Run task"). UPPERCASE reserved for the small tracked-label tier (statuses, metadata headers, stat labels).
- **Person:** second person sparingly; mostly subjectless system statements. No "we". Confirmations name consequences plainly: "This can't be undone."
- **IDs & code:** run IDs, hashes, branches, repos always in mono (`run_8f3ka92`, `sha:1f8c2ea`, `feat/billing-queue`).
- **Emoji:** never.
- **Numbers:** confident and specific — "98.2%", "12/12", "+1,180 −642" — tabular-nums.

## Visual foundations

- **Background:** near-black blue-gray `#0f1115` with barely-there radial ambient glows (blue top-left 8%, green bottom-right 6%). No imagery, no textures, no light mode.
- **Surfaces:** frosted glass — `rgba(25,28,36,.65)` + `backdrop-filter: blur(16px)`, 1px hairline border `rgba(255,255,255,.08)`, 16px radius, layered soft shadows (`--shadow-card` → `--shadow-raised` → `--shadow-overlay`). Inset wells `#0a0c10` for inputs, logs, code.
- **Color:** four accents, strictly semantic — blue #3b82f6 = action/running, green #10b981 = approved/passed, amber #f59e0b = pending/warning, red #ef4444 = rejected/failed. Never decorative. Accents appear as (a) 135° gradients on action buttons with faint matching glow, (b) 15% tints + 40% borders on badges/callouts, (c) raw color on icons, stat numbers, live dots.
- **Type:** Inter only. Headlines bold, tight-tracked (−0.025em), white-to-gray gradient fill (`--grad-headline` via background-clip). Body 15px/1.6 regular. Small 11px uppercase 0.08em-tracked labels. Stats 2.5rem bold in accent colors. JetBrains Mono for IDs/logs.
- **Radii:** 8px inputs · 12px buttons/nested panels · 16px cards/dialogs · pill badges.
- **Motion:** gentle fade-in on load (opacity + 6px rise, 400ms, `cubic-bezier(0.16,1,0.3,1)`); hover = −2px lift + raised shadow on interactive cards only; buttons brighten + glow on hover; pulse animation only on genuinely live dots. No bounce, spin, or scale-press.
- **Hover/press:** hover lightens (brightness 1.08 on gradients, `--surface-glass-2` on quiet elements); press states stay subtle — no shrink.
- **Borders & depth:** hairlines everywhere; `--border-strong` (14%) for focus/hover emphasis. Depth via blur + shadow layering, not elevation colors.
- **Layout:** fixed 240px glass sidebar, top bar with gradient-headline page title, content max 1280px, 4px spacing base.
- **Imagery:** none in-product. No illustrations were provided.

## Iconography

- **Set:** [Lucide](https://lucide.dev) line icons, 2px stroke, round caps — copied into `assets/icons/` (40 SVGs) and embedded in the `Icon` component (`components/icons/Icon.jsx`), which renders inline SVG with `currentColor`.
- No proprietary icon font or brand icon set was provided; Lucide is a **substitution** chosen for its operator-grade neutral stroke style. Flagged for review.
- Icons are always functional, colored via context (semantic accents for status, `--text-2/3` otherwise). No emoji, no unicode-as-icon, no hand-drawn SVG.
- **Logo:** none provided. Wordmark renders as plain type — a small "DCT" tile on the blue gradient + "Control Tower" in Inter 700 (see `guidelines/brand-wordmark.html`). Do not draw a logo.

## Index

- `styles.css` — global entry; imports everything in `tokens/` (colors, typography, spacing, effects, base).
- `tokens/` — all custom properties. Semantic aliases included (`--surface-card`, `--color-approved`, …).
- `assets/icons/` — Lucide SVGs.
- `guidelines/` — 16 specimen cards (Colors, Type, Spacing, Effects, Brand groups).
- `components/` — reusable primitives, namespace `DCTDesignSystem_a2ec41`:
  - `icons/` — **Icon**
  - `actions/` — **Button**, **IconButton**
  - `forms/` — **Input**, **Select**, **Checkbox**, **Radio**, **Switch**
  - `display/` — **Card**, **Badge**, **Tag**, **Stat**
  - `navigation/` — **Tabs**
  - `overlay/` — **Dialog**, **Toast**, **Tooltip**
- `ui_kits/dct_dashboard/` — the operator console (Overview, Review queue, Evidence pack), interactive `index.html`.
- `SKILL.md` — agent skill entry point.

### Intentional additions

- **Icon** — wrapper for the Lucide glyph set (no icon system was specified).
- **Stat** — big-number display named explicitly in the brand brief.
