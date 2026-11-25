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
| `vendor/monorail-types/` | Monorail's types, copied from [track-legible-records](https://github.com/Monorail-Tech/track-legible-records); `SOURCE` says which commit |
| `src/_data/monorailTypes.js` | Builds the Monorail types page from them |
| `scripts/sync-monorail-types.mjs` | Copies them again |
| `vendor/spec/` | The specification's prose, copied from [legiblerecords/spec](https://github.com/legiblerecords/spec); `SOURCE` says which commit |
| `src/_data/spec.js` | Builds a page under `/spec/` from each spec file |
| `scripts/sync-spec.mjs` | Copies the spec again |
| `scripts/check-links.mjs` | Checks that every page and `#section` a link names exists |

## Working on it

With [mise](https://mise.jdx.dev): `mise install`, then `mise run serve` to preview at http://localhost:8080 or `mise run build` to write `_site/`. Without it, Node 22 and `npm ci`, then `npm run serve` or `npm run build`.

To add a page, write `src/<name>.md` with a `title` (and optionally a `lede`) in its front matter, and add it to `src/_data/nav.js`.

## Content

The pages summarize the [spec](https://github.com/legiblerecords/spec) and the [tools](https://github.com/legiblerecords/tools) READMEs. Where they disagree, the spec is right: change the site to match it. Examples use the spec's own: `acme.example`, `Example Co`, and Monorail's published types.

## Guides and the specification

The pages under `/spec/` are the specification itself, copied from the spec repo: only their links change, so they work on this site. The other pages are guides to using Legible Records. Where a rule is normative, a guide links to the spec section that states it, rather than restating it, so the two can't drift apart. When the spec changes, copy it again and commit what changes:

```sh
node scripts/sync-spec.mjs ../spec
npm run check
```

A new spec file also needs a line in `src/_data/spec.js` and in `src/_data/nav.js`; the build stops and says so until it has them. `npm run check` (or `mise run check`) builds the site and fails on any link to a page or `#section` that doesn't exist.

## Monorail types

The Monorail types page is built from the schemas in `vendor/monorail-types/`, so it shows each type exactly as published: its description, its fields in the short form, and its examples. When the types change, copy them again from a checkout of track-legible-records and commit what changes:

```sh
node scripts/sync-monorail-types.mjs ../track-legible-records
```

A new type also needs a place in a group in `src/_data/monorailTypes.js`; the build stops and says so until it has one.

## Deploying

Nothing deploys yet. `_site/` is plain static files and can be served from anywhere.

## For language models

Every page is also built as Markdown, at the page's URL with `.md` (`/types/` is also `/types.md`, `/` is `/index.md`), and linked from the page's head. `/llms.txt` lists every page with its one-line `lede`, following [llmstxt.org](https://llmstxt.org), and `/llms-full.txt` is the whole site in one file. All three are built from the same Markdown, so they never drift from the HTML.

For that to work, pages stay plain Markdown: no template tags in them, and every page has a `lede`, its one-sentence summary. Links between pages are written as `/types/`; the Markdown copies point them at `/types.md`. `src/_data/site.js` holds the site's URL, which those files use for absolute links.
