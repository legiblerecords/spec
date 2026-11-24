---
title: Schema language
lede: Types are JSON Schema 2020-12, written in a short form that expands to JSON Schema and can be generated back from it.
---

Readers and validators need only the expanded JSON Schema. The short form is for writing and reviewing.

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
  contact?: email @user.contact.email.work
```

```sh
legible expand control.yaml --base https://monorail.tech/schemas/ > control.json
legible generate control.json --base https://monorail.tech/schemas/
```

## Type expressions

| Write | Means |
|---|---|
| `name?` | An optional field. Every other field is required. |
| `string -- text` | Everything after ` -- ` is the description |
| `string`, `integer`, `number`, `boolean`, `object` | A JSON type |
| `string(date)` | A string with a format |
| `/^[A-Z]{3}$/` | A string matching a pattern |
| `integer(1..)`, `number(0..1)` | A range; either end may be left out |
| `known(a, b)` | An open list: other values are allowed |
| `enum(a, b)` | A closed list that will never grow |
| `ref(control)` | A reference to another record |
| `string[]` | A list |
| `string?` | The value may be null |
| `string \| integer` | Either |
| `date`, `slug` | A shared definition from `org.legiblerecords.common` |
| `@user.name` | A sensitivity label (`x-data`) |

A field can also be a mapping, with `description`, `type`, `fields`, `items`, `examples` and `json` keys, for nested objects and lists of objects.

## Restricted YAML

The short form is written in a small subset of YAML, so every parser reads the same file the same way and a file can't hide structure from the person reviewing it.

- No anchors, aliases or tags.
- Mapping keys are strings, and no key appears twice.
- `no`, `yes`, `~`, `0x1F` and `inf` are strings, not booleans or numbers.
- At most 64 KiB and 32 levels deep.

Spec: [schema-language.md]({{ site.spec }}/blob/main/spec/schema-language.md), [restricted-yaml.md]({{ site.spec }}/blob/main/spec/restricted-yaml.md).
