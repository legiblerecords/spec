// Copies the specification's prose from a checkout of legiblerecords/spec into
// vendor/spec/, and records which commit it came from in SOURCE.
//
//   node scripts/sync-spec.mjs ../spec
import { execFileSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const from = process.argv[2];
if (!from) {
  console.error("usage: node scripts/sync-spec.mjs <path to legiblerecords/spec>");
  process.exit(2);
}
const prose = join(resolve(from), "spec");
if (!existsSync(prose)) {
  console.error(`${prose}: not found; give the root of a legiblerecords/spec checkout`);
  process.exit(2);
}
const commit = execFileSync("git", ["-C", resolve(from), "rev-parse", "HEAD"], { encoding: "utf8" }).trim();

const to = resolve("vendor/spec");
rmSync(to, { recursive: true, force: true });
mkdirSync(to, { recursive: true });
const files = readdirSync(prose).filter((name) => name.endsWith(".md"));
for (const name of files) copyFileSync(join(prose, name), join(to, name));
writeFileSync(join(to, "SOURCE"), `https://github.com/legiblerecords/spec/tree/${commit}\n`);
console.log(`copied ${files.length} files from ${commit}`);
