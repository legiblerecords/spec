import { IdAttributePlugin } from "@11ty/eleventy";
import syntaxHighlight from "@11ty/eleventy-plugin-syntaxhighlight";
import { copyFileSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";
import nav from "./src/_data/nav.js";

// "/" -> "/index.md", "/types/" -> "/types.md": where a page's Markdown copy lives.
const markdownUrl = (url) => (url === "/" ? "/index.md" : url.replace(/\/$/, "") + ".md");

export default function (eleventyConfig) {
  // Highlighting happens at build time with Prism; the site ships no JavaScript.
  eleventyConfig.addPlugin(syntaxHighlight);
  // Headings get ids from their text, such as #content-lines, so pages can link to sections.
  eleventyConfig.addPlugin(IdAttributePlugin);
  eleventyConfig.addPassthroughCopy({ "src/css": "css" });
  eleventyConfig.addPassthroughCopy({ "src/icons": "/" });

  // The repository's schemas, at the paths their $ids name:
  // ../schemas/<type>/v<n>.json is served at /schemas/<type>/v<n>.json,
  // and their licence, ../schemas/LICENSE, at /schemas/LICENSE.
  eleventyConfig.on("eleventy.after", ({ dir }) => {
    mkdirSync(join(dir.output, "schemas"), { recursive: true });
    copyFileSync("../schemas/LICENSE", join(dir.output, "schemas", "LICENSE"));
    for (const type of readdirSync("../schemas", { withFileTypes: true }).filter((d) => d.isDirectory()).map((d) => d.name)) {
      for (const file of readdirSync(join("../schemas", type)).filter((f) => /^v\d+\.json$/.test(f))) {
        mkdirSync(join(dir.output, "schemas", type), { recursive: true });
        copyFileSync(join("../schemas", type, file), join(dir.output, "schemas", type, file));
      }
    }
  });


  eleventyConfig.addFilter("markdownUrl", markdownUrl);

  // A page's Markdown as written, with links to other pages pointing at their Markdown copies,
  // so a reader that follows them stays in Markdown.
  eleventyConfig.addFilter("asMarkdown", (raw) =>
    raw.trim().replace(/\]\((\/(?:[a-z0-9-]+\/)*)(#[^)]*)?\)/g, (_, url, hash = "") => `](${markdownUrl(url)}${hash})`),
  );

  // The documentation pages, in the sidebar's order.
  eleventyConfig.addCollection("docs", (api) => {
    const byUrl = new Map(api.getAll().map((item) => [item.url, item]));
    return nav.flatMap((group) =>
      group.pages.map((p) => {
        const item = byUrl.get(p.url);
        if (!item) throw new Error(`nav.js lists ${p.url}, but no page has that URL; pages: ${[...byUrl.keys()].join(" ")}`);
        return item;
      }),
    );
  });

  return {
    dir: { input: "src", includes: "_includes", data: "_data", output: "_site" },
    // Pages are plain Markdown, so their Markdown copies are exactly what is written.
    markdownTemplateEngine: false,
    htmlTemplateEngine: "njk",
  };
}
