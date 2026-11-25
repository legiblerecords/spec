// Checks every link inside the built site: each page a link names exists, and
// so does each #section, in the HTML pages and in their Markdown copies.
// Run after a build: node scripts/check-links.mjs
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
for (const p of problems) console.error(p);
console.log(`${files.length} files checked, ${problems.length} broken links`);
process.exit(problems.length ? 1 : 0);
