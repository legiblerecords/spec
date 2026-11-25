// Copies Monorail's types from a checkout of Monorail-Tech/track-legible-records into
// vendor/monorail-types/, and records which commit they came from in SOURCE.
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
console.log(`copied ${types.length} types from ${commit}`);
