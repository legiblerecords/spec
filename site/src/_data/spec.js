// The specification's prose, read from this repository's spec/ folder, as one
// page each under /spec/. The text is the spec's own; only its links change, so
// they work on this site.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const root = "../spec";

// The pages, in reading order, each with the one-line summary llms.txt shows.
// Every file in spec/ must be here.
const pages = [
  { file: "records.md", lede: "What every record and bundle contains: references, content lines, record sets, signatures, key sets and encryption." },
  { file: "schema-language.md", lede: "The short form types are written in: its grammar, how it expands to JSON Schema, and how it is generated back." },
  { file: "restricted-yaml.md", lede: "The small subset of YAML the short form is written in, and the reasons a parser refuses a file." },
  { file: "rules.md", lede: "The published subset of JSON Schema, which changes are compatible, lenses, and conformance." },
  { file: "feeds.md", lede: "Feeds a reader polls for bundles: their layout, trust, the order of a reader's checks, reader state, access, connection files and outcome codes." },
];

export default function () {
  if (!existsSync(root)) throw new Error(`${root} is missing; build the site from site/ in the spec repository`);
  const files = readdirSync(root).filter((name) => name.endsWith(".md"));
  for (const name of files) {
    if (!pages.some((p) => p.file === name)) throw new Error(`spec/${name} isn't listed in site/src/_data/spec.js`);
  }
  return pages.map(({ file, lede }) => {
    const slug = file.replace(/\.md$/, "");
    if (!files.includes(file)) throw new Error(`spec.js lists ${file}, but spec/ doesn't have it`);
    const text = readFileSync(join(root, file), "utf8");
    const heading = text.match(/^# (.+)\n/);
    if (!heading) throw new Error(`spec/${file} doesn't start with a # heading`);
    const body = text
      .slice(heading[0].length)
      // Another spec file: its page here.
      .replace(/\]\(([a-z-]+)\.md(#[^)]*)?\)/g, (_, name, hash = "") => `](/spec/${name}/${hash})`)
      // The repository's schemas, vectors and fixtures: on GitHub.
      .replace(/\]\(\.\.\/((?:schemas|vectors|fixtures)\/?[^)]*)\)/g, (_, path) => {
        const kind = path.endsWith("/") || !/\.[a-z]+$/.test(path) ? "tree" : "blob";
        return `](https://github.com/legiblerecords/spec/${kind}/main/${path})`;
      });
    return {
      slug,
      url: `/spec/${slug}/`,
      title: heading[1],
      lede,
      markdown: `${body.trim()}\n`,
    };
  });
}
