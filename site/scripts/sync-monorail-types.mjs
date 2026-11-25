// Copies Monorail's types from a checkout of Monorail-Tech/track-legible-records into
// vendor/monorail-types/, and its data taxonomy into vendor/monorail-taxonomy/, with
// the notice and licence that credit what the taxonomy is built on. Each records
// which commit it came from in SOURCE.
//
//   node scripts/sync-monorail-types.mjs ../track-legible-records
import { execFileSync } from "node:child_process";
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const from = process.argv[2];
if (!from) {
  console.error("usage: node scripts/sync-monorail-types.mjs <path to track-legible-records>");
  process.exit(2);
}
const schemas = join(resolve(from), "schemas");
if (!existsSync(schemas)) {
  console.error(`${schemas}: not found; give the root of a track-legible-records checkout`);
  process.exit(2);
}
const commit = execFileSync("git", ["-C", resolve(from), "rev-parse", "HEAD"], { encoding: "utf8" }).trim();

const to = resolve("vendor/monorail-types");
rmSync(to, { recursive: true, force: true });
mkdirSync(to, { recursive: true });
const types = readdirSync(schemas).filter((name) => name.startsWith("tech.monorail."));
for (const type of types) cpSync(join(schemas, type), join(to, type), { recursive: true });
writeFileSync(join(to, "SOURCE"), `https://github.com/Monorail-Tech/track-legible-records/tree/${commit}/schemas\n`);
// The data taxonomy: every version, with its credit. A taxonomy without its notice
// and licence isn't copied, because the page can't be shown without them.
const taxonomy = join(resolve(from), "taxonomies", "tech.monorail.data");
const taxonomyFiles = existsSync(taxonomy) ? readdirSync(taxonomy).filter((name) => /^v\d+\.json$/.test(name)) : [];
for (const needed of ["NOTICE.md", "LICENSE"]) {
  if (taxonomyFiles.length === 0 || !existsSync(join(taxonomy, needed))) {
    console.error(`${taxonomy}: needs v<n>.json, NOTICE.md and LICENSE`);
    process.exit(2);
  }
}
const toTaxonomy = resolve("vendor/monorail-taxonomy");
rmSync(toTaxonomy, { recursive: true, force: true });
mkdirSync(toTaxonomy, { recursive: true });
for (const name of [...taxonomyFiles, "NOTICE.md", "LICENSE"]) cpSync(join(taxonomy, name), join(toTaxonomy, name));
writeFileSync(join(toTaxonomy, "SOURCE"), `https://github.com/Monorail-Tech/track-legible-records/tree/${commit}/taxonomies/tech.monorail.data\n`);

console.log(`copied ${types.length} types and ${taxonomyFiles.length} taxonomy version(s) from ${commit}`);
