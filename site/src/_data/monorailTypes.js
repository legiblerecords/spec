// Monorail's types, read from vendor/monorail-types/ (copied there by
// scripts/sync-monorail-types.mjs), as the Markdown of the Monorail types page.
// The page and its Markdown copy are both built from this, so they always match the schemas.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const root = "vendor/monorail-types";

// The page's sections, in reading order. Every vendored type must be in one.
const groups = [
  { heading: "People", types: ["tech.monorail.people.person", "tech.monorail.people.role"] },
  { heading: "Policies", types: ["tech.monorail.policy.document", "tech.monorail.policy.acknowledgment"] },
  {
    heading: "Controls",
    types: ["tech.monorail.controls.control", "tech.monorail.controls.mapping", "tech.monorail.controls.statement"],
  },
  { heading: "Systems", types: ["tech.monorail.access.account", "tech.monorail.it.device"] },
  { heading: "Vulnerabilities", types: ["tech.monorail.vulnerabilities.alert", "tech.monorail.vulnerabilities.sla"] },
  { heading: "Risk", types: ["tech.monorail.risk.appetite", "tech.monorail.risk.exception"] },
];

function load(type) {
  const dir = join(root, type);
  const versions = readdirSync(dir)
    .map((name) => /^v(\d+)\.json$/.exec(name)?.[1])
    .filter(Boolean)
    .map(Number)
    .sort((a, b) => a - b);
  const version = versions.at(-1);
  const schema = JSON.parse(readFileSync(join(dir, `v${version}.json`), "utf8"));
  // Only the fields: the page shows the type, title and description above the block, and the
  // examples below it, as JSON.
  const text = readFileSync(join(dir, `v${version}.yaml`), "utf8");
  const yaml = (text.match(/^fields:\n(?:(?: .*)?\n)*/m) || [""])[0];
  return { type, version, schema, yaml };
}

// JSON for people: each object or array on one line when that fits in 72 characters,
// spread over several otherwise.
function flat(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map(flat).join(", ")}]`;
  return `{${Object.entries(value).map(([k, v]) => `${JSON.stringify(k)}: ${flat(v)}`).join(", ")}}`;
}

function pretty(value, indent = "") {
  const line = flat(value);
  if (value === null || typeof value !== "object" || indent.length + line.length <= 72) return line;
  const inner = indent + "  ";
  if (Array.isArray(value)) return `[\n${value.map((v) => inner + pretty(v, inner)).join(",\n")}\n${indent}]`;
  const entries = Object.entries(value).map(([k, v]) => `${inner}${JSON.stringify(k)}: ${pretty(v, inner)}`);
  return `{\n${entries.join(",\n")}\n${indent}}`;
}

const firstSentence = (text) => (text.match(/^.*?\.(?=\s|$)/) || [text])[0];

export default function () {
  if (!existsSync(root)) throw new Error(`${root} is missing; run scripts/sync-monorail-types.mjs`);
  const vendored = readdirSync(root).filter((name) => name.startsWith("tech.monorail."));
  const listed = groups.flatMap((g) => g.types);
  for (const type of vendored) {
    if (!listed.includes(type)) throw new Error(`${type} is vendored but not in a group in monorailTypes.js`);
  }
  for (const type of listed) {
    if (!vendored.includes(type)) throw new Error(`${type} is in monorailTypes.js but not vendored`);
  }
  const source = readFileSync(join(root, "SOURCE"), "utf8").trim();
  const sections = groups.map((g) => ({ ...g, types: g.types.map(load) }));

  const out = [];
  out.push(
    "Each type is a schema published at its `$id`, with fixtures every reader and writer must pass. They live in [Monorail-Tech/track-legible-records](https://github.com/Monorail-Tech/track-legible-records), and this page is built from them.",
    "",
    "> The `$id`s aren't live yet: publishing to monorail.tech waits for its move to Cloudflare. The `legible` tools never fetch schemas, so nothing depends on them being live.",
    "",
    "| Type | `$type` | What it is |",
    "|---|---|---|",
  );
  for (const g of sections) {
    for (const t of g.types) {
      out.push(`| [${t.schema.title}](#${t.schema.title}) | \`${t.type}\` | ${firstSentence(t.schema.description)} |`);
    }
  }
  out.push(
    "",
    "## Patterns they share",
    "",
    "- **People.** A record about a person points at them with `person`, a `ref(person)`, when the person travels in the same bundle, or describes them with `person_match`, a [person match](/types/#person-matches), when they don't. It may have both. A reader shows one it can't match as unresolved and never guesses. A schema can't require one of the two, so the type's description says so and the fixtures check it.",
    "- **Records elsewhere.** A policy acknowledgment points at the policy it acknowledges with an [external reference](/types/#external-references), pinning its revision and content hash. A vulnerability alert names what it's in, a repository, a VM or a container image, with an [identifier](/types/#identifiers).",
    "- **`source_fields`.** The source system's own fields that no field covers, under the source's names. Readers keep them and don't interpret them. They never hold a personal value that a labelled field would.",
    "- **Large sets.** Accounts, devices and vulnerability alerts often number in the thousands, and travel as [record sets](/bundles/#record-sets).",
    "- **Sensitivity labels.** Fields holding personal data carry labels such as `@user.name` and `@user.contact.email.work`.",
    "",
  );
  for (const g of sections) {
    out.push(`## ${g.heading}`, "");
    for (const t of g.types) {
      const { schema } = t;
      out.push(
        `### ${schema.title}`,
        "",
        `\`${t.type}\`, version ${t.version}, at \`${schema.$id}\`.`,
        "",
        schema.description,
        "",
        "```yaml",
        t.yaml.trimEnd(),
        "```",
        "",
      );
      for (const example of schema.examples || []) {
        out.push("Example:", "", "```json", pretty(example), "```", "");
      }
    }
  }
  out.push(`Built from ${source}.`);
  return { markdown: out.join("\n") + "\n", source };
}
