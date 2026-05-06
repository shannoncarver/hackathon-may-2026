# 02 — Architecture

Hands-on design and tech plan for the showcase site. Discovery findings live in [01-discovery.md](01-discovery.md); design tokens in [design-tokens.md](design-tokens.md).

## Decisions

| # | Decision | Choice |
|---|---|---|
| 1 | Information architecture | Matrix: persona-pivot homepage + pillar content underneath |
| 2 | Tech stack | Astro 5.x with MDX |
| 3 | Deploy mechanism | GitHub Actions → Pages |
| 4 | Pillar structure | Hybrid — outcomes top-level, pillars as deep-dive |
| 5 | Repo visibility | Public; Pages URL: `https://shannoncarver.github.io/hackathon-may-2026/` |
| 6 | Voice | Polished but candid (per Decision 0010) |
| 7 | Authorship | I draft from existing artifacts, you edit |
| 8 | Interactivity (v1) | Defer — establish structure and flow first |

Open items deferred to v2 (not blocking v1 skeleton): custom domain, Pagefind / Lunr search, filterable galleries, embedded interactive demos, analytics, headshots, verified-metrics call-outs.

## 1. Information architecture

### Sitemap (v1 skeleton)

```
/                          Home — persona-pivot hero + outcome highlights
/outcomes/                 Top-level outcome cards (hybrid IA — outcomes lead)
/outcomes/<slug>/          One outcome story (TL;DR → Overview → Deep dive)
/how-it-works/             Architecture overview — entry to pillars
/how-it-works/knowledge/   Pillar 1 — Knowledge base
/how-it-works/repo/        Pillar 2 — Repo structure
/how-it-works/docs/        Pillar 3 — Documentation
/how-it-works/agents/      Pillar 4 — Agent definitions
/how-it-works/skills/      Pillar 5 — Skills management
/how-it-works/mcp/         Pillar 6 — MCP connector inventory
/decisions/                ADR explorer (16 records, list in v1; filterable in v2)
/decisions/<NNNN>-<slug>/  Single decision page
/agents/                   Agent gallery (9 agents)
/agents/<slug>/            Single agent page
/about/                    What this is, who built it, scope, contact
/demo/                     Demo narrative (v1 stub; embed video when recorded)
404                        Custom not-found
```

### Navigation model

- **Top nav (sticky, dark)**: Home · Outcomes · How it works · Decisions · Demo
- **In-page anchor nav** on every long page (right-rail TOC at desktop, collapsible at mobile).
- **Breadcrumb** in the header on inner pages.
- **Footer**: source-repo link, license, "what is this" one-liner.

### Persona-pivot homepage

The hero sits above four pivot pills:

```
[ I'm an exec ]   [ I'm a PM ]   [ I'm a builder ]   [ I'm just curious ]
```

Each pill scrolls to a tailored landing band on the same page (`#exec`, `#pm`, `#builder`, `#curious`) — no separate routes. Each band has:

- One-paragraph framing in the persona's vocabulary.
- 3 outcome cards routed to the relevant `/outcomes/<slug>/` pages.
- "Go deeper" link to `/how-it-works/` (builder/PM), `/decisions/` (engineer), or `/about/` (curious).

Single-page persona pivot keeps all content on one URL, avoids content duplication, and lets a curious exec scroll past their pill to read the engineer's framing — the hybrid IA in practice.

### Depth tiers

Each long-form page exposes three disclosure tiers:

1. **TL;DR** (3 bullets, always visible at top — teal-tint callout).
2. **Overview** (1 page, always visible below TL;DR — body text).
3. **Deep dive** (collapsible `<details>` or "Read deep dive →" link to source markdown).

Pages link out to authoritative `.md` in the repo for raw artifacts rather than duplicating.

### Stakeholder routing

