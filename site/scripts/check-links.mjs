// Checks every link inside the built site: each page a link names exists, and
// so does each #section, in the HTML pages and in their Markdown copies. Also
// checks that each of the repository's schemas is served at the URL its $id
// names, and that every $ref into this site names a served schema.
// Run after a build, from site/: node scripts/check-links.mjs
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";

const root = "_site";
const files = [];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path);
    else files.push(path);
  }
})(root);

const ids = new Map(); // HTML page path -> its ids
const idsOf = (path) => {
  if (!ids.has(path)) {
    const html = readFileSync(path, "utf8");
    ids.set(path, new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => m[1])));
  }
  return ids.get(path);
};
// The HTML page a site path names: /types/ and /types.md both mean _site/types/index.html.
const pageFor = (path) => {
  if (path === "/" || path === "/index.md") return join(root, "index.html");
  if (path.endsWith(".md")) return join(root, path.slice(0, -3), "index.html");
  if (path.endsWith("/")) return join(root, path, "index.html");
  return join(root, path);
};

const problems = [];
for (const file of files) {
  let links;
  if (file.endsWith(".html")) {
    links = [...readFileSync(file, "utf8").matchAll(/\shref="([^"]*)"/g)].map((m) => m[1]);
  } else if (file.endsWith(".md") || file.endsWith(".txt")) {
    const text = readFileSync(file, "utf8").replace(/```[\s\S]*?```/g, "");
    links = [...text.matchAll(/\]\(([^)\s]+)\)/g)].map((m) => m[1]);
  } else continue;
  const self = file.endsWith(".html") ? file : pageFor("/" + file.slice(root.length + 1));
  for (const raw of links) {
    const link = raw.replace(/^https:\/\/legiblerecords\.org/, "").replace(/&amp;/g, "&");
    if (/^[a-z]+:/.test(link)) continue; // another site
    const [path, hash] = link.split("#");
    const target = path === "" ? self : pageFor(path);
    if (!existsSync(target)) {
      problems.push(`${file}: ${raw}: no such page`);
      continue;
    }
    if (hash && target.endsWith(".html") && !idsOf(target).has(hash)) {
      problems.push(`${file}: ${raw}: ${path || "this page"} has no #${hash}`);
    }
  }
}
// Schemas: ../schemas/<type>/v<n>.json must have $id <site>/schemas/<type>/v<n>.json,
// and be served there byte for byte.
const SITE = "https://legiblerecords.org";
for (const type of readdirSync("../schemas")) {
  for (const file of readdirSync(join("../schemas", type)).filter((f) => /^v\d+\.json$/.test(f))) {
    const source = join("../schemas", type, file);
    const text = readFileSync(source, "utf8");
    const schema = JSON.parse(text);
    const want = `${SITE}/schemas/${type}/${file}`;
    if (schema.$id !== want) problems.push(`${source}: $id is ${schema.$id}, expected ${want}`);
    const served = join(root, "schemas", type, file);
    if (!existsSync(served)) problems.push(`${source}: not served at ${want}`);
    else if (readFileSync(served, "utf8") !== text) problems.push(`${served}: differs from ${source}`);
    for (const m of text.matchAll(/"\$ref":\s*"(https:\/\/legiblerecords\.org\/[^"#]*)/g)) {
      const target = join(root, m[1].slice(SITE.length));
      if (!existsSync(target)) problems.push(`${source}: $ref ${m[1]} isn't served`);
    }
  }
}

for (const p of problems) console.error(p);
console.log(`${files.length} files checked, ${problems.length} broken links`);
process.exit(problems.length ? 1 : 0);
