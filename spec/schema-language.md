# Schema language

Status: draft. The full grammar, with test vectors, will move here from the implementation it started in (Monorail's Track, `spec/schema-short-form.md`).

Legible Records types are JSON Schema 2020-12. They are written in a short YAML form that expands to JSON Schema exactly, and that a tool can generate back from the JSON Schema. Readers and validators only ever need the expanded JSON Schema; the short form is for writing.

## Example

```yaml
type: tech.monorail.controls.control
version: 1
title: control
description: What the organization does to make its commitments true.
fields:
  id: slug
  title: string
  status: known(proposed, active, retired)
  owner: string -- The owning role or person, by name.
  body: string -- What is done, in Markdown.
  scope?: string
  assess_every_months?: integer(1..) -- How long an assessment lasts; 12 when absent.
  due?: date
```

## Document keys

| Key | Meaning |
|---|---|
| `type` | The type identifier. Makes this a published type. |
| `version` | The major version. |
| `title` | The type's short name, used as `kind` in references. |
| `description` | What one record is. |
| `fields` | The properties. |
| `defs` | Named definitions. |
| `examples` | Example records, checked against the schema. |
| `json` | JSON Schema keywords the short form has no syntax for. Limited in published types; see [rules.md](rules.md). |

`type` and `version` expand to `$id` and to required `$type` and `version` properties with `const` values.

## Fields

A field name ending in `?` is optional. A field value is a type expression, optionally followed by ` -- ` and a description, or a mapping with `description`, `type`, `fields`, `items`, `examples` and `json`.

## Type expressions

| Expression | Means |
|---|---|
| `string`, `integer`, `number`, `boolean` | the JSON type |
| `string(date)`, `string(date-time)`, `string(email)`, `string(uri)` | a string with that format |
| `/<regex>/` | a string matching the pattern |
| `integer(<min>..<max>)`, `number(<min>..<max>)` | a range, either bound optional |
| `enum(a, b)` | a closed set of values |
| `known(a, b)` | an open set: these values are expected, others are allowed |
| `ref(<kind>)` | a `kind:key` reference |
| `<name>` | a shared definition, such as `date` or `slug` |
| `<expr>[]` | a list |
| `<expr>?` | the value may be null |
| `<expr> @<label>` | the field holds data of that kind |

`known(a, b)` expands to `{"type": "string", "examples": ["a", "b"]}`, never to `enum`.