| Persona | Lands at | Reads | Goes to |
|---|---|---|---|
| Exec | `/#exec` band on home | TL;DR + 3 outcomes | `/outcomes/<top-one>/` Overview |
| PM | `/#pm` band on home | "What we shipped" outcomes | `/how-it-works/` Overview tier |
| Engineer | `/#builder` band on home | Architecture entry | `/decisions/` + per-pillar Deep dive |
| Curious | `/#curious` band on home | "What is this" overview | `/about/` |

## 2. Content schema

Astro content collections, MDX-friendly. One example schema (lives in `site/src/content/config.ts`):

```ts
import { defineCollection, z } from 'astro:content';

const outcomes = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    slug: z.string(),
    type: z.enum(['outcome', 'pillar', 'decision', 'agent', 'skill']),
    status: z.enum(['shipped', 'in-progress', 'future']),
    pillar: z.string().optional(),
    order: z.number().default(99),
    summary_exec: z.string(),
    summary_pm:   z.string(),
    summary_eng:  z.string(),
    tldr: z.array(z.string()).length(3),
    outcomes: z.array(z.string()).default([]),
    lessons: z.array(z.string()).default([]),
    artifacts: z.array(z.object({ label: z.string(), href: z.string() })).default([]),
    team: z.array(z.object({ name: z.string(), role: z.string() })).default([]),
    next_steps: z.array(z.string()).default([]),
  }),
});

export const collections = { outcomes };
```

A worked example ships in **Milestone 2**: the "Three-layer LLM-wiki" outcome, drawn from `docs/pillars/1-knowledge-base.md` + Decision 0013 + `knowledge/SCHEMA.md`.

## 3. Tech & deploy plan

### Stack

- **Astro 5.x** (zero-JS by default, MDX, content collections, SSG).
- **No UI framework islands in v1** (option open for v2 if a particular widget needs it).
- **Vanilla CSS** with custom-properties (the design tokens) — no Tailwind, keep the cascade legible.
- **Pagefind** for v2 search.

### Repository layout

Site source lives in a top-level `site/` directory.

```
site/
├── astro.config.mjs
├── package.json
├── public/                    Static assets (favicon, og-image, brand SVG, .nojekyll)
├── src/
│   ├── content/
│   │   ├── outcomes/          MDX
│   │   ├── pillars/           MDX
│   │   ├── decisions/         Pulled at build from /docs/decisions/
│   │   ├── agents/            MDX
│   │   └── skills/            MDX
│   ├── components/            Astro components
│   ├── layouts/               BaseLayout, Article, Print
│   ├── pages/                 Routes
│   ├── styles/                tokens.css + global.css + print.css
│   └── lib/                   Helpers
└── tsconfig.json
```

**Decision-record sourcing.** Decision pages are built from `docs/decisions/*.md` at build time — single source of truth in `docs/decisions/`, site stays in sync automatically.

### Astro config

```js
// astro.config.mjs
import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://shannoncarver.github.io',
  base: '/hackathon-may-2026',
  integrations: [mdx(), sitemap()],
  output: 'static',
  trailingSlash: 'always',
});
```

`base: '/hackathon-may-2026'` is critical for `*.github.io/<repo>/` URLs — internal links must use Astro's `Astro.url` / `import.meta.env.BASE_URL` helpers.

### GitHub Actions deploy workflow

Lives at `.github/workflows/site-deploy.yml`:

