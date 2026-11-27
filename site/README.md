# Legible Records site

The documentation site for Legible Records, served at https://legiblerecords.org: guides to using records, bundles, signatures and feeds with the `legible` tools, the specification itself, and the schemas at their `$id`s.

It lives in the spec repository, in `site/`, and builds from the repository's own `spec/` and `schemas/`, so what it serves is always what is on `main`.

It is built with [Eleventy](https://www.11ty.dev): Markdown pages, one layout, and code highlighted at build time, so the site ships no JavaScript.

## What's here

| Path | What it is |
|---|---|
| `src/*.md` | One page each |
| `src/_data/nav.js` | The sidebar, in reading order; previous and next links follow it |
| `src/_includes/base.njk` | The layout every page uses |
| `src/css/site.css` | All the styles, black on white |
| `src/icons/` | The favicon, `{ }` in Atkinson Hyperlegible Mono Bold, and the 180 px home-screen icon; both served at the site's root |
| `eleventy.config.js` | Eleventy's settings |
| `src/_data/spec.js` | Builds a page under `/spec/` from each file in `../spec/` |
| `scripts/check-links.mjs` | Checks that every page and `#section` a link names exists, and that every schema in `../schemas/` is served at its `$id` |

## Working on it

Run these from `site/`. With [mise](https://mise.jdx.dev): `mise install`, then `mise run serve` to preview at http://localhost:8080 or `mise run build` to write `_site/`. Without it, Node 22 and `npm ci`, then `npm run serve` or `npm run build`.

To add a page, write `src/<name>.md` with a `title` (and optionally a `lede`) in its front matter, and add it to `src/_data/nav.js`.

## Content

The guides summarize the spec and the [tools](https://github.com/legiblerecords/tools) README. Where they disagree, the spec is right: change the guide to match it. A change to the spec that a guide describes should change the guide in the same pull request. Examples use the spec's own: `acme.example`, `Example Co`, and Monorail's published types.

## Guides and the specification

The pages under `/spec/` are the files in `spec/`, built as they are: only their links change, so they work on this site. Links between spec files point at their pages here, and links to `schemas/`, `vectors/` and `fixtures/` point at GitHub. The other pages are guides to using Legible Records. Where a rule is normative, a guide links to the spec section that states it, rather than restating it, so the two can't drift apart.

The site also serves each `schemas/<type>/v<n>.json` at `/schemas/<type>/v<n>.json`, the URL its `$id` names, byte for byte, and the schemas' licence, `schemas/LICENSE`, at `/schemas/LICENSE`.

A new spec file needs a line in `src/_data/spec.js` and in `src/_data/nav.js`; the build stops and says so until it has them. `npm run check` (or `mise run check`) builds the site and fails on any link to a page or `#section` that doesn't exist, and on any schema that isn't served at its `$id`. CI runs it on every pull request that touches `site/`, `spec/` or `schemas/`, so renaming a spec section that a guide links to fails there.

## Who uses it

The "Who uses it" page lists organizations that publish types, with links to where they publish them. Each organization's own pages, such as Monorail's at https://monorail.tech/records/, are on its own site, beside its schemas; this site only links to them.

## Deploying

[`.github/workflows/site.yml`](../.github/workflows/site.yml) builds and checks the site on every pull request and push to `main` that touches `site/`, `spec/` or `schemas/`. On `main`, it also deploys `_site/` to GitHub Pages, but only once the repository variable `PAGES_ENABLED` is `true`. Setting it is the go-ahead to publish.

To set it up:

1. In the repository's **Settings → Pages**, set the source to **GitHub Actions**, and the custom domain to `legiblerecords.org`.
2. At the domain's DNS host, point `legiblerecords.org` at GitHub Pages: `A` records for `185.199.108.153`, `185.199.109.153`, `185.199.110.153` and `185.199.111.153`, and `AAAA` records for `2606:50c0:8000::153`, `2606:50c0:8001::153`, `2606:50c0:8002::153` and `2606:50c0:8003::153`.
3. In the organization's **Settings → Pages**, verify `legiblerecords.org`, so no other account can serve it.
4. Once the certificate is issued, turn on **Enforce HTTPS**.
5. In **Settings → Secrets and variables → Actions → Variables**, add `PAGES_ENABLED` with the value `true`. The next push to `main` that touches the site deploys it, or run the workflow by hand.

## For language models

Every page is also built as Markdown, at the page's URL with `.md` (`/types/` is also `/types.md`, `/` is `/index.md`), and linked from the page's head. `/llms.txt` lists every page with its one-line `lede`, following [llmstxt.org](https://llmstxt.org), and `/llms-full.txt` is the whole site in one file. All three are built from the same Markdown, so they never drift from the HTML.

For that to work, pages stay plain Markdown: no template tags in them, and every page has a `lede`, its one-sentence summary. Links between pages are written as `/types/`; the Markdown copies point them at `/types.md`. `src/_data/site.js` holds the site's URL, which those files use for absolute links.

## License

The pages' text, `src/*.md`, is under [CC BY 4.0](../spec/LICENSE), like the spec's. The rest of `site/` is code, under the [Apache License 2.0](../LICENSE). The footer on every page says so.
