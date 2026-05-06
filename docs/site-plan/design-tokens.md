# Design tokens

Lifted directly from `LINQ-Labs/src-service-poc/docs/training/assets/styles.css` — the canonical LINQ-branded theme used in the SRCS reference site. Tokens are reused verbatim so future maintainers familiar with one site recognise the other.

> "Derived from app.dev.erplinq.com visual language: dark teal sidebar/header, LINQ teal primary accent, orange flame reserved for the logo mark, white cards on soft off-white, subtle borders, minimal shadow." — header comment in `styles.css`

## Color

```css
/* Brand */
--color-brand-dark:        #134e5a;   /* header bg */
--color-brand-dark-hover:  #1f6a7b;
--color-primary:           #0f8a9c;   /* LINQ teal — links, accents, active states */
--color-primary-hover:     #0b6d7e;
--color-primary-tint:      #e0f2f4;   /* pale teal callouts */
--color-accent-flame:      #f97316;   /* LINQ orange — logo only */
--color-accent-flame-hi:   #fb923c;

/* On-dark foregrounds */
--color-on-dark:           #ffffff;
--color-on-dark-muted:     rgba(255, 255, 255, 0.78);
--color-on-dark-subtle:    rgba(255, 255, 255, 0.55);
--color-on-dark-divider:   rgba(255, 255, 255, 0.18);

/* Neutrals */
--color-bg:                #f7f8fa;
--color-surface:           #ffffff;
--color-surface-alt:       #f1f5f9;
--color-text:              #0f172a;
--color-text-muted:        #475569;
--color-text-subtle:       #94a3b8;
--color-border:            #e2e8f0;
--color-border-strong:     #cbd5e1;
--color-code-bg:           #f1f5f9;
--color-code-border:       #e2e8f0;

/* Callouts */
--color-callout-bg:        var(--color-primary-tint);
--color-callout-border:    var(--color-primary);
--color-warn-bg:           #fef3c7;
--color-warn-border:       #f59e0b;
--color-selfcheck-bg:      #ecfdf5;
--color-selfcheck-border:  #10b981;
```

**Brand rule:** flame orange is for the logo only. Primary CTAs use `--color-primary` (teal). The flame appears in the brand lockup and on the Hero call-to-action card.

## Typography

```css
--font-body: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
--font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
```

Inter weights loaded: 400 / 500 / 600 / 700 / 800. Loaded via Google Fonts with `font-display: swap`; site-build will subset to Latin only at deploy time.

| Token | Size | Line | Weight | Letter |
|---|---|---|---|---|
| Body | 16 px | 1.65 | 400 | — |
| Lede | 19 px | 1.55 | 400 | — |
| h1 (hero) | 44 px | 1.1 | 800 | -0.02em |
| h1 (chapter) | 40 px | 1.15 | 800 | -0.015em |
| h2 | 28 px | 1.25 | 700 | -0.015em |
| h3 | 20 px | 1.3 | 700 | — |
| h4 | 16 px | — | 600 | — |
| Eyebrow | 12 px | — | 700 | 0.08–0.1em (uppercase) |
| Code inline | 0.9em | — | 400 | — |
| Code block | 13.5 px | 1.55 | 400 | — |

## Layout

```css
--maxw-reading: 820px;   /* article body */
--maxw-wide:    1200px;  /* header, nav, gallery */
--radius-sm:    6px;
--radius:       8px;
--radius-lg:    12px;
```

- Container horizontal padding: 24 px.
- Section spacing: 40–80 px vertical between major regions, 24–36 px within.
- Vertical rhythm: soft 4 / 8 / 16 / 24 / 36 / 52 / 64 grid.

## Component vocabulary

Astro component names mirror the reference-site CSS class names so the two stay legible to one set of maintainers.

