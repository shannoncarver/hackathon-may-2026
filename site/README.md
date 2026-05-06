# LINQ Hackathon — Showcase site

Astro 5 static site that showcases outcomes, decisions, and architecture of the LINQ Hackathon May 2026.

Built and deployed by `.github/workflows/site-deploy.yml` to `https://shannoncarver.github.io/hackathon-may-2026/`.

## Local development

```bash
cd site
npm install
npm run dev    # http://localhost:4321
```

`base: '/hackathon-may-2026'` is set in `astro.config.mjs`, so dev URLs include the base path. Visit `http://localhost:4321/hackathon-may-2026/`.

## Build

```bash
npm run build
npm run preview    # serve the production build locally
```

Output lives in `site/dist/`.

## Project layout

```
site/
├── astro.config.mjs
├── package.json
├── public/                   .nojekyll, favicon, og images
├── src/
│   ├── components/           Reusable Astro components
│   ├── content/              Content collections (outcomes, pillars, ...)
│   ├── layouts/              BaseLayout, Article
│   ├── pages/                Routes
│   └── styles/               tokens.css + global.css + print.css
└── tsconfig.json
```

## Source-of-truth content

Where possible, content is sourced from existing repo artifacts rather than duplicated:

- Pillar pages pull from `../docs/pillars/<n>-<slug>.md`.
- Decision pages pull from `../docs/decisions/<NNNN>-<slug>.md` at build time.
- Agent pages pull from `../docs/agent/<NN>-<slug>.md`.
- Outcome pages live in `src/content/outcomes/` (MDX, hand-authored against the schema).

## Design system

Tokens lifted verbatim from `LINQ-Labs/src-service-poc/docs/training/assets/styles.css`. See [`docs/site-plan/design-tokens.md`](../docs/site-plan/design-tokens.md) for the canonical spec.

## Pointers

- Discovery: [`docs/site-plan/01-discovery.md`](../docs/site-plan/01-discovery.md)
- Architecture: [`docs/site-plan/02-architecture.md`](../docs/site-plan/02-architecture.md)
- Project context: [`CLAUDE.md`](../CLAUDE.md)
