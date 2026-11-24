---
title: Introduction
heading: Legible, portable, pragmatic security records
lede: Legible Records is a small set of conventions for the security records an organization owns. These include risk decisions, controls, policies, systems and data flows, diagrams, and audit evidence.
description: Conventions for security records that stay readable, move between tools and say where they came from.
---

A Legible Record says what it is, where it came from and how sensitive its fields are. It moves between tools, firms and agents, and stays readable after the app that made it is gone.

- **Legible.** Plain JSON, a short schema syntax, Markdown for long text. A person can open a file and understand it without special tools.
- **Portable.** Every file names its type and version and says where it came from. Bundles carry hashes. Records move with the organization they describe.
- **Pragmatic.** Standard JSON Schema 2020-12, a small subset of it, additive changes, and lenses only when unavoidable.

> Status: draft. Nothing is stable until version 1 is published.

## A record

A record is one JSON object in a UTF-8 `.json` file. `$type` and `version` are required. Everything else belongs to the type.

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

| Field | Required | Meaning |
|---|---|---|
| `$type` | yes | The type's identifier, a reverse domain name |
| `version` | yes | The type's major version, an integer |
| `produced_by` | no | What wrote the file: `app`, and optionally `build` and `output` |
| `source` | no | What it was built from: `system`, `refs` and `as_of` |
| `body` | depends on the type | The main content, in Markdown unless the type says otherwise |

### Reading a record

- Check `$type` and `version` first. A reader that doesn't know the type, or knows only an older major version, says so rather than guessing.
- Accept fields you don't know, and keep them when you rewrite the record.
- Show a value from an open list that you don't know as written.

### Writing a record

Write only the fields the type defines. Write keys in sorted order, numbers in their shortest form, and end the file with one newline, so the same content always gives the same bytes.

## Read the spec

This site summarizes the [specification]({{ site.spec }}). Where they differ, the spec is right.