| Component | Reference class | Purpose |
|---|---|---|
| `SiteHeader` | `.site-header` | Sticky dark-teal top bar with brand lockup and breadcrumb |
| `BrandLockup` | `.brand` | Flame SVG + "LINQ" wordmark + divider + product name |
| `Hero` | `.hero` | Display heading + lede + bottom border |
| `ChapterHeader` | `.chapter-header` | Eyebrow + h1 + lede for inner pages |
| `PrimaryCard` | `.primary-card` | Dark-teal CTA card with flame-orange button (used for top-level features) |
| `DocList` / `DocItem` | `.doc-list` / `.doc` | White card list with bold title, mono path, muted description |
| `Callout` | `.callout` (+ `.warn`, `.self-check`) | Three coloured note variants |
| `Pre` / `Code` | `pre`, `code` | Dark code blocks, light inline code |
| `Table` | `table` | White surface with striped header, rounded outer |
| `Breadcrumb` | `.breadcrumb` | Top-right of header |
| `SiteFooter` | `.site-footer` | Single-line attribution + source link |
| `PersonaPivot` | new | Hackathon-site addition — four hero pills routing to anchored persona bands |
| `TldrCard` | new | TL;DR tier callout (3-bullet summary on outcome / pillar pages) |
| `OverviewBlock` | new | Overview tier wrapper |
| `DeepDiveExpander` | new | Collapsible Deep-dive tier (`<details>`) or "Read deep dive →" link |
| `OutcomeCard`, `DecisionCard`, `AgentCard` | new | Domain cards used in galleries |
| `RightRailToc` | new | Desktop right-rail TOC; collapsible at mobile |

## Motion

- Card hover: `transform: translateY(-2px)` + teal-tinted shadow `0 8px 24px rgba(19, 78, 90, 0.25)`; transition `0.15s ease`.
- Doc-list hover: background swap to `--color-surface-alt`; transition `0.15s ease`.
- Smooth scroll: `html { scroll-behavior: smooth }`.
- `prefers-reduced-motion: reduce` — disable `translateY` and shadow transitions; keep the colour change.

## Accessibility targets

- WCAG 2.1 AA on every token pair (verify on first build with axe). Most pairs already meet AA: e.g. `--color-text` (`#0f172a`) on `--color-bg` (`#f7f8fa`) is 16.6 : 1.
- Visible focus rings on every interactive element (no `outline: none`). Use `outline: 2px solid var(--color-primary)` with `outline-offset: 2px`.
- Semantic landmarks: `<header>`, `<nav>`, `<main>`, `<aside>`, `<footer>`.
- Keyboard-navigable persona pivot — arrow-key cycling on the hero pills, focus-visible state on every option.
- Skip-link to `#main` as the first focusable element.
- All decorative SVGs marked `aria-hidden="true"`; every meaningful image gets an `alt`.

## Responsive breakpoints

Mobile-first. Three breakpoints:

```css
@media (min-width: 640px)   { /* tablet portrait — two-column cards */ }
@media (min-width: 960px)   { /* desktop — right-rail TOC, full nav */ }
@media (min-width: 1200px)  { /* wide — max content width */ }
```

Mobile (under 640 px) collapses the sticky header brand to flame + wordmark only, hides the breadcrumb's middle segments behind a "…" affordance, and stacks all cards single-column.

## Print stylesheet

A minimal `print.css` for `/outcomes/<slug>/` and `/about/`:

- Hide nav, footer, persona pivot, deep-dive expanders.
- Widen reading column to `100%` (drop the 820 px cap).
- Black-on-white type; no background colours.
- Show URLs after links in parentheses (`a[href^="http"]:after { content: " (" attr(href) ")"; }`).
- Page-break hints on `h2` (avoid breaking after) and on `figure` (keep with caption).

## Pointers

- Source stylesheet: `https://github.com/LINQ-Labs/src-service-poc/blob/main/docs/training/assets/styles.css`.
- Architecture, sitemap, milestones: [02-architecture.md](02-architecture.md).
- Discovery context: [01-discovery.md](01-discovery.md).
