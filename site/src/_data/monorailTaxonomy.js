// Monorail's data taxonomy, read from vendor/monorail-taxonomy/ (copied there by
// scripts/sync-monorail-types.mjs), as the Markdown of its page. The page and its
// Markdown copy are both built from this, so they always match the published file.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";

const root = "vendor/monorail-taxonomy";

// Table cells: a pipe would end the cell.
const cell = (text) => String(text ?? "").replace(/\|/g, "\\|").replace(/\s*\n\s*/g, " ");

export default function () {
  if (!existsSync(root)) throw new Error(`${root} is missing; run scripts/sync-monorail-types.mjs`);
  const versions = readdirSync(root)
    .map((name) => /^v(\d+)\.json$/.exec(name)?.[1])
    .filter(Boolean)
    .map(Number)
    .sort((a, b) => a - b);
  const version = versions.at(-1);
  const t = JSON.parse(readFileSync(join(root, `v${version}.json`), "utf8"));
  const source = readFileSync(join(root, "SOURCE"), "utf8").trim();
  // The credit is not optional: a file without it isn't shown.
  for (const field of ["work", "by", "url", "licence"]) {
    if (!t.attribution?.[field]) throw new Error(`${root}/v${version}.json has no attribution.${field}; the page must credit what the taxonomy is built on`);
  }
  if (JSON.stringify(t).includes('"ai"')) throw new Error(`${root}/v${version}.json carries AI caps, which aren't published`);

  const levelName = Object.fromEntries(t.levels.map((l) => [l.key, l.name]));
  // Four columns fit the page: the name leads the description, and Monorail's additions say so there.
  const what = (entry) => `**${cell(entry.name)}**${entry.source === "monorail" ? " (Monorail)" : ""}. ${cell(entry.description)}`;
  const file = `/monorail-data-taxonomy/v${version}.json`;
  const added = t.categories.filter((c) => c.source === "monorail").length;
  const branches = [...new Set(t.categories.map((c) => c.key.split(".")[0]))];
  const branchTitle = (key) => t.categories.find((c) => c.key === key)?.name ?? key;

  const out = [];
  out.push(
    `Monorail's types say what kind of data a field or a system holds with keys from one taxonomy, \`${t.id}\`, version ${t.version}. A field's data label, such as \`@user.contact.email.work\`, is one of its categories. So is each key in a [system](/monorail-types/#system) record's \`data_categories\` and \`customer_content\`, and each key in its \`data_subjects\` is one of its subjects.`,
    "",
    `The whole taxonomy is one file, [v${version}.json](${file}), and this page is built from it.`,
    "",
    `> The levels here are Monorail's defaults. An organization's own data policy may classify a category differently, and the defaults may change. A key is never removed or given another meaning.`,
    "",
    "## Credit",
    "",
    `Based on [${t.attribution.work}](${t.attribution.url}) by ${t.attribution.by}, licensed under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Fideslang's categories, subjects and uses are here as published.`,
    "",
    `Monorail added ${added} categories, mostly the \`company\` tree for business data, and the subject \`customer_user\`. It also added the default classification: the level of every category and the reason for it, the regime tags, and the floor of every subject. Entries Monorail added are marked (Monorail) in the tables below and \`"source": "monorail"\` in the file. Monorail's additions are under CC BY 4.0 too.`,
    "",
    `The full list of changes is in the [notice](/monorail-data-taxonomy/NOTICE.txt), and the licence text is [beside it](/monorail-data-taxonomy/LICENSE). If you copy the file, keep the credit with it.`,
    "",
    "## Levels",
    "",
    "Four levels, most sensitive first. Every category has one.",
    "",
    "| Level | Key | What it means |",
    "|---|---|---|",
    ...t.levels.map((l) => `| ${l.name} | \`${l.key}\` | ${cell(l.description)} |`),
    "",
    "## Choosing keys for a system",
    "",
    "- **Use the most specific key that is true.** `user.contact.email.work` if the system only holds work addresses, `user.contact.email` if it isn't known which kind, `user.contact` if it holds contact details of several kinds. A key takes its own level, not its children's.",
    "- **List everything it stores, processes or transmits**, including backups, copies and logs. Storage counts.",
    "- **Label the business information and the personal data.** A CRM holds `company.sales.pipeline` and also `user.name`, `user.contact.email.work` and `user.job_title`.",
    "- **Keep the organization's own data apart from what it holds for customers.** Its own data goes in `data_categories`. What customers upload or enter into the product goes in `customer_content`. Data about customers that the organization collects for itself, such as CRM contacts, is its own data.",
    "- **Say when it can't be known.** A system that holds customer content of any kind, such as a file store, sets `customer_content_unknown`. That counts as Restricted.",
    "- **Say whose data it is** in `data_subjects`. A subject's floor raises the level of personal data (`user.*`) held about them, and never lowers it: a work email address is Internal for an `employee` and Confidential for a `customer_user`.",
    `- **With no subject listed**, personal data is at least ${levelName[t.unlisted_subject_floor.floor]}.`,
    "- **A system's level** is the highest among its categories after those rules. A publisher doesn't have to work it out: a reader that holds the organization's policy does.",
    "",
    "## Categories",
    "",
    `${t.categories.length} kinds of data, in ${branches.length} trees: ${branches.map((b) => `[\`${b}\`](#${b})`).join(", ")}.`,
    "",
  );
  for (const branch of branches) {
    const rows = t.categories.filter((c) => c.key === branch || c.key.startsWith(branch + "."));
    out.push(
      `### ${branch}`,
      "",
      `${cell(t.categories.find((c) => c.key === branch)?.description ?? branchTitle(branch))}`,
      "",
      "| Key | What it is | Default level | Why |",
      "|---|---|---|---|",
      ...rows.map(
        (c) =>
          `| \`${c.key}\` | ${what(c)} | ${levelName[c.level]} | ${cell(c.why)}${c.regimes.length ? ` Regimes: ${c.regimes.map((r) => `\`${r}\``).join(", ")}.` : ""} |`,
      ),
      "",
    );
  }
  const subjects = [...t.subjects].sort((a, b) => Number(b.common) - Number(a.common));
  out.push(
    "## Subjects",
    "",
    "Whose data it is. The ones most organizations use come first.",
    "",
    "| Key | Who | Floor | Why |",
    "|---|---|---|---|",
    ...subjects.map((s) => `| \`${s.key}\` | ${what(s)} | ${levelName[s.floor]} | ${cell(s.why)} |`),
    "",
    "## Regimes",
    "",
    "A regime is a legal scope a category falls under. It is a tag on categories, to help find the data a law or standard covers; it is not legal advice.",
    "",
    "| Key | Name | What it covers | Categories |",
    "|---|---|---|---|",
    ...t.regimes.map((r) => `| \`${r.key}\` | ${cell(r.name)} | ${cell(r.description)} | ${t.categories.filter((c) => c.regimes.includes(r.key)).length} |`),
    "",
    "## Uses",
    "",
    `Fideslang's ${t.uses.length} data uses, what data is processed for, are in the file too. No Monorail type uses them yet.`,
    "",
    t.uses.filter((u) => u.parent === null).map((u) => `\`${u.key}\``).join(", ") + ", and their children.",
    "",
    "## The file",
    "",
    `[v${version}.json](${file}) has \`levels\`, \`regimes\`, \`categories\`, \`subjects\`, \`unlisted_subject_floor\` and \`uses\`. Each category has its \`key\`, \`parent\`, \`name\`, \`description\`, \`source\`, \`level\`, \`why\` and \`regimes\`; each subject its \`floor\`.`,
    "",
    "```json",
    JSON.stringify(t.categories.find((c) => c.key === "user.contact.email.work"), null, 2),
    "```",
    "",
    `Its address will be \`https://monorail.tech/taxonomies/${t.id}/v${version}.json\`, which isn't live yet: publishing to monorail.tech waits for its move to Cloudflare. It lives in [Monorail-Tech/track-legible-records](https://github.com/Monorail-Tech/track-legible-records), which copies it from Track, where the taxonomy is kept.`,
    "",
    `Built from ${source}.`,
  );
  return { markdown: out.join("\n") + "\n", version, source };
}
