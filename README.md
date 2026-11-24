# Legible Records site

The documentation site for [Legible Records](https://github.com/legiblerecords/spec): what records, bundles, signatures and feeds are, and how to use the `legible` tools.

It is built with [Eleventy](https://www.11ty.dev): Markdown pages, one layout, and code highlighted at build time, so the site ships no JavaScript.

## What's here

| Path | What it is |
|---|---|
| `src/*.md` | One page each |
| `src/_data/nav.js` | The sidebar, in reading order; previous and next links follow it |
| `src/_includes/base.njk` | The layout every page uses |
| `src/css/site.css` | All the styles, black on white |
| `eleventy.config.js` | Eleventy's settings |

## Working on it

With [mise](https://mise.jdx.dev): `mise install`, then `mise run serve` to preview at http://localhost:8080 or `mise run build` to write `_site/`. Without it, Node 22 and `npm ci`, then `npm run serve` or `npm run build`.

To add a page, write `src/<name>.md` with a `title` (and optionally a `lede`) in its front matter, and add it to `src/_data/nav.js`.

## Content

The pages summarize the [spec](https://github.com/legiblerecords/spec) and the [tools](https://github.com/legiblerecords/tools) READMEs. Where they disagree, the spec is right: change the site to match it. Examples use the spec's own: `acme.example`, `Example Co`, and Monorail's published types.

## Deploying

Nothing deploys yet. `_site/` is plain static files and can be served from anywhere.
