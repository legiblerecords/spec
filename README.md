# Legible Records

**Legible, portable, pragmatic security records.**

Legible Records is a small set of conventions for security records that an organization owns: risk decisions, controls, policies, systems and data flows, diagrams, audit evidence. A Legible Record says what it is, where it came from and how sensitive its fields are. It moves between tools, firms and agents, and stays readable after the app that made it is gone.

- **Legible:** plain JSON, a short schema syntax, Markdown for long text. A person can open a file and understand it without special tools.
- **Portable:** every file names its type and version and says where it came from; bundles carry hashes. Records move with the organization they describe.
- **Pragmatic:** standard JSON Schema 2020-12 rather than a new schema language, a small subset of it, additive changes, lenses only when unavoidable.

Status: draft. Nothing here is stable yet; expect changes until version 1 is published.

## What's here

| Path | What it is |
|---|---|
| [spec/records.md](spec/records.md) | What every record and bundle contains |
| [spec/feeds.md](spec/feeds.md) | Feeds a reader polls for bundles, connection files, and the outcome codes readers return |
| [spec/schema-language.md](spec/schema-language.md) | The short form for writing schemas: its grammar, how it expands to JSON Schema, and how it's generated back |
| [spec/restricted-yaml.md](spec/restricted-yaml.md) | The YAML subset the short form is written in |
| [spec/rules.md](spec/rules.md) | The published subset, compatible changes, open value lists, lenses |
| [schemas/](schemas/) | The shared definitions every type uses, and the spec's own types (bundles, key sets, feeds, connection files), under `org.legiblerecords` |
| [fixtures/](fixtures/) | Records every implementation must accept or reject |
| [vectors/](vectors/) | Test vectors for the schema language, restricted YAML, signatures, key sets, bundles and feeds |
| [site/](site/) | The documentation site at [legiblerecords.org](https://legiblerecords.org): guides, this spec as pages, and the schemas at their `$id`s |

## Types and namespaces

Legible Records defines how types work, not which types exist. Anyone publishes types under a domain they control, in reverse order: Monorail's controls type is `tech.monorail.controls.control`, published at `https://monorail.tech/schemas/`. Definitions every type shares live here, under `org.legiblerecords.*`, with `$id`s at `https://legiblerecords.org/schemas/`.

A file is then "a Legible Record of type `tech.monorail.controls.control`."

## A record

```json
{
  "$type": "tech.monorail.risk.appetite",
  "version": 1,
  "produced_by": { "app": "tolerance.monorail.tools", "build": "1.2.0" },
  "organization": "Example Co",
  "currency": "USD",
  "decided_at": "2026-11-18",
  "thresholds": [
    { "level": "serious", "label": "A major setback", "loss": 2000000, "one_in_years": 25 },
    { "level": "existential", "label": "Company-ending", "loss": 8000000, "one_in_years": 200 }
  ]
}
```

## Stewardship

[Monorail](https://monorail.tech) started Legible Records and maintains it for now. It is meant to be shared: if others come to depend on it, stewardship can move to a neutral body. See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

## License

[Apache License 2.0](LICENSE).