```yaml
name: Deploy site to Pages
on:
  push:
    branches: [main]
    paths: ['site/**', '.github/workflows/site-deploy.yml', 'docs/decisions/**']
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: false
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20', cache: 'npm', cache-dependency-path: 'site/package-lock.json' }
      - run: npm ci
        working-directory: site
      - run: npm run build
        working-directory: site
      - uses: actions/upload-pages-artifact@v3
        with: { path: site/dist }
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

**One-time manual step**: in repo settings → Pages → Source, select "GitHub Actions". Documented in `03-handoff.md` once written.

### Performance budget

- Lighthouse ≥ 95 on Performance, Accessibility, Best Practices, SEO.
- Page weight ≤ 200 KB on first paint (HTML + CSS + critical font subset).
- Inter loaded with `font-display: swap`, subset for Latin only.
- All images `loading="lazy"`, modern formats, explicit width/height to prevent CLS.
- No third-party scripts in v1.

### Print stylesheet

A minimal `print.css` for `/outcomes/<slug>/` and `/about/` — exec audiences print things. Hides nav, footer, deep-dive expanders; widens reading column; black-on-white type.

## 4. Implementation milestones

Each milestone is independently demoable. **Pause for review after every milestone before starting the next.**

### Milestone 1 — Skeleton + design system + nav + persona-pivot homepage

- Scaffold `site/` with Astro 5 + MDX, `astro.config.mjs` with `base: '/hackathon-may-2026'`.
- Port design tokens to `src/styles/tokens.css` and `global.css`.
- Build core components: `SiteHeader`, `BrandLockup`, `Hero`, `PersonaPivot`, `PrimaryCard`, `DocList`, `Callout`, `SiteFooter`.
- Wire homepage with placeholder copy, persona pivot, three outcome stub cards.
- Wire top nav with empty-state inner pages.
- Add Actions deploy workflow.
- A11y axe pass; mobile viewport check at 375 px.

**Demoable as**: live URL with skim-grade homepage; nav works; persona-pivot scrolls; design system visible on placeholder content.

### Milestone 2 — One end-to-end outcome at all three depth tiers (template proof)

- Author "Three-layer LLM-wiki" outcome page using the content schema.
- Implement `TldrCard`, `OverviewBlock`, `DeepDiveExpander`.
- Pipeline `docs/pillars/1-knowledge-base.md` content into the Overview tier.
- Link to Decision 0013 and `knowledge/SCHEMA.md` source on github.com.
- Add the matching pillar page `/how-it-works/knowledge/`.
- Print stylesheet.

**Demoable as**: one fully-populated outcome page with TL;DR / Overview / Deep dive; one fully-populated pillar; print preview clean.

### Milestone 3 — Remaining pillars + decision explorer + agent gallery

- Generate `/how-it-works/<pillar>/` for the other five pillars from existing pillar briefs.
- Build `/decisions/` index that pulls from `docs/decisions/` at build time.
- Build `/agents/` gallery with cards for the 9 agents (sourced from `docs/agent/`).
- Add `/about/` page.

**Demoable as**: complete site skeleton, all sections reachable, content on every page even if some sections are still placeholders.

### Milestone 4 — Outcome content fill-in

- Author the rest of the outcome pages (drafted by me, edited by you).
- Wire outcome cards on each persona band.
- Add `/demo/` page (video embed when available).
- Cross-link outcomes ↔ pillars ↔ decisions.

**Demoable as**: full content site.

### Milestone 5 — Polish, a11y audit, perf pass, deploy

- Lighthouse audit on every published page.
- Manual axe + keyboard pass.
- Broken-link scan.
- View-source clean-up.
- Confirm no sensitive content shipped (final scan).
- Promote to default branch / production.

**Demoable as**: production site at `https://shannoncarver.github.io/hackathon-may-2026/`.

## 5. Verification

- Build reproducibly from clean clone via `cd site && npm ci && npm run build`.
- Lighthouse ≥ 95 on Performance, Accessibility, Best Practices, SEO on home + one outcome + one pillar.
- Renders cleanly at 375 px viewport, no horizontal scroll.
- Logical tab order; visible focus rings; no console errors; no broken links / images.
- View-source clean.
- Each persona reaches their landing in under 10 seconds from the homepage.
- Every pillar / outcome answers, in order: What did we do? What came of it? What did we learn? What's next?
- Print stylesheet renders outcome pages to one to two clean pages.
- No sensitive content shipped (re-scan before deploy).

## 6. Pointers

- Discovery: [01-discovery.md](01-discovery.md).
- Design tokens: [design-tokens.md](design-tokens.md).
- Approved plan source: `~/.claude/plans/role-mission-you-linear-wigderson.md`.
- Reference site source: `https://github.com/LINQ-Labs/src-service-poc/tree/main/docs`.
