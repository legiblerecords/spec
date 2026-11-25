export default {
  name: "Legible Records",
  // Where the site is served. Used for absolute links in llms.txt and llms-full.txt.
  url: "https://legiblerecords.org",
  summary:
    "Legible Records is a draft set of conventions for the security records an organization owns: risk decisions, controls, policies, systems and data flows, diagrams, and audit evidence. Records are plain JSON that names its type and version; types are JSON Schema 2020-12 written in a short YAML form; records travel in hashed, optionally signed (ed25519) and encrypted (age) bundles, and publishers offer them to readers through feeds.",
  spec: "https://github.com/legiblerecords/spec",
  tools: "https://github.com/legiblerecords/tools",
};
