import { defineConfig } from 'astro/config';
import mdx from '@astrojs/mdx';
import sitemap from '@astrojs/sitemap';

// https://astro.build/config
export default defineConfig({
  site: 'https://shannoncarver.github.io',
  base: '/hackathon-may-2026',
  trailingSlash: 'always',
  output: 'static',
  integrations: [mdx(), sitemap()],
  build: {
    format: 'directory',
  },
});
